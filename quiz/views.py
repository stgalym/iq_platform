import json
import logging
import random # <--- Тот самый потерянный импорт
import os
import sys
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.utils.translation import get_language
from django.utils.translation import gettext as _ # Импорт для переводов внутри Python
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from aiogram import Bot
from aiogram.types import Update
from .telegram_bot import dp  # Импортируем из нового файла
# Импорт моделей
from .models import Test, Question, Answer, UserTestResult, UserAnswer, TestInvitation, UserProfile
# Импорт сервиса ИИ
from .ai_service import generate_test_report

logger = logging.getLogger(__name__)

# Вспомогательная функция для безопасного вывода (обрабатывает проблемы с кодировкой Windows)
def safe_print(*args, **kwargs):
    """Безопасный print, который обрабатывает ошибки кодировки Unicode"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Если не удается вывести с Unicode, выводим без эмодзи
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Убираем эмодзи и заменяем на текстовые метки
                safe_arg = arg.encode('ascii', 'ignore').decode('ascii')
                safe_args.append(safe_arg if safe_arg else str(arg).encode('ascii', 'ignore').decode('ascii'))
            else:
                safe_args.append(arg)
        print(*safe_args, **kwargs)
@csrf_exempt
async def telegram_webhook(request):
    """
    Обработчик вебхуков от Telegram.
    """
    if request.method == "POST":
        try:
            # 1. Получаем токен
            token = os.getenv('TELEGRAM_TOKEN')
            if not token:
                return JsonResponse({"error": "Token not found"}, status=500)

            # 2. Создаем бота ТОЛЬКО на время этого запроса
            # Использование 'async with' гарантирует, что сессия закроется правильно
            async with Bot(token=token) as bot:
                # 3. Читаем данные от Телеграм
                data = json.loads(request.body)
                update = Update.model_validate(data)
                
                # 4. Передаем обновление в диспетчер
                # feed_update сам найдет нужный хендлер в telegram_bot.py
                await dp.feed_update(bot, update)
            
            return JsonResponse({"status": "ok"})
            
        except Exception as e:
            # Логируем ошибку, чтобы видеть её в Render Logs
            logger.error(f"Telegram Webhook Error: {e}")
            # Возвращаем 200 OK даже при ошибке логики, чтобы Телеграм не долбил нас повторами
            return JsonResponse({"status": "error", "message": str(e)}, status=200)
            
    return HttpResponse("Bot is active. Use POST to send updates.")

# --- 1. ГЛАВНАЯ (HOME) ---
def home(request):
    user_plan = 'guest'
    locked_test_id = None
    
    if request.user.is_authenticated:
        # Получаем план безопасно
        try:
            user_plan = request.user.profile.plan
        except:
            user_plan = 'free' # Если профиль не найден
            
        # Логика Free: ищем "выбранный" тест
        if user_plan == 'free':
            first_result = UserTestResult.objects.filter(user=request.user).order_by('date_taken').first()
            if first_result:
                locked_test_id = first_result.test.id
    
    # Фильтруем тесты в зависимости от тарифа пользователя
    # Тесты для рекрутеров видны только пользователям с тарифом 'hr' или суперпользователям
    if request.user.is_authenticated and (user_plan == 'hr' or request.user.is_superuser):
        # Рекрутеры видят все тесты
        tests = Test.objects.all()
    else:
        # Обычные пользователи видят только тесты для пользователей или для всех
        tests = Test.objects.exclude(test_audience='recruiter')

    return render(request, 'home.html', {
        'tests': tests,
        'user_plan': user_plan,
        'locked_test_id': locked_test_id
    })

# --- 2. ЛОГИКА ТЕСТА (Единая функция) ---
def test_detail(request, test_id):
    test = get_object_or_404(Test, pk=test_id)
    
    # === 0. ПРОВЕРКА ДОСТУПА К ТЕСТУ ДЛЯ РЕКРУТЕРОВ ===
    # Если тест предназначен только для рекрутеров, проверяем доступ
    if test.test_audience == 'recruiter':
        if not request.user.is_authenticated:
            # Неавторизованные пользователи перенаправляются на вход
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.path)
        
        # Проверяем тариф пользователя
        try:
            user_plan = request.user.profile.plan
        except:
            user_plan = 'free'
        
        # Доступ только для рекрутеров или суперпользователей
        if user_plan != 'hr' and not request.user.is_superuser:
            return render(request, 'subscription_required.html', {
                'tier_name': 'HR Recruiter',
                'message': 'Этот тест доступен только для рекрутеров. Пожалуйста, обновите подписку до тарифа HR.'
            })
    
    # === 1. ПРОВЕРКА ПОДПИСКИ ===
    if request.user.is_authenticated:
        try:
            plan = request.user.profile.plan
        except:
            plan = 'free'

        # Если FREE: проверяем, тот ли это тест
        if plan == 'free':
            first_result = UserTestResult.objects.filter(user=request.user).order_by('date_taken').first()
            
            if first_result:
                locked_test_id = first_result.test.id
                # Если пытаемся открыть НЕ тот тест, который выбрали первым
                if test.id != locked_test_id:
                    return render(request, 'subscription_required.html', {
                        'tier_name': 'Pro',
                        'message': 'В бесплатной версии вы уже выбрали один тест. Чтобы открыть остальные, перейдите на Pro.'
                    })
    # ==============================
    
    # Ключи сессии для хранения состояния
    session_key_order = f'test_{test_id}_order'
    session_key_index = f'test_{test_id}_index'
    session_key_answers = f'test_{test_id}_answers'
    session_key_locked = f'test_{test_id}_locked'

    # 1. ИНИЦИАЛИЗАЦИЯ (Если пользователь зашел первый раз)
    if session_key_order not in request.session:
        # Получаем все ID вопросов
        all_q = list(test.questions.values_list('id', flat=True))
        
        # Перемешиваем
        random.shuffle(all_q)
        
        # Обрезаем, если в настройках теста задано ограничение количества
        if test.questions_count > 0 and len(all_q) > test.questions_count:
            all_q = all_q[:test.questions_count]
            
        # Сохраняем в сессию
        request.session[session_key_order] = all_q
        request.session[session_key_index] = 0
        request.session[session_key_answers] = {}
        request.session[session_key_locked] = []
        request.session.modified = True

    # 2. ЗАГРУЖАЕМ ТЕКУЩЕЕ СОСТОЯНИЕ
    question_ids = request.session[session_key_order]
    current_index = request.session[session_key_index]
    saved_answers = request.session[session_key_answers]
    locked_steps = request.session[session_key_locked]

    # 3. ОБРАБОТКА ОТВЕТОВ (Метод POST)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Сохраняем выбранный ответ
        current_q_id = question_ids[current_index]
        selected_ans_id = request.POST.get('selected_answer')
        
        if selected_ans_id:
            saved_answers[str(current_q_id)] = int(selected_ans_id)
            request.session[session_key_answers] = saved_answers
        
        # Логика блокировки возврата назад (для вопросов на память)
        # Получаем объект вопроса, чтобы проверить exposure_time
        try:
            current_q_obj = Question.objects.get(pk=current_q_id)
            if current_q_obj.exposure_time > 0:
                if current_index not in locked_steps:
                    locked_steps.append(current_index)
                    request.session[session_key_locked] = locked_steps
        except Question.DoesNotExist:
            pass # Если вопроса нет, пропускаем логику блокировки
        
        # Навигация
        if action == 'next':
            if current_index < len(question_ids) - 1:
                request.session[session_key_index] = current_index + 1
            else:
                # Это был последний вопрос
                return finish_test(request, test, question_ids, saved_answers)
                
        elif action == 'prev':
            prev_index = current_index - 1
            # Разрешаем назад, только если шаг не заблокирован
            if prev_index >= 0 and prev_index not in locked_steps:
                request.session[session_key_index] = prev_index

        elif action == 'finish':
            return finish_test(request, test, question_ids, saved_answers)

        request.session.modified = True
        return redirect('test_detail', test_id=test_id)

    # 4. ПОДГОТОВКА К ОТОБРАЖЕНИЮ (Метод GET)
    
    # Проверка на выход за границы (на всякий случай)
    if current_index >= len(question_ids):
        return finish_test(request, test, question_ids, saved_answers)

    current_q_id = question_ids[current_index]
    
    # Пытаемся получить вопрос из БД
    try:
        current_question = Question.objects.get(pk=current_q_id)
    except Question.DoesNotExist:
        # Если вопрос удалили из базы во время прохождения теста - сброс
        if session_key_order in request.session:
            del request.session[session_key_order]
        return redirect('test_detail', test_id=test_id)

    current_answer_id = saved_answers.get(str(current_q_id))
    
    # Можно ли вернуться назад?
    can_go_back = (current_index > 0) and ((current_index - 1) not in locked_steps)
    is_last = (current_index == len(question_ids) - 1)

    # Получаем и перемешиваем варианты ответов
    answers_list = list(current_question.answers.all())
    random.shuffle(answers_list)

    return render(request, 'test_detail.html', {
        'test': test,
        'question': current_question,
        'answers_list': answers_list, 
        'current_index': current_index + 1,
        'total_questions': len(question_ids),
        'current_answer_id': current_answer_id,
        'can_go_back': can_go_back,
        'is_last': is_last,
    })

# --- 3. ФИНАЛИЗАЦИЯ ТЕСТА ---
def finish_test(request, test, question_ids, saved_answers):
    score = 0
    category_stats = {}
    
    user = request.user if request.user.is_authenticated else None
    
    # Создаем запись результата
    result_obj = UserTestResult.objects.create(user=user, test=test, score=0)
    
    # 1. ОПТИМИЗАЦИЯ: Загружаем вопросы массово
    questions_map = Question.objects.in_bulk(question_ids)
    user_answers_to_create = []
    
    # Переменная для определения типа теста
    has_psychology_questions = False

    for q_id in question_ids:
        question = questions_map.get(q_id)
        if not question:
            continue

        # Собираем статистику для определения типа теста
        cat_code = question.category.lower() if question.category else ""
        if 'psychology' in cat_code or 'психология' in cat_code:
            has_psychology_questions = True

        ans_id = saved_answers.get(str(q_id))
        selected_answer = None
        is_correct = False
        
        if ans_id:
            selected_answer = Answer.objects.filter(pk=ans_id).first()
            if selected_answer and selected_answer.is_correct:
                is_correct = True
                score += 1
                # Для статистики берем красивое название категории
                cat_display = question.get_category_display()
                category_stats[cat_display] = category_stats.get(cat_display, 0) + 1
        
        user_answers_to_create.append(UserAnswer(
            result=result_obj,
            question=question,
            selected_answer=selected_answer,
            is_correct=is_correct
        ))

    # ОПРЕДЕЛЯЕМ ТИП ТЕСТА
    test_type = 'iq' # По умолчанию
    # Если в тесте есть вопросы категории psychology ИЛИ в названии теста есть "Психология"
    if has_psychology_questions or 'psychology' in test.title_en.lower() or 'психология' in test.title_ru.lower():
        test_type = 'psychology'

    # Для психологических тестов собираем детальную информацию об ответах ДО сохранения
    detailed_answers = None
    if test_type == 'psychology':
        detailed_answers = []
        # Загружаем все правильные ответы заранее для оптимизации
        all_questions_ids = [ua.question.id for ua in user_answers_to_create]
        correct_answers_map = {
            ans.question_id: ans 
            for ans in Answer.objects.filter(question_id__in=all_questions_ids, is_correct=True)
        }
        
        for user_answer_obj in user_answers_to_create:
            question = user_answer_obj.question
            selected_answer = user_answer_obj.selected_answer
            correct_answer = correct_answers_map.get(question.id)
            
            detailed_answers.append({
                'question_text': question.text,
                'selected_answer_text': selected_answer.text if selected_answer else 'Не отвечено',
                'correct_answer_text': correct_answer.text if correct_answer else 'Не определено',
                'is_correct': user_answer_obj.is_correct
            })

    # Сохраняем ответы
    if user_answers_to_create:
        UserAnswer.objects.bulk_create(user_answers_to_create)

    result_obj.score = score
    
    # Определяем, для кого делается анализ
    # Если тест проходит через приглашение (кандидат) - анализ для рекрутера
    # Если тест проходит обычный пользователь - анализ для пользователя
    invite_id = request.session.get('active_invitation_id')
    is_candidate_test = invite_id is not None
    
    # Определяем аудиторию анализа на основе:
    # 1. Если это кандидат (через приглашение) - всегда для рекрутера
    # 2. Если это пользователь - смотрим на настройку теста или делаем для пользователя
    if is_candidate_test:
        analysis_for = 'recruiter'
    else:
        # Если тест предназначен для рекрутеров, но проходит пользователь - все равно для пользователя
        # Если тест для пользователей или для всех - для пользователя
        if test.test_audience == 'recruiter':
            analysis_for = 'recruiter'  # Тест для рекрутеров, но проходит пользователь
        else:
            analysis_for = 'user'  # Обычный пользователь проходит тест
    
    # Генерируем отчет с учетом типа
    current_lang = get_language()
    username_for_ai = user.username if user else "Candidate"
    
    try:
        # Отладочная информация
        safe_print(f"[DEBUG] test_type={test_type}, analysis_for={analysis_for}, is_candidate={is_candidate_test}, detailed_answers count={len(detailed_answers) if detailed_answers else 0}, total_questions={len(question_ids)}")
        
        # Передаем test_type, analysis_for и детальную информацию об ответах в функцию
        analysis_result = generate_test_report(
            username_for_ai, 
            category_stats, 
            score, 
            test_type=test_type, 
            language=current_lang,
            detailed_answers=detailed_answers,
            total_questions=len(question_ids),
            analysis_for=analysis_for  # Новый параметр: 'recruiter' или 'user'
        )
        
        if analysis_result:
            result_obj.ai_analysis = analysis_result
            safe_print(f"[OK] AI Analysis generated successfully, length: {len(analysis_result)}")
        else:
            safe_print(f"[WARNING] AI Analysis returned empty, using fallback")
            result_obj.ai_analysis = "Analysis currently unavailable."
        
    except Exception as e:
        safe_print(f"[ERROR] AI Error: {e}")
        import traceback
        traceback.print_exc()
        result_obj.ai_analysis = f"Analysis currently unavailable. Error: {str(e)[:100]}"
    
    # Сохраняем результат безопасно, используя update() для оптимизации памяти
    try:
        # Используем update() вместо save() для больших текстов - это более эффективно
        from django.db import transaction
        with transaction.atomic():
            UserTestResult.objects.filter(pk=result_obj.pk).update(
                score=result_obj.score,
                ai_analysis=result_obj.ai_analysis
            )
        safe_print(f"[OK] Result saved successfully (ID: {result_obj.id})")
    except Exception as e:
        safe_print(f"[ERROR] Error saving result: {e}")
        import traceback
        traceback.print_exc()
        # Пробуем сохранить без AI анализа
        try:
            with transaction.atomic():
                UserTestResult.objects.filter(pk=result_obj.pk).update(
                    score=result_obj.score,
                    ai_analysis=None
                )
            safe_print(f"[WARNING] Result saved without AI analysis")
        except Exception as e2:
            safe_print(f"[CRITICAL] Could not save result at all: {e2}")
            # В критическом случае удаляем объект, чтобы не было мусора в БД
            try:
                result_obj.delete()
            except:
                pass
            raise
    
    # Очистка сессии
    keys = [f'test_{test.id}_order', f'test_{test.id}_index', f'test_{test.id}_answers', f'test_{test.id}_locked']
    for k in keys:
        if k in request.session:
            del request.session[k]

    # Обработка приглашений (используем уже определенный invite_id выше)
    if invite_id:
        try:
            invite = TestInvitation.objects.get(pk=invite_id)
            invite.result = result_obj
            invite.completed = True
            invite.save()
            del request.session['active_invitation_id']
            return render(request, 'candidate_success.html')
        except TestInvitation.DoesNotExist:
            pass

    return redirect('result_detail', result_id=result_obj.id)

# --- 4. ПРОСМОТР РЕЗУЛЬТАТА ---
def result_detail(request, result_id):
    # 1. Сначала просто ищем результат по ID (независимо от того, чей он)
    result = get_object_or_404(UserTestResult, pk=result_id)
    
    # 2. Проверяем права доступа
    # Разрешаем просмотр, если:
    # - Пользователь владелец результата (result.user == request.user)
    # - ИЛИ Пользователь - сотрудник/админ (request.user.is_staff)
    # - ИЛИ Результат анонимный (result.user is None) — чтобы вы могли видеть свои тесты при разработке
    
    is_owner = (request.user.is_authenticated and result.user == request.user)
    is_staff = (request.user.is_authenticated and request.user.is_staff)
    is_anonymous_result = (result.user is None)

    if not (is_owner or is_staff or is_anonymous_result):
        # Если ни одно условие не совпало — запрещаем доступ
        return render(request, 'hr/error.html', {'message': 'У вас нет прав для просмотра этого результата.'})

    user_answers = result.details.all()
    
    return render(request, 'test_result.html', {
        'test': result.test,
        'score': result.score,
        'total': user_answers.count(),
        'ai_analysis': result.ai_analysis,
        'user_answers': user_answers,
        'is_old_result': True 
    })

# --- 5. HR DASHBOARD (Панель рекрутера) ---
# quiz/views.py

@login_required
def hr_dashboard(request):
    # 1. Получаем план подписки
    try:
        # Пытаемся получить профиль
        profile = UserProfile.objects.get(user=request.user)
        plan = profile.plan
    except UserProfile.DoesNotExist:
        # Если профиля вдруг нет — считаем халявщиком
        plan = 'free'

    # --- ДИАГНОСТИКА (Смотрите в терминал!) ---
    safe_print(f"[DEBUG] PROVERKA: User={request.user.username} | Plan={plan} | Superuser={request.user.is_superuser}")
    # ------------------------------------------

    # 2. ЖЕСТКАЯ ПРОВЕРКА ДОСТУПА
    # Доступ разрешен ТОЛЬКО если (План == HR) ИЛИ (Это Суперюзер)
    if plan != 'hr' and not request.user.is_superuser:
        # Если условия не совпали — показываем заглушку
        return render(request, 'subscription_required.html', {
            'tier_name': 'HR Recruiter',
            'message': 'Этот раздел доступен только для рекрутеров. Пожалуйста, обновите подписку.'
        })

    # 3. Если проверка пройдена — показываем дашборд
    invitations = TestInvitation.objects.filter(recruiter=request.user).order_by('-created_at')
    
    # Чтобы в выпадающем списке не было ошибок при создании приглашения
    tests = Test.objects.all() 
    
    if request.method == 'POST':
        test_id = request.POST.get('test_id')
        email = request.POST.get('candidate_email')
        
        if test_id and email:
            test = get_object_or_404(Test, pk=test_id)
            TestInvitation.objects.create(
                recruiter=request.user,
                test=test,
                candidate_email=email
            )
            return redirect('hr_dashboard') # Перезагрузка страницы после создания
    
    return render(request, 'hr/dashboard.html', {
        'invitations': invitations,
        'tests': tests,
    })

# --- 6. ПРИНЯТИЕ ПРИГЛАШЕНИЯ ---
def accept_invitation(request, uuid):
    invite = get_object_or_404(TestInvitation, uuid=uuid)
    
    if invite.completed:
        return render(request, 'hr/error.html', {'message': 'Эта ссылка уже была использована.'})
    
    # ВАЖНО: Выходим из текущего аккаунта (если админ тестирует ссылку)
    if request.user.is_authenticated:
        logout(request)

    # Сохраняем ID приглашения в сессию, чтобы "finish_test" знал, куда сохранить результат
    request.session['active_invitation_id'] = invite.id
    
    # Перенаправляем на начало теста
    return redirect('test_detail', test_id=invite.test.id)

@login_required
def upgrade_profile(request, plan_type):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if plan_type == 'pro':
        profile.plan = 'pro'
        messages.success(request, 'Оплата успешна! Вы перешли на тариф PRO.')
    elif plan_type == 'hr':
        profile.plan = 'hr'
        messages.success(request, 'Оплата успешна! Кабинет рекрутера открыт.')
    elif plan_type == 'free':
        profile.plan = 'free'
        messages.info(request, 'Тариф сброшен до Free.')

    profile.save()
    
    if plan_type == 'hr':
        return redirect('hr_dashboard')
    return redirect('home')
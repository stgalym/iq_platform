import json
import logging
import random # <--- Тот самый потерянный импорт
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
from .ai_service import generate_iq_report

logger = logging.getLogger(__name__)
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
    tests = Test.objects.all()
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

    return render(request, 'home.html', {
        'tests': tests,
        'user_plan': user_plan,
        'locked_test_id': locked_test_id
    })

# --- 2. ЛОГИКА ТЕСТА (Единая функция) ---
def test_detail(request, test_id):
    test = get_object_or_404(Test, pk=test_id)
    
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
    
    # Определяем пользователя (если он вошел) или None (если Кандидат по ссылке)
    user = request.user if request.user.is_authenticated else None
    
    # Создаем запись результата
    result_obj = UserTestResult.objects.create(user=user, test=test, score=0)
    
    # Подсчет баллов
    for q_id in question_ids:
        try:
            question = Question.objects.get(pk=q_id)
        except Question.DoesNotExist:
            continue

        ans_id = saved_answers.get(str(q_id))
        selected_answer = None
        is_correct = False
        
        if ans_id:
            selected_answer = Answer.objects.filter(pk=ans_id).first()
            if selected_answer and selected_answer.is_correct:
                is_correct = True
                score += 1
                cat = question.get_category_display()
                category_stats[cat] = category_stats.get(cat, 0) + 1
        
        # Сохраняем детальный ответ
        UserAnswer.objects.create(
            result=result_obj,
            question=question,
            selected_answer=selected_answer,
            is_correct=is_correct
        )

    # Обновляем итоговый балл
    result_obj.score = score
    
    # Генерируем AI отчет
    current_lang = get_language()
    username_for_ai = user.username if user else "Candidate"
    
    # Внимание: убедитесь, что функция generate_iq_report у вас работает корректно
    result_obj.ai_analysis = generate_iq_report(username_for_ai, category_stats, score, language=current_lang)
    result_obj.save()
    
    # Очищаем сессию от данных этого теста
    keys = [f'test_{test.id}_order', f'test_{test.id}_index', f'test_{test.id}_answers', f'test_{test.id}_locked']
    for k in keys:
        if k in request.session:
            del request.session[k]

    # === РАЗВИЛКА: КАНДИДАТ или ПОЛЬЗОВАТЕЛЬ ===
    
    invite_id = request.session.get('active_invitation_id')
    
    if invite_id:
        # СЦЕНАРИЙ 1: Это кандидат по ссылке
        try:
            invite = TestInvitation.objects.get(pk=invite_id)
            invite.result = result_obj
            invite.completed = True
            invite.save()
            
            # Удаляем ID приглашения, чтобы сессия стала чистой
            del request.session['active_invitation_id']
            
            # Показываем "Спасибо" (кандидат не видит баллы)
            return render(request, 'candidate_success.html')
            
        except TestInvitation.DoesNotExist:
            # Если приглашение не найдено (странная ситуация), показываем как обычному юзеру
            pass

    # СЦЕНАРИЙ 2: Это обычный пользователь (видит свои баллы)
    # Используем redirect, чтобы при обновлении страницы тест не отправлялся заново
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
    print(f"🔍 ПРОВЕРКА: Юзер={request.user.username} | План={plan} | Суперюзер={request.user.is_superuser}")
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
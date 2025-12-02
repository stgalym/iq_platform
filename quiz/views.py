import random
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Test, Question, Answer, UserTestResult, UserAnswer
from .ai_service import generate_iq_report

# --- 1. ГЛАВНАЯ СТРАНИЦА (Которую мы потеряли) ---
def home(request):
    # Если пользователь вошел - показываем тесты
    if request.user.is_authenticated:
        tests = Test.objects.all()
    else:
        # Если гость - список пуст (шаблон покажет лендинг)
        tests = []
    return render(request, 'home.html', {'tests': tests})

# --- 2. ЛОГИКА ТЕСТА (С сессиями и навигацией) ---
def test_detail(request, test_id):
    test = get_object_or_404(Test, pk=test_id)
    
    # Ключи сессии
    session_key_order = f'test_{test_id}_order'
    session_key_index = f'test_{test_id}_index'
    session_key_answers = f'test_{test_id}_answers'
    session_key_locked = f'test_{test_id}_locked'

    # ИНИЦИАЛИЗАЦИЯ (Первый вход)
    if session_key_order not in request.session:
        all_q = list(test.questions.values_list('id', flat=True))
        random.shuffle(all_q)
        
        if test.questions_count > 0 and len(all_q) > test.questions_count:
            all_q = all_q[:test.questions_count]
            
        request.session[session_key_order] = all_q
        request.session[session_key_index] = 0
        request.session[session_key_answers] = {}
        request.session[session_key_locked] = []
        request.session.modified = True

    # Загружаем состояние
    question_ids = request.session[session_key_order]
    current_index = request.session[session_key_index]
    saved_answers = request.session[session_key_answers]
    locked_steps = request.session[session_key_locked]

    # ОБРАБОТКА ДЕЙСТВИЙ (POST)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Сохраняем ответ
        current_q_id = question_ids[current_index]
        selected_ans_id = request.POST.get('selected_answer')
        
        if selected_ans_id:
            saved_answers[str(current_q_id)] = int(selected_ans_id)
            request.session[session_key_answers] = saved_answers
        
        # Блокировка возврата для вопросов на Память
        current_q_obj = Question.objects.get(pk=current_q_id)
        if current_q_obj.exposure_time > 0:
            if current_index not in locked_steps:
                locked_steps.append(current_index)
                request.session[session_key_locked] = locked_steps
        
        # Навигация
        if action == 'next':
            if current_index < len(question_ids) - 1:
                request.session[session_key_index] = current_index + 1
            else:
                return finish_test(request, test, question_ids, saved_answers)
                
        elif action == 'prev':
            prev_index = current_index - 1
            if prev_index >= 0 and prev_index not in locked_steps:
                request.session[session_key_index] = prev_index

        elif action == 'finish':
            return finish_test(request, test, question_ids, saved_answers)

        request.session.modified = True
        return redirect('test_detail', test_id=test_id)

    # ОТОБРАЖЕНИЕ (GET)
    if current_index >= len(question_ids):
        return finish_test(request, test, question_ids, saved_answers)

    current_q_id = question_ids[current_index]
    current_question = get_object_or_404(Question, pk=current_q_id)
    current_answer_id = saved_answers.get(str(current_q_id))
    
    can_go_back = (current_index > 0) and ((current_index - 1) not in locked_steps)
    is_last = (current_index == len(question_ids) - 1)

    return render(request, 'test_detail.html', {
        'test': test,
        'question': current_question,
        'current_index': current_index + 1,
        'total_questions': len(question_ids),
        'current_answer_id': current_answer_id,
        'can_go_back': can_go_back,
        'is_last': is_last,
    })

# --- 3. ФУНКЦИЯ ЗАВЕРШЕНИЯ ---
def finish_test(request, test, question_ids, saved_answers):
    score = 0
    category_stats = {}
    
    result_obj = UserTestResult.objects.create(user=request.user, test=test, score=0)
    
    for q_id in question_ids:
        question = Question.objects.get(pk=q_id)
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
        
        UserAnswer.objects.create(
            result=result_obj,
            question=question,
            selected_answer=selected_answer,
            is_correct=is_correct
        )

    result_obj.score = score
    result_obj.ai_analysis = generate_iq_report(request.user.username, category_stats, score)
    result_obj.save()
    
    # Чистим сессию
    keys = [f'test_{test.id}_order', f'test_{test.id}_index', f'test_{test.id}_answers', f'test_{test.id}_locked']
    for k in keys:
        if k in request.session:
            del request.session[k]

    return render(request, 'test_result.html', {
        'test': test,
        'score': score,
        'total': len(question_ids),
        'ai_analysis': result_obj.ai_analysis
    })

# ... в конец файла ...

def result_detail(request, result_id):
    # Достаем результат, но только если он принадлежит текущему пользователю (чужие смотреть нельзя)
    result = get_object_or_404(UserTestResult, pk=result_id, user=request.user)
    
    # Достаем детальные ответы (какие кнопки нажимал пользователь)
    user_answers = result.details.all()
    
    return render(request, 'test_result.html', {
        'test': result.test,
        'score': result.score,
        'total': user_answers.count(),
        'ai_analysis': result.ai_analysis,
        'user_answers': user_answers, # Передаем детализацию в шаблон
        'is_old_result': True # Флаг, что это архивный просмотр
    })
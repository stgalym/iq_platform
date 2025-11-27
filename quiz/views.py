from django.shortcuts import render, get_object_or_404, redirect
from .models import Test, Question, Answer, UserTestResult

def home(request):
    tests = Test.objects.all()
    return render(request, 'home.html', {'tests': tests})

def test_detail(request, test_id):
    test = get_object_or_404(Test, pk=test_id)
    
    # Если пользователь нажал кнопку "Завершить" (метод POST)
    if request.method == 'POST':
        score = 0 # Счётчик правильных ответов
        total_questions = test.questions.count()
        
        # Пробегаемся по всем вопросам теста
        for question in test.questions.all():
            # Имя поля в HTML мы делали как 'question_ID' (например, question_5)
            # Получаем ID ответа, который выбрал пользователь
            selected_answer_id = request.POST.get(f'question_{question.id}')
            
            if selected_answer_id:
                # Находим этот ответ в базе
                answer = Answer.objects.filter(pk=selected_answer_id).first()
                # Если ответ найден и он правильный - добавляем балл
                if answer and answer.is_correct:
                    score += 1
        
        # Сохраняем результат в базу (только если пользователь вошел в систему)
        if request.user.is_authenticated:
            UserTestResult.objects.create(
                user=request.user,
                test=test,
                score=score
            )
            # Тут можно было бы обновить общий IQ пользователя, сделаем это позже
        
        # Показываем страницу с результатом
        return render(request, 'test_result.html', {
            'test': test,
            'score': score,
            'total': total_questions
        })

    # Если это просто открытие страницы (метод GET)
    return render(request, 'test_detail.html', {'test': test})

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from quiz.models import UserTestResult # Импортируем результаты

@login_required # Декоратор: не пускает на страницу, если не вошел
def profile(request):
    # Достаем результаты ТОЛЬКО текущего пользователя
    results = UserTestResult.objects.filter(user=request.user).order_by('-date_taken')

    return render(request, 'profile.html', {'results': results})

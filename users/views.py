import random
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from quiz.models import UserTestResult
from .forms import CustomUserCreationForm, CustomUserUpdateForm

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Сразу входим после регистрации
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile(request):
    results = UserTestResult.objects.filter(user=request.user).order_by('-date_taken')
    # Генерация кода для бота, если его нет
    user = request.user
    if not user.telegram_chat_id: # Если бот еще не подключен
        if not user.telegram_code: # И кода нет
            # Генерируем случайное число от 10000 до 99999
            user.telegram_code = str(random.randint(10000, 99999))
            user.save()
    return render(request, 'profile.html', {'results': results})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = CustomUserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            # messages.success(request, 'Ваш профиль обновлен!') # Можно добавить уведомление
            return redirect('profile')
    else:
        # Заполняем форму текущими данными пользователя
        form = CustomUserUpdateForm(instance=request.user)
    
    return render(request, 'users/edit_profile.html', {'form': form})
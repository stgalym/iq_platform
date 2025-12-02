from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email')
        
class CustomUserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        # Добавляем bot_category в список полей
        fields = ('first_name', 'last_name', 'email', 'bot_category')
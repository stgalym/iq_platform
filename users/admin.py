from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # Добавляем наши поля в отображение "Список пользователей"
    list_display = ('username', 'email', 'iq_score', 'is_premium', 'is_staff', 'telegram_chat_id')
    
    # Добавляем наши поля в форму редактирования пользователя
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {'fields': ('iq_score', 'is_premium')}),
        ('Telegram Info', {'fields': ('telegram_chat_id', 'telegram_code')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)

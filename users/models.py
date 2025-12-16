from django.contrib.auth.models import AbstractUser
from django.db import models

# Дублируем категории (или можно вынести их в отдельный файл constants.py, но пока так)
CATEGORY_CHOICES = [
    ('logic', 'Логика'),
    ('math', 'Математика'),
    ('spatial', 'Пространственное мышление'),
    ('memory', 'Память'),
    ('Multi_table', 'Таблица умножения'),
]

# Список языков
LANG_CHOICES = [
    ('ru', 'Русский'),
    ('kk', 'Qazaqsha'),
    ('en', 'English'),
]

class CustomUser(AbstractUser):
    iq_score = models.IntegerField(null=True, blank=True, verbose_name="IQ Результат")
    is_premium = models.BooleanField(default=False, verbose_name="Премиум аккаунт")
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID Телеграм чата")
    telegram_code = models.CharField(max_length=10, blank=True, null=True, verbose_name="Код подключения")

    # НОВОЕ ПОЛЕ: Настройка для бота
    bot_category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='logic', 
        verbose_name="Категория для тренировок в Telegram"
    )
    # НОВОЕ ПОЛЕ
    language = models.CharField(
        max_length=5, 
        choices=LANG_CHOICES, 
        default='ru', 
        verbose_name="Язык / Language"
    )

    def __str__(self):
        return self.username
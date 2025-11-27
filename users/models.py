from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Добавляем поле для хранения IQ. Может быть пустым (null=True), если тест еще не пройден.
    iq_score = models.IntegerField(null=True, blank=True, verbose_name="IQ Результат")
    
    # Флаг платного режима
    is_premium = models.BooleanField(default=False, verbose_name="Премиум аккаунт")

    # Можно добавить аватарку или город позже
    
    def __str__(self):
        return self.username

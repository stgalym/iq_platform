from django.db import models
from django.conf import settings # Чтобы сослаться на нашего пользователя

# 1. Модель самого Теста (например, "Тест на IQ - Легкий")
class Test(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название теста")
    description = models.TextField(verbose_name="Описание", blank=True)
    
    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"

# 2. Модель Вопроса
class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions', verbose_name="Тест")
    text = models.TextField(verbose_name="Текст вопроса")
    order = models.IntegerField(default=0, verbose_name="Порядковый номер")

    def __str__(self):
        return self.text[:50]  # Показываем первые 50 символов

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"

# 3. Модель Варианта ответа
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name="Вопрос")
    text = models.CharField(max_length=255, verbose_name="Текст ответа")
    is_correct = models.BooleanField(default=False, verbose_name="Верный ответ?")

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"

class UserTestResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Пользователь")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, verbose_name="Тест")
    score = models.IntegerField(verbose_name="Количество правильных ответов")
    date_taken = models.DateTimeField(auto_now_add=True, verbose_name="Дата прохождения")

    def __str__(self):
        return f"{self.user} - {self.test} - {self.score}"

    class Meta:
        verbose_name = "Результат теста"
        verbose_name_plural = "Результаты тестов"

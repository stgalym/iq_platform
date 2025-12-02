from django.db import models
from django.conf import settings

# Категории
CATEGORY_CHOICES = [
    ('logic', 'Логика'),
    ('math', 'Математика'),
    ('spatial', 'Пространственное мышление'),
    ('memory', 'Память'),
]

class Test(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    image = models.ImageField(upload_to='test_covers/', blank=True, null=True, verbose_name="Обложка")
    
    # Настройки прохождения (День 17)
    questions_count = models.IntegerField(default=10, verbose_name="Кол-во вопросов (N)")
    time_limit = models.IntegerField(default=0, verbose_name="Время на тест (минуты)", help_text="0 - без ограничений")

    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"

# ... (предыдущий код Test) ...

class Question(models.Model):
    test = models.ForeignKey(Test, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField(verbose_name="Текст вопроса")
    image = models.ImageField(upload_to='questions/', blank=True, null=True, verbose_name="Картинка вопроса")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='logic', verbose_name="Категория")
    order = models.IntegerField(default=0, verbose_name="Порядок")
    
    # --- НОВЫЕ ПОЛЯ ДЛЯ ПРОФЕССИОНАЛЬНОГО РЕЖИМА ---
    exposure_time = models.IntegerField(
        default=0, 
        verbose_name="Время показа (сек)", 
        help_text="Сколько секунд показывать картинку (для тестов на память). 0 - показывать всегда."
    )
    answer_time = models.IntegerField(
        default=60, 
        verbose_name="Время на ответ (сек)", 
        help_text="Лимит времени конкретно на этот вопрос."
    )

    def __str__(self):
        return self.text[:50]
    
    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    text = models.CharField(max_length=255, verbose_name="Текст ответа")
    is_correct = models.BooleanField(default=False, verbose_name="Верный?")

    def __str__(self):
        return self.text
    
    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"

class UserTestResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    score = models.IntegerField(verbose_name="Баллы")
    ai_analysis = models.TextField(blank=True, null=True, verbose_name="Анализ ИИ")
    date_taken = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Результат теста"
        verbose_name_plural = "Результаты тестов"

class UserAnswer(models.Model):
    result = models.ForeignKey(UserTestResult, related_name='details', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True)
    is_correct = models.BooleanField(default=False)

# --- ВОТ ЭТУ МОДЕЛЬ МЫ ПОТЕРЯЛИ, ВОЗВРАЩАЕМ ЕЁ ---
class BotResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.question} - {self.is_correct}"
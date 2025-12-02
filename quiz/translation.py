from modeltranslation.translator import register, TranslationOptions
from .models import Test, Question, Answer

# Настройки перевода для Теста
@register(Test)
class TestTranslationOptions(TranslationOptions):
    fields = ('title', 'description') # Переводим Заголовок и Описание

# Настройки перевода для Вопроса
@register(Question)
class QuestionTranslationOptions(TranslationOptions):
    fields = ('text',) # Переводим текст вопроса

# Настройки перевода для Ответа
@register(Answer)
class AnswerTranslationOptions(TranslationOptions):
    fields = ('text',) # Переводим текст ответа
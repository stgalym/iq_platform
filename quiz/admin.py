from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline
from .models import Test, Question, Answer, UserTestResult

# Для ответов (так как они внутри вопросов) используем TranslationTabularInline
class AnswerInline(TranslationTabularInline):
    model = Answer
    extra = 4

# Для вопросов используем TranslationAdmin
class QuestionAdmin(TranslationAdmin):
    inlines = [AnswerInline]
    list_display = ('text', 'test', 'order')
    list_filter = ('test',)
    search_fields = ('text',)
    
    # Это добавит вкладки языков в админку (для удобства)
    class Media:
        js = (
            'http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js',
            'http://ajax.googleapis.com/ajax/libs/jqueryui/1.10.2/jquery-ui.min.js',
            'modeltranslation/js/tabbed_translation_fields.js',
        )
        css = {
            'screen': ('modeltranslation/css/tabbed_translation_fields.css',),
        }

# Для тестов тоже TranslationAdmin
class TestAdmin(TranslationAdmin):
    list_display = ('title', 'description')
    
    class Media:
        js = (
            'http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js',
            'http://ajax.googleapis.com/ajax/libs/jqueryui/1.10.2/jquery-ui.min.js',
            'modeltranslation/js/tabbed_translation_fields.js',
        )
        css = {
            'screen': ('modeltranslation/css/tabbed_translation_fields.css',),
        }

# Регистрируем
admin.site.register(Test, TestAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(UserTestResult) # Результаты переводить не надо
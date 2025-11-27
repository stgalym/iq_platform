from django.contrib import admin
from .models import Test, Question, Answer, UserTestResult # <--- Добавили UserTestResult

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4

class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerInline]
    list_display = ('text', 'test', 'order')
    list_filter = ('test',)
    search_fields = ('text',)

# Настройки для отображения результатов
class UserTestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'test', 'score', 'date_taken') # <--- Столбцы таблицы
    list_filter = ('test', 'date_taken') # <--- Фильтры справа

admin.site.register(Test)
admin.site.register(Question, QuestionAdmin)
admin.site.register(UserTestResult, UserTestResultAdmin) # <--- Самая важная строка

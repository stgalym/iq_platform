import csv
import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from quiz.models import Test, Question, Answer

class Command(BaseCommand):
    help = 'Импорт вопросов на трех языках (RU/KK/EN)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')

    def handle(self, *args, **kwargs):
        csv_path = kwargs['csv_file']
        
        # Создаем тест (заголовки на 3 языках)
        main_test, _ = Test.objects.get_or_create(
            title_ru="Таблица умножения (Мультиязычный)",
            title_kk="Көбейту кестесі (Көптілді)",
            title_en="Multiplication table (Multilingual)",
            defaults={
                'description_ru': 'Таблица умножения на трех языках.',
                'description_kk': 'Көбейту кестесі',
                'description_en': 'Multiplication table ',
                'questions_count': 96,
                'time_limit': 60
            }
        )

        source_images_dir = os.path.join(settings.MEDIA_ROOT, 'import_images')
        target_images_dir = os.path.join(settings.MEDIA_ROOT, 'questions')
        if not os.path.exists(target_images_dir):
            os.makedirs(target_images_dir)

        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'Файл {csv_path} не найден!'))
            return

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            count = 0
            for row in reader:
                # 1. Создаем Вопрос (RU, KK, EN)
                question = Question.objects.create(
                    test=main_test,
                    text_ru=row['text_ru'],
                    text_kk=row['text_kk'],
                    text_en=row['text_en'], # Английский
                    category=row['category'],
                    exposure_time=int(row['exposure_time']),
                    answer_time=int(row['answer_time']),
                    order=count + 1
                )

                # 2. Картинка
                img_name = row['image_filename'].strip()
                if img_name:
                    source_path = os.path.join(source_images_dir, img_name)
                    if os.path.exists(source_path):
                        target_path = os.path.join(target_images_dir, img_name)
                        shutil.copy(source_path, target_path)
                        question.image = f'questions/{img_name}'
                        question.save()

                # 3. Ответы
                # Правильный
                Answer.objects.create(
                    question=question, 
                    text_ru=row['correct_answer_ru'], 
                    text_kk=row['correct_answer_kk'], 
                    text_en=row['correct_answer_en'], 
                    is_correct=True
                )
                
                # Неправильные (1, 2, 3)
                for i in range(1, 4):
                    ru = row.get(f'wrong_{i}_ru')
                    kk = row.get(f'wrong_{i}_kk')
                    en = row.get(f'wrong_{i}_en')
                    
                    if ru: # Если ответ существует
                        Answer.objects.create(
                            question=question, 
                            text_ru=ru, 
                            text_kk=kk, 
                            text_en=en, 
                            is_correct=False
                        )
                
                count += 1
                self.stdout.write(f'Добавлен: {question.text_en[:20]}...')

        self.stdout.write(self.style.SUCCESS(f'Импорт завершен! Добавлено вопросов: {count}'))
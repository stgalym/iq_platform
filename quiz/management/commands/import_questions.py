import csv
import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from quiz.models import Test, Question, Answer

class Command(BaseCommand):
    help = 'Импорт вопросов из CSV файла с разделителем точка-запятая'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')

    def handle(self, *args, **kwargs):
        csv_path = kwargs['csv_file']
        
        # 1. Создаем "Контейнер" - Общий Тест
        # Если тест с таким названием уже есть, скрипт просто возьмет его (get_or_create)
        main_test, created = Test.objects.get_or_create(
            title="Полный IQ Тест (Стандарт)",
            defaults={
                'description': 'Комплексная проверка интеллекта: Логика, Математика, Память, Пространство. 96 вопросов.',
                'questions_count': 96,
                'time_limit': 60 # 60 минут на весь тест
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Создан новый тест: "{main_test.title}"'))
        else:
            self.stdout.write(self.style.WARNING(f'Добавляем вопросы в существующий тест: "{main_test.title}"'))

        # Папка, откуда будем брать картинки для импорта
        # Ты должен положить картинки в папку media/import_images/
        source_images_dir = os.path.join(settings.MEDIA_ROOT, 'import_images')

        # Папка, куда Django сохраняет картинки вопросов (целевая)
        target_images_dir = os.path.join(settings.MEDIA_ROOT, 'questions')
        if not os.path.exists(target_images_dir):
            os.makedirs(target_images_dir)

        # Проверка наличия CSV файла
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'Файл {csv_path} не найден!'))
            return

        # ЧТЕНИЕ ФАЙЛА
        with open(csv_path, 'r', encoding='utf-8') as f:
            # ВАЖНО: delimiter=';' указывает, что разделитель - точка с запятой
            reader = csv.DictReader(f, delimiter=';')
            
            count = 0
            for row in reader:
                # 2. Создаем Вопрос
                question = Question.objects.create(
                    test=main_test,
                    text=row['text'],
                    category=row['category'],
                    exposure_time=int(row['exposure_time']),
                    answer_time=int(row['answer_time']),
                    order=count + 1
                )

                # 3. Обработка Картинки
                img_name = row['image_filename'].strip() # strip убирает случайные пробелы
                if img_name:
                    source_path = os.path.join(source_images_dir, img_name)
                    
                    if os.path.exists(source_path):
                        # Копируем файл из папки импорта в папку вопросов
                        target_path = os.path.join(target_images_dir, img_name)
                        shutil.copy(source_path, target_path)
                        
                        # Привязываем к модели (путь относительно MEDIA_ROOT)
                        question.image = f'questions/{img_name}'
                        question.save()
                    else:
                        self.stdout.write(self.style.WARNING(f'Внимание: Картинка {img_name} не найдена в {source_images_dir}'))

                # 4. Создаем Ответы
                # Правильный ответ
                Answer.objects.create(question=question, text=row['correct_answer'], is_correct=True)
                
                # Неправильные ответы (проверяем, чтобы не были пустыми)
                if row['wrong_1']:
                    Answer.objects.create(question=question, text=row['wrong_1'], is_correct=False)
                if row['wrong_2']:
                    Answer.objects.create(question=question, text=row['wrong_2'], is_correct=False)
                if row['wrong_3']:
                    Answer.objects.create(question=question, text=row['wrong_3'], is_correct=False)
                
                count += 1
                self.stdout.write(f'Добавлен вопрос [{row["category"]}]: {question.text[:30]}...')

        self.stdout.write(self.style.SUCCESS(f'Импорт завершен! Всего добавлено вопросов: {count}'))
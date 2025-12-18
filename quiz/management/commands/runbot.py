from django.core.management.base import BaseCommand
import os
import requests

class Command(BaseCommand):
    help = 'Установка Webhook для Telegram бота'

    def handle(self, *args, **kwargs):
        token = os.getenv('TELEGRAM_TOKEN')
        # Вставь сюда свой домен на Render БЕЗ слеша в конце
        # Например: https://my-project.onrender.com
        # Или лучше брать из переменной окружения
        domain = os.getenv('RENDER_EXTERNAL_HOSTNAME') 
        
        if not domain:
            self.stdout.write(self.style.ERROR('Не найдена переменная RENDER_EXTERNAL_HOSTNAME или домен!'))
            return

        # Если домен пришел от Render, он обычно без https://
        if not domain.startswith('http'):
            domain = f'https://{domain}'

        url = f"{domain}/webhook/telegram/"
        
        # Запрос к API Telegram
        response = requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={url}")
        
        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS(f'Webhook успешно установлен на: {url}'))
            self.stdout.write(f"Ответ Telegram: {response.text}")
        else:
            self.stdout.write(self.style.ERROR(f'Ошибка установки: {response.text}'))
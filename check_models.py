import os
import google.generativeai as genai
from dotenv import load_dotenv

# Загружаем ключ
load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')

if not api_key:
    print("ОШИБКА: Ключ не найден в .env файле!")
else:
    genai.configure(api_key=api_key)
    print("Подключаемся к Google... Список доступных моделей:")
    print("-" * 30)
    
    try:
        found = False
        for m in genai.list_models():
            # Нам нужны только модели, умеющие генерировать текст (generateContent)
            if 'generateContent' in m.supported_generation_methods:
                print(f"Имя: {m.name}")
                found = True
        
        if not found:
            print("Модели не найдены. Возможно, проблема с регионом или ключом.")
            
    except Exception as e:
        print(f"Критическая ошибка: {e}")
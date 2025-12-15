import os
import google.generativeai as genai

def generate_iq_report(user_name, category_stats, total_score, language='ru'):
    """
    Генерирует отчет на выбранном языке (RU, KK, EN).
    """
    
    # --- 1. НАСТРОЙКИ ЯЗЫКОВ (Промпты и Локальные тексты) ---
    
    # Словари с заготовками для локального отчета (если ИИ недоступен)
    local_texts = {
        'ru': {
            'greeting': f"Уважаемый(а) {user_name}!",
            'score': f"Ваш результат: {total_score} баллов.",
            'high': "Это выдающийся результат! Вы демонстрируете высокие аналитические способности.",
            'mid': "Это хороший результат, выше среднего.",
            'low': "Результат требует улучшения. Рекомендуем больше тренироваться.",
            'strength': "Ваша сильная сторона:"
        },
        'kk': {
            'greeting': f"Құрметті {user_name}!",
            'score': f"Сіздің нәтижеңіз: {total_score} ұпай.",
            'high': "Бұл өте жақсы нәтиже! Сіз жоғары талдау қабілеттерін көрсеттіңіз.",
            'mid': "Бұл жақсы нәтиже, орташа деңгейден жоғары.",
            'low': "Нәтижені жақсарту қажет. Көбірек жаттығуды ұсынамыз.",
            'strength': "Сіздің күшті тұсыңыз:"
        },
        'en': {
            'greeting': f"Dear {user_name}!",
            'score': f"Your result: {total_score} points.",
            'high': "This is an outstanding result! You demonstrate high analytical skills.",
            'mid': "This is a good result, above average.",
            'low': "The result needs improvement. We recommend practicing more.",
            'strength': "Your strong side:"
        }
    }

    # Выбираем тексты для текущего языка (по умолчанию ru)
    t = local_texts.get(language, local_texts['ru'])

    # Формируем локальный отчет
    best_cat = "N/A"
    if category_stats:
        best_cat = max(category_stats, key=category_stats.get)
        
    local_report = f"{t['greeting']}\n\n{t['score']} "
    
    if total_score >= 80: # Условная шкала
        local_report += t['high']
    elif total_score >= 40:
        local_report += t['mid']
    else:
        local_report += t['low']

    local_report += f"\n{t['strength']} {best_cat}."


    # --- 2. ПРОБУЕМ ИСПОЛЬЗОВАТЬ ИИ ---
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        return local_report

    try:
        genai.configure(api_key=api_key)
        # Используем стабильную модель
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Формируем промпт в зависимости от языка
        if language == 'kk':
            prompt = (
                f"Пайдаланушы {user_name} IQ тестін тапсырды. "
                f"Жалпы ұпай: {total_score}. "
                f"Санаттар бойынша статистика: {category_stats}. "
                f"Қысқаша психологиялық портрет жазыңыз (3-4 сөйлем), "
                f"күшті жақтарын атап өтіңіз және дамуға кеңес беріңіз. "
                f"Пайдаланушыға 'Сіз' деп сөйлеңіз. Жауапты тек Қазақ тілінде жазыңыз."
            )
        elif language == 'en':
            prompt = (
                f"User {user_name} passed an IQ test. "
                f"Total score: {total_score}. "
                f"Category stats: {category_stats}. "
                f"Write a brief psychological profile (3-4 sentences), "
                f"highlight strengths and provide recommendations. "
                f"Address the user formally. Write the response in English only."
            )
        else: # RU
            prompt = (
                f"Проанализируй результаты IQ теста пользователя {user_name}. "
                f"Общий балл: {total_score}. "
                f"Статистика по категориям: {category_stats}. "
                f"Напиши краткий психологический портрет (3-4 предложения), "
                f"выдели сильные стороны и дай рекомендацию. "
                f"Обращайся на 'Вы'. Ответ пиши на русском языке."
            )

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"⚠️ Ошибка Gemini: {e}")
        return local_report
import os
import google.generativeai as genai
from django.conf import settings

def generate_test_report(user_name, category_stats, total_score, test_type='iq', language='ru'):
    """
    Генерирует отчет в зависимости от типа теста (IQ или Psychology).
    test_type: 'iq' или 'psychology'
    """
    
    # --- 1. ЗАГОТОВКИ НА СЛУЧАЙ ОШИБКИ ИИ (Fallback) ---
    local_texts = {
        'iq': {
            'ru': f"Уважаемый(а) {user_name}! Ваш результат: {total_score}. Это показатель ваших аналитических способностей.",
            'kk': f"Құрметті {user_name}! Сіздің нәтижеңіз: {total_score}. Бұл сіздің талдау қабілеттеріңіздің көрсеткіші.",
            'en': f"Dear {user_name}! Your score: {total_score}. This indicates your analytical abilities."
        },
        'psychology': {
            'ru': f"Уважаемый(а) {user_name}! Вы набрали {total_score} баллов. Это отражает ваш уровень эмоционального интеллекта и навыков принятия решений.",
            'kk': f"Құрметті {user_name}! Сіз {total_score} ұпай жинадыңыз. Бұл сіздің эмоционалдық зияткерлік деңгейіңізді көрсетеді.",
            'en': f"Dear {user_name}! You scored {total_score}. This reflects your emotional intelligence and decision-making skills."
        }
    }

    # Выбираем заглушку по умолчанию
    fallback_text = local_texts.get(test_type, local_texts['iq']).get(language, local_texts['iq']['ru'])

    api_key = getattr(settings, "GOOGLE_API_KEY", None)
    if not api_key:
        return fallback_text

    genai.configure(api_key=api_key)
    
    # Выбираем модель (пробуем по очереди)
    model = None
    for m_name in ['gemini-1.5-flash', 'gemini-pro']:
        try:
            model = genai.GenerativeModel(m_name)
            break
        except:
            continue
            
    if not model:
        return fallback_text

    # --- 2. ФОРМИРОВАНИЕ ПРОМПТА (ЗАПРОСА К ИИ) ---
    
    # >> ЛОГИКА ДЛЯ ПСИХОЛОГИИ <<
    if test_type == 'psychology':
        if language == 'kk':
            prompt = (
                f"Пайдаланушы {user_name} Психологиялық/Soft Skills тестін тапсырды. "
                f"Жалпы ұпай: {total_score} (бұл жағдаяттық сұрақтарға дұрыс жауаптар саны). "
                f"Санаттар бойынша: {category_stats}. "
                f"Пайдаланушының психологиялық портретін жасаңыз. "
                f"Оның ұжымдағы мінез-құлқына, эмпатиясына және шешім қабылдау дағдыларына баға беріңіз. "
                f"Жауапты 'Сіз' деп сыпайы түрде, тек Қазақ тілінде жазыңыз."
            )
        elif language == 'en':
            prompt = (
                f"User {user_name} passed a Psychology/Soft Skills test. "
                f"Total score: {total_score} (correct answers to situational questions). "
                f"Categories: {category_stats}. "
                f"Create a psychological profile. Assess their behavior in a team, empathy, and decision-making skills. "
                f"Highlight leadership potential if the score is high. "
                f"Address the user formally. Write in English only."
            )
        else: # RU
            prompt = (
                f"Проанализируй результаты психологического теста (Soft Skills) пользователя {user_name}. "
                f"Общий балл: {total_score} (это количество правильных решений в ситуационных кейсах). "
                f"Категории: {category_stats}. "
                f"Составь краткий психологический портрет (3-4 предложения). "
                f"Оцени навыки коммуникации, стрессоустойчивость и умение работать в команде. "
                f"Не используй термины 'высокий IQ'. Фокусируйся на личности и поведении. "
                f"Обращайся на 'Вы'. Ответ пиши на русском языке."
            )

    # >> ЛОГИКА ДЛЯ IQ (Оставляем как было) <<
    else:
        if language == 'kk':
            prompt = (
                f"Пайдаланушы {user_name} IQ тестін тапсырды. "
                f"Жалпы ұпай: {total_score}. Санаттар: {category_stats}. "
                f"Қысқаша портрет жазыңыз, күшті жақтарын атап өтіңіз (логика, математика). "
                f"Жауап тек Қазақ тілінде."
            )
        elif language == 'en':
            prompt = (
                f"User {user_name} passed an IQ test. Score: {total_score}. Stats: {category_stats}. "
                f"Write a brief analytical profile highlighting logic and math skills. "
                f"Write in English only."
            )
        else: # RU
            prompt = (
                f"Проанализируй результаты IQ теста пользователя {user_name}. "
                f"Общий балл: {total_score}. Категории: {category_stats}. "
                f"Напиши краткий портрет, выдели сильные стороны (логика, анализ). "
                f"Дай рекомендацию по развитию. Ответ на русском языке."
            )

    # --- 3. ГЕНЕРАЦИЯ ---
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return fallback_text
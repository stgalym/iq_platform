import os
import google.generativeai as genai
from django.conf import settings

def generate_test_report(user_name, category_stats, total_score, test_type='iq', language='ru', detailed_answers=None, total_questions=0):
    """
    Генерирует отчет в зависимости от типа теста (IQ или Psychology).
    test_type: 'iq' или 'psychology'
    detailed_answers: список словарей с детальной информацией об ответах (для психологических тестов)
    total_questions: общее количество вопросов
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

    # Пробуем получить API ключ из разных источников
    api_key = getattr(settings, "GOOGLE_API_KEY", None) or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("⚠️ WARNING: GOOGLE_API_KEY not found, using fallback text")
        return fallback_text
    
    print(f"🔑 API Key found, generating report for {test_type} test...")

    genai.configure(api_key=api_key)
    
    # Выбираем модель (пробуем по очереди)
    model = None
    for m_name in ['gemini-2.5-flash', 'gemini-pro']:
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
        # Формируем детальную информацию об ответах для анализа
        answers_context = ""
        if detailed_answers:
            # Выбираем заголовки в зависимости от языка
            headers = {
                'ru': {
                    'title': 'Детальные ответы кандидата:',
                    'question': 'Вопрос:',
                    'selected': 'Выбранный ответ:',
                    'correct': 'Правильный ответ:',
                    'result_ok': '✓ Правильно',
                    'result_fail': '✗ Неправильно'
                },
                'kk': {
                    'title': 'Кандидаттың толық жауаптары:',
                    'question': 'Сұрақ:',
                    'selected': 'Таңдалған жауап:',
                    'correct': 'Дұрыс жауап:',
                    'result_ok': '✓ Дұрыс',
                    'result_fail': '✗ Дұрыс емес'
                },
                'en': {
                    'title': 'Detailed candidate answers:',
                    'question': 'Question:',
                    'selected': 'Selected answer:',
                    'correct': 'Correct answer:',
                    'result_ok': '✓ Correct',
                    'result_fail': '✗ Incorrect'
                }
            }
            h = headers.get(language, headers['ru'])
            
            answers_context = f"\n\n{h['title']}\n"
            for idx, answer_data in enumerate(detailed_answers, 1):
                answers_context += f"\n{idx}. {h['question']} {answer_data['question_text']}\n"
                answers_context += f"   {h['selected']} {answer_data['selected_answer_text']}\n"
                answers_context += f"   {h['correct']} {answer_data['correct_answer_text']}\n"
                result_text = h['result_ok'] if answer_data['is_correct'] else h['result_fail']
                # Используем правильный язык для "Результат"
                result_label = {'ru': 'Результат:', 'kk': 'Нәтиже:', 'en': 'Result:'}.get(language, 'Результат:')
                answers_context += f"   {result_label} {result_text}\n"
        
        if language == 'kk':
            prompt = (
                f"Пайдаланушы {user_name} Психологиялық/Soft Skills тестін тапсырды. "
                f"Жалпы ұпай: {total_score} / {total_questions} (бұл жағдаяттық сұрақтарға дұрыс жауаптар саны). "
                f"{answers_context}\n\n"
                f"РЕКРУТЕРГЕ АРНАЛҒАН ДЕТАЛДЫ ЕСЕП ҚҰРАСТЫРЫҢЫЗ:\n"
                f"1. Психологиялық портрет: ұжымдағы мінез-құлқы, эмпатия, шешім қабылдау дағдылары\n"
                f"2. Күшті жақтары: кандидаттың ең жақсы көрсеткіштері\n"
                f"3. Әлсіз жақтары: дамытуға қажетті салалар\n"
                f"4. Жұмысқа қабылдау ұсынысы: 'Ұсынылады', 'Шартты түрде ұсынылады' немесе 'Ұсынылмайды' "
                f"және негіздемесі\n"
                f"5. Қандай лауазымға/командаға сәйкес келетіні\n"
                f"Жауапты Қазақ тілінде, рекрутерге арналған формальды стильде жазыңыз."
            )
        elif language == 'en':
            prompt = (
                f"User {user_name} passed a Psychology/Soft Skills test. "
                f"Total score: {total_score} / {total_questions} (correct answers to situational questions). "
                f"{answers_context}\n\n"
                f"CREATE A DETAILED REPORT FOR THE RECRUITER:\n"
                f"1. Psychological profile: behavior in team, empathy, decision-making skills\n"
                f"2. Strengths: candidate's best indicators\n"
                f"3. Weaknesses: areas that need development\n"
                f"4. Hiring recommendation: 'Recommended', 'Conditionally recommended', or 'Not recommended' with justification\n"
                f"5. What position/team would be suitable\n"
                f"Write in English, in a formal style for the recruiter."
            )
        else: # RU
            prompt = (
                f"Проанализируй результаты психологического теста (Soft Skills) кандидата {user_name}. "
                f"Общий балл: {total_score} / {total_questions} (количество правильных решений в ситуационных кейсах). "
                f"{answers_context}\n\n"
                f"СОСТАВЬ ДЕТАЛЬНЫЙ ОТЧЕТ ДЛЯ РЕКРУТЕРА:\n"
                f"1. Психологический портрет: поведение в команде, эмпатия, навыки принятия решений, стрессоустойчивость, этичность\n"
                f"2. Сильные стороны: лучшие показатели кандидата\n"
                f"3. Слабые стороны: области, требующие развития\n"
                f"4. Рекомендация по найму: 'Рекомендуется', 'Условно рекомендуется' или 'Не рекомендуется' с обоснованием\n"
                f"5. На какую должность/в какую команду подходит\n"
                f"6. Конкретные примеры из ответов, которые подтверждают выводы\n\n"
                f"Ответ должен быть структурированным, профессиональным и полезным для принятия решения о найме. "
                f"Пиши на русском языке, обращайся к рекрутеру формально."
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
        print(f"📝 Prompt length: {len(prompt)} characters")
        print(f"📝 Prompt preview (first 200 chars): {prompt[:200]}...")
        response = model.generate_content(prompt)
        result_text = response.text
        print(f"✅ AI Response received, length: {len(result_text)} characters")
        return result_text
    except Exception as e:
        print(f"❌ AI Generation Error: {e}")
        import traceback
        traceback.print_exc()
        return fallback_text
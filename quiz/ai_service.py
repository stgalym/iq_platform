import os
import google.generativeai as genai
from django.conf import settings

def generate_test_report(user_name, category_stats, total_score, test_type='iq', language='ru', detailed_answers=None, total_questions=0, analysis_for='user'):
    """
    Генерирует отчет в зависимости от типа теста (IQ или Psychology) и для кого анализ.
    test_type: 'iq' или 'psychology'
    detailed_answers: список словарей с детальной информацией об ответах (для психологических тестов)
    total_questions: общее количество вопросов
    analysis_for: 'recruiter' (для рекрутера - оценка кандидата) или 'user' (для пользователя - самопознание)
    """
    
    # --- 1. ЗАГОТОВКИ НА СЛУЧАЙ ОШИБКИ ИИ (Fallback) ---
    local_texts = {
        'iq': {
            'ru': f"Уважаемый(а) {user_name}! Ваш результат: {total_score}. Это показатель ваших аналитических способностей.",
            'kk': f"Құрметті {user_name}! Сіздің нәтижеңіз: {total_score}. Бұл сіздің талдау қабілеттеріңіздің көрсеткіші.",
            'en': f"Dear {user_name}! Your score: {total_score}. This indicates your analytical abilities."
        },
        'psychology': {
            'ru': {
                'user': f"Уважаемый(а) {user_name}! Вы набрали {total_score} баллов из {total_questions}. Это отражает ваш уровень эмоционального интеллекта и навыков принятия решений.",
                'recruiter': f"Кандидат {user_name} набрал {total_score} баллов из {total_questions}. Требуется детальный анализ для оценки пригодности."
            },
            'kk': {
                'user': f"Құрметті {user_name}! Сіз {total_questions} ішінен {total_score} ұпай жинадыңыз. Бұл сіздің эмоционалдық зияткерлік деңгейіңізді көрсетеді.",
                'recruiter': f"Үміткер {user_name} {total_questions} ішінен {total_score} ұпай жинады. Бағалау үшін деталды талдау қажет."
            },
            'en': {
                'user': f"Dear {user_name}! You scored {total_score} out of {total_questions}. This reflects your emotional intelligence and decision-making skills.",
                'recruiter': f"Candidate {user_name} scored {total_score} out of {total_questions}. Detailed analysis required for assessment."
            }
        }
    }

    # Выбираем заглушку по умолчанию
    if test_type == 'psychology':
        fallback_text = local_texts['psychology'].get(language, local_texts['psychology']['ru']).get(analysis_for, local_texts['psychology']['ru']['user'])
    else:
        fallback_text = local_texts.get(test_type, local_texts['iq']).get(language, local_texts['iq']['ru'])

    # Пробуем получить API ключ из разных источников
    api_key = getattr(settings, "GOOGLE_API_KEY", None) or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        try:
            print(f"[WARNING] GOOGLE_API_KEY not found, using fallback text. test_type={test_type}, analysis_for={analysis_for}")
        except UnicodeEncodeError:
            print(f"[WARNING] GOOGLE_API_KEY not found, using fallback text")
        return fallback_text
    
    try:
        print(f"[OK] API Key found (length: {len(api_key)}), generating report for {test_type} test, analysis_for={analysis_for}")
    except UnicodeEncodeError:
        print(f"[OK] API Key found, generating report for {test_type} test")

    genai.configure(api_key=api_key)
    
    # Выбираем модель (пробуем по очереди доступные модели)
    model = None
    model_names = [
        'gemini-2.5-flash',         # Рекомендуемая модель
        'gemini-1.5-flash',         # Стабильная версия flash
        'gemini-1.5-pro',            # Стабильная версия pro
        'gemini-pro',                # Стабильная версия pro (старое имя)
        'gemini-1.0-pro',           # Альтернатива
    ]
    
    last_error = None
    for m_name in model_names:
        try:
            try:
                print(f"[INFO] Trying model: {m_name}")
            except UnicodeEncodeError:
                print(f"[INFO] Trying model: {m_name}")
            model = genai.GenerativeModel(m_name)
            # Проверяем, что модель доступна, делая тестовый запрос (необязательно, но полезно)
            try:
                print(f"[OK] Model {m_name} initialized successfully")
            except UnicodeEncodeError:
                print(f"[OK] Model {m_name} initialized")
            break
        except Exception as e:
            last_error = str(e)
            try:
                print(f"[WARNING] Model {m_name} failed: {str(e)[:150]}")
            except UnicodeEncodeError:
                print(f"[WARNING] Model {m_name} failed")
            continue
            
    if not model:
        try:
            print(f"[ERROR] No available models found. Last error: {last_error[:200] if last_error else 'Unknown'}")
            print("[INFO] Trying to list available models...")
            try:
                available_models = [m.name for m in genai.list_models() 
                                  if 'generateContent' in m.supported_generation_methods]
                print(f"[INFO] Available models: {available_models[:5]}")  # Показываем первые 5
                if available_models:
                    # Пробуем использовать первую доступную модель
                    model_name = available_models[0].split('/')[-1]
                    print(f"[INFO] Trying first available model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    print(f"[OK] Using model: {model_name}")
            except Exception as list_error:
                print(f"[ERROR] Could not list models: {str(list_error)[:150]}")
        except UnicodeEncodeError:
            print("[ERROR] No available models found")
        
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
        
        # Разные промпты для рекрутера и пользователя
        if analysis_for == 'recruiter':
            # ПРОМПТ ДЛЯ РЕКРУТЕРА (оценка кандидата)
            if language == 'kk':
                prompt = (
                    f"Үміткер {user_name} Психологиялық/Soft Skills тестін тапсырды. "
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
                    f"Candidate {user_name} passed a Psychology/Soft Skills test. "
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
        else:
            # ПРОМПТ ДЛЯ ПОЛЬЗОВАТЕЛЯ (самопознание и рекомендации)
            if language == 'kk':
                prompt = (
                    f"Сіз {user_name} Психологиялық/Soft Skills тестін тапсырдыңыз. "
                    f"Жалпы ұпай: {total_score} / {total_questions} (бұл жағдаяттық сұрақтарға дұрыс жауаптар саны). "
                    f"{answers_context}\n\n"
                    f"СІЗГЕ АРНАЛҒАН ЖЕКЕ ТАЛДАУ ЖАСАҢЫЗ:\n"
                    f"1. Психологиялық портрет: сіздің мінез-құлқыңыз, эмпатия, шешім қабылдау дағдыларыңыз\n"
                    f"2. Күшті жақтарыңыз: сіздің ең жақсы қасиеттеріңіз\n"
                    f"3. Дамытуға қажетті салалар: қай жерде өсу керек\n"
                    f"4. Жеке даму ұсыныстары: қалай жақсартуға болады\n"
                    f"5. Сізге сәйкес келетін жұмыс түрлері/командалар\n"
                    f"Жауапты Қазақ тілінде, сізге арналған қолдау көрсететін стильде жазыңыз. 'Сіз' деп сыпайы түрде."
                )
            elif language == 'en':
                prompt = (
                    f"You {user_name} passed a Psychology/Soft Skills test. "
                    f"Total score: {total_score} / {total_questions} (correct answers to situational questions). "
                    f"{answers_context}\n\n"
                    f"CREATE A PERSONAL ANALYSIS FOR YOU:\n"
                    f"1. Psychological profile: your behavior, empathy, decision-making skills\n"
                    f"2. Your strengths: your best qualities\n"
                    f"3. Areas for development: where you can grow\n"
                    f"4. Personal development recommendations: how to improve\n"
                    f"5. Types of work/teams that would suit you\n"
                    f"Write in English, in a supportive and encouraging style. Address the user as 'You'."
                )
            else: # RU
                prompt = (
                    f"Вы {user_name} прошли психологический тест (Soft Skills). "
                    f"Общий балл: {total_score} / {total_questions} (количество правильных решений в ситуационных кейсах). "
                    f"{answers_context}\n\n"
                    f"СОСТАВЬ ЛИЧНЫЙ АНАЛИЗ ДЛЯ ВАС:\n"
                    f"1. Психологический портрет: ваше поведение в команде, эмпатия, навыки принятия решений, стрессоустойчивость\n"
                    f"2. Ваши сильные стороны: ваши лучшие качества\n"
                    f"3. Области для развития: где можно улучшиться\n"
                    f"4. Рекомендации по личностному развитию: как стать лучше\n"
                    f"5. Какие типы работы/команды вам подходят\n"
                    f"6. Конкретные примеры из ваших ответов и что они говорят о вас\n\n"
                    f"Ответ должен быть поддерживающим, мотивирующим и полезным для самопознания. "
                    f"Пиши на русском языке, обращайся к пользователю на 'Вы' в дружелюбном тоне."
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
        if not model:
            print("[ERROR] Model is None, cannot generate content")
            return fallback_text
            
        try:
            print(f"[INFO] Prompt length: {len(prompt)} characters")
            print(f"[INFO] Prompt preview (first 200 chars): {prompt[:200]}...")
        except UnicodeEncodeError:
            print(f"[INFO] Prompt length: {len(prompt)} characters")
        
        response = model.generate_content(prompt)
        
        if not response or not hasattr(response, 'text'):
            print("[ERROR] Invalid response from model")
            return fallback_text
            
        result_text = response.text
        
        if not result_text or len(result_text.strip()) == 0:
            print("[WARNING] Empty response from AI, using fallback")
            return fallback_text
            
        try:
            print(f"[OK] AI Response received, length: {len(result_text)} characters")
        except UnicodeEncodeError:
            print(f"[OK] AI Response received, length: {len(result_text)} characters")
        return result_text
    except Exception as e:
        try:
            print(f"[ERROR] AI Generation Error: {type(e).__name__}: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
        except UnicodeEncodeError:
            print(f"[ERROR] AI Generation Error occurred")
        return fallback_text
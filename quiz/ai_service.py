import os
# import openai # Раскомментируйте, когда добавите ключ в .env

def generate_iq_report(user_name, category_stats, total_score):
    # Заглушка, пока нет API ключа. Работает локально.
    text = f"Здравствуйте, {user_name}!\n\n"
    
    if total_score == 0:
        text += "К сожалению, вы не дали правильных ответов. Стоит попробовать еще раз."
    elif total_score > 5:
        text += "У вас отличные показатели! "
    else:
        text += "Неплохой результат, но есть куда расти. "

    if category_stats:
        best_cat = max(category_stats, key=category_stats.get)
        text += f"\nВаша сильная сторона: {best_cat}."
    
    text += "\n\n(Чтобы здесь появился настоящий анализ от ChatGPT, нужно добавить API ключ)."
    return text
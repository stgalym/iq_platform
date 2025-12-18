# quiz/telegram_bot.py
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
from asgiref.sync import sync_to_async
from users.models import CustomUser
from quiz.models import Question, Answer, BotResult

# Инициализация
TOKEN = os.getenv('TELEGRAM_TOKEN')
# ВАЖНО: для вебхука убираем таймауты или делаем их дефолтными
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СЛОВАРЬ ПЕРЕВОДОВ ДЛЯ БОТА ---
MESSAGES = {
    'ru': {
        'welcome': "✅ <b>{name}</b>, вы подключены!\nНажмите /train чтобы начать.",
        'error_code': "❌ Ошибка. Код не найден.",
        'hello': "Привет! Напишите /start ВАШ_КОД",
        'limit': "🚫 Лимит на сегодня исчерпан! Купите Premium на сайте.",
        'no_questions': "В этой категории нет вопросов.",
        'correct': "✅ Правильно!",
        'wrong': "❌ Ошибка.",
        'next': "Следующий вопрос ➡️",
        'caption': "<b>Вопрос:</b>\n{text}"
    },
    'kk': {
        'welcome': "✅ <b>{name}</b>, қосылдыңыз!\nБастау үшін /train басыңыз.",
        'error_code': "❌ Қате. Код табылмады.",
        'hello': "Сәлем! /start СІЗДІҢ_КОДЫҢЫЗ жазыңыз",
        'limit': "🚫 Бүгінгі лимит таусылды! Сайттан Premium сатып алыңыз.",
        'no_questions': "Бұл санатта сұрақтар жоқ.",
        'correct': "✅ Дұрыс!",
        'wrong': "❌ Қате.",
        'next': "Келесі сұрақ ➡️",
        'caption': "<b>Сұрақ:</b>\n{text}"
    },
     'en': {
        'welcome': "✅ <b>{name}</b>, connected!\nPress /train to start.",
        'error_code': "❌ Error. Code not found.",
        'hello': "Hi! Type /start YOUR_CODE",
        'limit': "🚫 Daily limit reached! Buy Premium on website.",
        'no_questions': "No questions in this category.",
        'correct': "✅ Correct!",
        'wrong': "❌ Wrong.",
        'next': "Next question ➡️",
        'caption': "<b>Question:</b>\n{text}"
    }
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
@sync_to_async
def get_user_lang(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        return user.language if user.language else 'ru'
    except CustomUser.DoesNotExist:
        return 'ru'

@sync_to_async
def register_user(code, chat_id, username):
    try:
        user = CustomUser.objects.get(telegram_code=code)
        user.telegram_chat_id = str(chat_id)
        user.save()
        return user
    except CustomUser.DoesNotExist:
        return None

@sync_to_async
def get_random_question(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        # Проверка лимитов (упрощено, добавь логику проверки премиума если нужно)
        # if not user.is_premium and user.today_questions > 10: return None
        
        category = user.bot_category
        # Выбираем вопросы, на которые пользователь еще не отвечал
        answered_ids = BotResult.objects.filter(user=user).values_list('question_id', flat=True)
        questions = Question.objects.filter(category=category).exclude(id__in=answered_ids)
        
        if not questions.exists():
            # Если ответил на всё, можно сбросить историю или вернуть None
            # Для примера берем любой случайный, если закончились новые
            questions = Question.objects.filter(category=category)
            if not questions.exists():
                return None
                
        return random.choice(list(questions))
    except CustomUser.DoesNotExist:
        return None

@sync_to_async
def save_result(chat_id, answer_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        answer = Answer.objects.get(id=answer_id)
        
        BotResult.objects.create(
            user=user,
            question=answer.question,
            is_correct=answer.is_correct
        )
        return answer.is_correct
    except Exception:
        return False

# --- ХЕНДЛЕРЫ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    lang = await get_user_lang(message.chat.id)
    t = MESSAGES[lang]

    args = command.args
    if args:
        user = await register_user(args, message.chat.id, message.from_user.full_name)
        if user:
            # Обновляем язык, так как узнали пользователя
            lang = user.language if user.language else 'ru'
            msg = MESSAGES[lang]['welcome'].format(name=message.from_user.full_name)
            await message.answer(msg, parse_mode="HTML")
        else:
            await message.answer(t['error_code'])
    else:
        await message.answer(t['hello'])

async def send_question(message: types.Message):
    lang = await get_user_lang(message.chat.id)
    t = MESSAGES[lang]
    
    question = await get_random_question(message.chat.id)
    
    if not question:
        await message.answer(t['no_questions'])
        return

    # Формируем текст вопроса
    q_text = getattr(question, f'text_{lang}', question.text_ru)
    caption_text = t['caption'].format(text=q_text)

    # Клавиатура
    # Получаем ответы асинхронно
    answers = await sync_to_async(list)(question.answers.all())
    random.shuffle(answers)
    
    buttons = []
    for ans in answers:
        ans_text = getattr(ans, f'text_{lang}', ans.text_ru)
        buttons.append([InlineKeyboardButton(text=ans_text, callback_data=f"ans_{ans.id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        if question.image:
            # Важно: для отправки файлов лучше использовать ID файла если он уже загружен в ТГ, 
            # или URL, или FSInputFile. Здесь предполагаем, что question.image.path доступен.
            # На Render файловая система эфемерна, поэтому лучше проверять существование.
            try:
                photo_file = FSInputFile(question.image.path)
                await message.answer_photo(photo_file, caption=caption_text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                # Если картинки нет физически, шлем текст
                 await message.answer(caption_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(caption_text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        print(f"Error sending question: {e}")
        await message.answer("Error / Қате / Ошибка")

@dp.message(Command("train"))
async def cmd_train(message: types.Message):
    await send_question(message)

@dp.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.message.chat.id)
    t = MESSAGES[lang]

    ans_id = callback.data.split("_")[1]
    is_correct = await save_result(callback.message.chat.id, ans_id)

    # Ответ бота
    result_text = t['correct'] if is_correct else t['wrong']
    
    # Кнопка "Далее"
    next_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['next'], callback_data="next_q")]
    ])

    await callback.message.edit_reply_markup(reply_markup=None) # Убираем старые кнопки
    await callback.message.answer(result_text, reply_markup=next_kb)
    await callback.answer()

@dp.callback_query(F.data == "next_q")
async def process_next(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await send_question(callback.message)
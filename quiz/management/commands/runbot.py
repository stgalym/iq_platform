import asyncio
import os
import random
from django.core.management.base import BaseCommand
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command, CommandObject
from asgiref.sync import sync_to_async
from django.utils import timezone
from users.models import CustomUser
from quiz.models import Question, Answer, BotResult

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СЛОВАРЬ ПЕРЕВОДОВ ДЛЯ БОТА ---
# Чтобы сам бот отвечал на нужном языке
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
        'hello': "Сәлем! /start СІЗДІҢ_КОДЫҢЫЗ деп жазыңыз",
        'limit': "🚫 Бүгінгі лимит бітті! Сайтта Premium сатып алыңыз.",
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
        'limit': "🚫 Daily limit exceeded! Buy Premium on the website.",
        'no_questions': "No questions in this category.",
        'correct': "✅ Correct!",
        'wrong': "❌ Wrong.",
        'next': "Next question ➡️",
        'caption': "<b>Question:</b>\n{text}"
    }
}

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---

@sync_to_async
def get_user_lang(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        return user.language if user.language in MESSAGES else 'ru'
    except CustomUser.DoesNotExist:
        return 'ru'

@sync_to_async
def connect_user(code, chat_id):
    clean_code = str(code).strip()
    updated_count = CustomUser.objects.filter(telegram_code=clean_code).update(
        telegram_chat_id=str(chat_id),
        telegram_code=None
    )
    if updated_count > 0:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        return user.username, user.language
    return None, 'ru'

@sync_to_async
def get_random_question(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        # Фильтр по категории
        if user.bot_category:
            questions = Question.objects.filter(category=user.bot_category).order_by('?')
        else:
            questions = Question.objects.order_by('?')
            
        question = questions.first()
        if not question:
            return None, None

        answers = list(question.answers.all())
        random.shuffle(answers)
        return question, answers

    except CustomUser.DoesNotExist:
        return None, None

@sync_to_async
def check_limit(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        if user.is_premium:
            return True
        today_count = BotResult.objects.filter(
            user=user, created_at__date=timezone.now().date()
        ).count()
        return today_count < 3
    except CustomUser.DoesNotExist:
        return False

@sync_to_async
def save_result(chat_id, answer_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        answer = Answer.objects.get(id=int(answer_id))
        BotResult.objects.create(user=user, question=answer.question, is_correct=answer.is_correct)
        return answer.is_correct
    except:
        return False

# --- ЛОГИКА БОТА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    code = command.args
    if code:
        username, lang = await connect_user(code, message.chat.id)
        msg = MESSAGES.get(lang, MESSAGES['ru'])
        
        if username:
            await message.answer(msg['welcome'].format(name=username), parse_mode="HTML")
        else:
            await message.answer(msg['error_code'])
    else:
        # Язык пока не знаем, отвечаем на русском
        await message.answer(MESSAGES['ru']['hello'])

async def send_question(message: types.Message):
    lang = await get_user_lang(message.chat.id)
    t = MESSAGES[lang] # Словарь текстов для текущего языка

    # 1. Лимит
    if not await check_limit(message.chat.id):
        await message.answer(t['limit'])
        return

    # 2. Получаем вопрос (объект базы данных)
    question, answers = await get_random_question(message.chat.id)
    if not question:
        await message.answer(t['no_questions'])
        return

    # 3. Достаем тексты на нужном языке
    # Используем getattr, чтобы динамически взять поле text_ru, text_kk или text_en
    q_text = getattr(question, f'text_{lang}', question.text_ru)
    if not q_text: q_text = question.text_ru # Фолбэк на русский

    buttons = []
    for ans in answers:
        a_text = getattr(ans, f'text_{lang}', ans.text_ru)
        if not a_text: a_text = ans.text_ru
        
        buttons.append([InlineKeyboardButton(text=a_text, callback_data=f"ans_{ans.id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # 4. Отправка (с картинкой или без)
    try:
        caption_text = t['caption'].format(text=q_text)
        
        if question.image:
            photo = FSInputFile(question.image.path)
            await message.answer_photo(photo, caption=caption_text, reply_markup=keyboard, parse_mode="HTML")
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

class Command(BaseCommand):
    help = 'Запуск многоязычного бота'
    def handle(self, *args, **kwargs):
        print("Бот запущен (RU/KK/EN)...")
        asyncio.run(dp.start_polling(bot))
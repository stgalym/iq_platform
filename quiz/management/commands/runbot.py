import asyncio
import os
import random
from datetime import date
from django.core.management.base import BaseCommand
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

# Импорты моделей
from users.models import CustomUser
from quiz.models import Question, Answer, BotResult

TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---

@sync_to_async
def connect_user(code, chat_id):
    clean_code = str(code).strip()
    updated_count = CustomUser.objects.filter(telegram_code=clean_code).update(
        telegram_chat_id=str(chat_id),
        telegram_code=None
    )
    if updated_count > 0:
        return CustomUser.objects.get(telegram_chat_id=str(chat_id)).username
    return None

@sync_to_async
def get_random_question(chat_id):
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        user_category = user.bot_category
        
        # --- ОТЛАДКА (DEBUG) ---
        print(f"\n[DEBUG] Пользователь: {user.username}")
        print(f"[DEBUG] Выбранная категория (код): '{user_category}'")
        
        # Проверяем, сколько вопросов есть в этой категории
        count_in_cat = Question.objects.filter(category=user_category).count()
        print(f"[DEBUG] Вопросов в базе с такой категорией: {count_in_cat}")
        # -----------------------

        if user_category:
            # Ищем вопросы строго по категории
            questions = Question.objects.filter(category=user_category).order_by('?')
        else:
            questions = Question.objects.order_by('?')
            
        question = questions.first()
        
        if not question:
            print("[DEBUG] Вопрос не найден! Возвращаем None.")
            return None, None

        answers = list(question.answers.all())
        random.shuffle(answers)
        
        print(f"[DEBUG] Выбран вопрос: {question.text[:20]}... (Категория: {question.category})")
        return question, answers

    except CustomUser.DoesNotExist:
        print("[DEBUG] Ошибка: Пользователь не найден по chat_id")
        return None, None

@sync_to_async
def check_answer_and_save(chat_id, answer_id):
    # 1. Находим пользователя
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
    except CustomUser.DoesNotExist:
        return None, False

    # 2. Находим ответ и вопрос
    try:
        answer = Answer.objects.get(id=int(answer_id))
        question = answer.question
        is_correct = answer.is_correct
    except Answer.DoesNotExist:
        return None, False

    # 3. СОХРАНЯЕМ РЕЗУЛЬТАТ В БАЗУ
    BotResult.objects.create(
        user=user,
        question=question,
        is_correct=is_correct
    )
    
    return is_correct, True

@sync_to_async
def check_limit(chat_id):
    """
    Проверяем, можно ли пользователю решать задачи.
    Возвращает True, если МОЖНО.
    Возвращает False, если ЛИМИТ ИСЧЕРПАН.
    """
    try:
        user = CustomUser.objects.get(telegram_chat_id=str(chat_id))
        
        # Если Премиум - лимитов нет
        if user.is_premium:
            return True
            
        # Считаем, сколько задач он решил СЕГОДНЯ
        today_count = BotResult.objects.filter(
            user=user,
            created_at__date=timezone.now().date()
        ).count()
        
        # ЛИМИТ: Например, 3 задачи в день для бесплатного аккаунта
        if today_count >= 3:
            return False
            
        return True
        
    except CustomUser.DoesNotExist:
        return False

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    code = command.args
    if code:
        username = await connect_user(code, message.chat.id)
        if username:
            await message.answer(f"✅ <b>{username}</b> подключен!", parse_mode="HTML")
        else:
            await message.answer("❌ Неверный код.")
    else:
        await message.answer("Привет! Введите /start ВАШ_КОД")

# Функция отправки вопроса (вынесли отдельно, чтобы вызывать из разных мест)
async def send_question(message: types.Message):
    # 1. Проверяем лимит
    try:
        can_play = await check_limit(message.chat.id)
    except Exception as e:
        print(f"[DEBUG] Ошибка лимита: {e}")
        return

    if not can_play:
        site_url = "http://127.0.0.1:8000/users/premium/"
        await message.answer(f"Лимит исчерпан. <a href='{site_url}'>Купить Premium</a>", parse_mode="HTML")
        return

    # 2. Получаем вопрос
    try:
        question, answers = await get_random_question(message.chat.id)
    except Exception as e:
        print(f"[DEBUG] Ошибка поиска вопроса: {e}")
        return

    if not question:
        await message.answer("В вашей категории пока нет вопросов.")
        return

    # Проверка на наличие ответов
    if not answers:
        await message.answer(f"Ошибка: у вопроса '{question.text}' нет вариантов ответа.")
        return

    # 3. Формируем кнопки
    buttons = []
    for ans in answers:
        buttons.append([InlineKeyboardButton(text=ans.text, callback_data=f"ans_{ans.id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # 4. ОТПРАВКА (С КАРТИНКОЙ ИЛИ БЕЗ)
    print(f"[DEBUG] Отправляем вопрос: {question.text}")
    
    try:
        # Проверяем, есть ли картинка у вопроса
        if question.image:
            # Получаем полный путь к файлу на диске
            photo_path = question.image.path
            print(f"[DEBUG] Найдена картинка: {photo_path}")
            
            # Создаем объект файла для Телеграма
            photo_file = FSInputFile(photo_path)
            
            # Отправляем ФОТО + Текст (как подпись/caption)
            await message.answer_photo(
                photo=photo_file,
                caption=f"<b>Вопрос:</b>\n{question.text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Отправляем просто ТЕКСТ (по-старому)
            await message.answer(
                text=f"<b>Вопрос:</b>\n{question.text}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
        print("[DEBUG] ✅ Успешно отправлено")

    except Exception as e:
        print(f"[DEBUG] ❌ Ошибка отправки в Telegram: {e}")
        await message.answer("Не удалось отправить вопрос (ошибка формата).")
    
@dp.message(Command("train"))
async def cmd_train(message: types.Message):
    await send_question(message)

@dp.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: types.CallbackQuery):
    answer_id = callback.data.split("_")[1]
    
    # Проверяем и сохраняем в базу
    is_correct, user_found = await check_answer_and_save(callback.message.chat.id, answer_id)

    if not user_found:
        await callback.answer("Ошибка пользователя")
        return

    if is_correct:
        text = "✅ <b>Правильно!</b>"
    else:
        text = "❌ <b>Ошибка.</b>"

    # Убираем старую клавиатуру, чтобы не нажал дважды
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Кнопка "Следующий вопрос"
    next_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Следующий вопрос ➡️", callback_data="next_q")]
    ])

    await callback.message.answer(text, reply_markup=next_btn, parse_mode="HTML")
    await callback.answer()

# Обработчик кнопки "Следующий вопрос"
@dp.callback_query(F.data == "next_q")
async def process_next(callback: types.CallbackQuery):
    # Удаляем кнопку "Следующий", чтобы было красиво
    await callback.message.edit_reply_markup(reply_markup=None)
    # Отправляем новый вопрос
    await send_question(callback.message)

class Command(BaseCommand):
    help = 'Запуск бота'
    def handle(self, *args, **kwargs):
        print("Бот с лимитами запущен...")
        asyncio.run(dp.start_polling(bot))
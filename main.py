import asyncio
import logging
import random
import time
import aiosqlite

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# =========================
# CONFIG
# =========================

TOKEN = "8756367883:AAEJZdghN5Lz0B8R7O1P1NHC5jHya6i4pTA"
BOT_USERNAME = "tebepishut1_bot"
ADMIN_ID = 1691654877

# =========================
# INIT
# =========================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================
# STATES
# =========================

class ReplyState(StatesGroup):
    waiting_for_message = State()


class AdminState(StatesGroup):
    waiting_broadcast = State()
    waiting_ban = State()

# =========================
# DB
# =========================

async def init_db():

    async with aiosqlite.connect("db.sqlite3") as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrals INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            created_at INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER,
            to_user INTEGER,
            text TEXT,
            created_at INTEGER
        )
        """)

        await db.commit()

# =========================
# KEYBOARDS
# =========================

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📩 Моя ссылка")],
        [KeyboardButton(text="📬 Мои сообщения")],
        [KeyboardButton(text="👥 Пригласить")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="🔨 Бан")]
    ],
    resize_keyboard=True
)

# =========================
# HELPERS
# =========================

bad_words = [
    "лох",
    "дебил",
    "идиот",
    "сука",
    "блядь"
]

hints = [
    "👀 Возможно ты знаешь этого человека",
    "🤫 Кто-то думает о тебе",
    "💭 Вам есть что обсудить",
    "🔥 Сообщение отправлено анонимно"
]

async def add_user(user_id: int):

    async with aiosqlite.connect("db.sqlite3") as db:

        await db.execute("""
        INSERT OR IGNORE INTO users
        (user_id, created_at)
        VALUES (?, ?)
        """, (user_id, int(time.time())))

        await db.commit()

def contains_bad_words(text: str):

    text = text.lower()

    for word in bad_words:
        if word in text:
            return True

    return False

# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):

    await state.clear()

    user_id = message.from_user.id

    await add_user(user_id)

    args = message.text.split()

    # Обычный старт
    if len(args) == 1:

        await message.answer(
            "🤫 Добро пожаловать в ТебеПишут\n\n"
            "Получи свою анонимную ссылку 👇",
            reply_markup=menu
        )

        return

    # START С ID
    try:

        target_id = int(args[1])

    except:
        await message.answer("❌ Ошибка ссылки")
        return

    if target_id == user_id:
        await message.answer(
            "❌ Нельзя отправить сообщение самому себе",
            reply_markup=menu
        )
        return

    await state.update_data(target_id=target_id)
    await state.set_state(ReplyState.waiting_for_message)

    await message.answer(
        "✍️ Напиши анонимное сообщение"
    )

# =========================
# SEND MESSAGE
# =========================

@dp.message(ReplyState.waiting_for_message)
async def send_message(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()

    target_id = data.get("target_id")

    if not target_id:

        await message.answer("❌ Ошибка пользователя")

        await state.clear()

        return

    text = message.text

    if contains_bad_words(text):

        await message.answer("🚫 Сообщение содержит запрещённые слова")

        return

    async with aiosqlite.connect("db.sqlite3") as db:

        await db.execute("""
        INSERT INTO messages
        (from_user, to_user, text, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            message.from_user.id,
            target_id,
            text,
            int(time.time())
        ))

        await db.commit()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить",
                    callback_data=f"reply_{message.from_user.id}"
                )
            ]
        ]
    )

    hint = random.choice(hints)

    try:

        await bot.send_message(
            target_id,
            f"💌 Новое анонимное сообщение:\n\n"
            f"{text}\n\n"
            f"{hint}",
            reply_markup=keyboard
        )

    except:

        await message.answer("❌ Не удалось отправить")

        await state.clear()

        return

    await message.answer("✅ Сообщение отправлено")

    await state.clear()

# =========================
# REPLY
# =========================

@dp.callback_query(F.data.startswith("reply_"))
async def reply_callback(
    call: types.CallbackQuery,
    state: FSMContext
):

    target_id = int(call.data.split("_")[1])

    await state.update_data(target_id=target_id)
    await state.set_state(ReplyState.waiting_for_message)

    await call.message.answer("✍️ Напиши ответ")

# =========================
# LINK
# =========================

@dp.message(F.text == "📩 Моя ссылка")
async def my_link(message: types.Message):

    link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"

    await message.answer(
        f"🔗 Твоя ссылка:\n\n{link}"
    )

# =========================
# MY MESSAGES
# =========================

@dp.message(F.text == "📬 Мои сообщения")
async def my_messages(message: types.Message):

    async with aiosqlite.connect("db.sqlite3") as db:

        cursor = await db.execute("""
        SELECT text FROM messages
        WHERE to_user = ?
        ORDER BY id DESC
        LIMIT 10
        """, (message.from_user.id,))

        rows = await cursor.fetchall()

    if not rows:

        await message.answer("📭 Сообщений пока нет")

        return

    text = "📬 Последние сообщения:\n\n"

    for row in rows:

        text += f"• {row[0]}\n\n"

    await message.answer(text)

# =========================
# INVITE
# =========================

@dp.message(F.text == "👥 Пригласить")
async def invite(message: types.Message):

    await message.answer(
        "🔥 Пригласи друзей и получай больше сообщений"
    )

# =========================
# ADMIN
# =========================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "⚙️ Админ панель",
        reply_markup=admin_menu
    )

# =========================
# BROADCAST
# =========================

@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.waiting_broadcast)

    await message.answer("✍️ Введи текст рассылки")

@dp.message(AdminState.waiting_broadcast)
async def process_broadcast(
    message: types.Message,
    state: FSMContext
):

    async with aiosqlite.connect("db.sqlite3") as db:

        cursor = await db.execute("""
        SELECT user_id FROM users
        WHERE banned = 0
        """)

        users = await cursor.fetchall()

    sent = 0

    for user in users:

        try:

            await bot.send_message(
                user[0],
                f"📢 {message.text}"
            )

            sent += 1

            await asyncio.sleep(0.05)

        except:
            pass

    await message.answer(f"✅ Отправлено: {sent}")

    await state.clear()

# =========================
# BAN
# =========================

@dp.message(F.text == "🔨 Бан")
async def ban_start(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.waiting_ban)

    await message.answer("✍️ Введи ID пользователя")

@dp.message(AdminState.waiting_ban)
async def process_ban(message: types.Message, state: FSMContext):

    try:

        user_id = int(message.text)

    except:

        await message.answer("❌ Неверный ID")

        return

    async with aiosqlite.connect("db.sqlite3") as db:

        await db.execute("""
        UPDATE users
        SET banned = 1
        WHERE user_id = ?
        """, (user_id,))

        await db.commit()

    await message.answer(f"🔨 Пользователь {user_id} забанен")

    await state.clear()

# =========================
# MAIN
# =========================

async def main():

    await init_db()

    print("✅ BOT STARTED SUCCESSFULLY")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

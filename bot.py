import os
import psycopg2
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

TZ = pytz.timezone("Asia/Yekaterinburg")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# =========================
# БАЗА ДАННЫХ
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trainings (
        id SERIAL PRIMARY KEY,
        title TEXT,
        start_time TIMESTAMP,
        capacity INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        training_id INTEGER REFERENCES trainings(id) ON DELETE CASCADE,
        created_at TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# =========================
# КНОПКИ
# =========================

def main_kb(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📅 Ближайшие тренировки")
    kb.add("📋 Мои записи")
    kb.add("❌ Отменить тренировку")
    if is_admin:
        kb.add("👀 Просмотр записанных")
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb

# =========================
# START
# =========================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, name)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
    """, (message.from_user.id, message.from_user.full_name))

    conn.commit()
    conn.close()

    await message.answer(
        "Привет! Выберите действие:",
        reply_markup=main_kb(message.from_user.id == ADMIN_ID)
    )

# =========================
# БЛИЖАЙШИЕ ТРЕНИРОВКИ
# =========================

@dp.message_handler(lambda m: m.text == "📅 Ближайшие тренировки")
async def show_trainings(message: types.Message):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, start_time, capacity
        FROM trainings
        WHERE start_time > NOW()
        ORDER BY start_time
        LIMIT 5
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет ближайших тренировок.")
        return

    text = "🏋 Ближайшие тренировки:\n\n"
    for tid, title, start_time, capacity in rows:
        text += f"{tid}. {title} — {start_time.strftime('%d.%m %H:%M')}\n"

    text += "\nВведите номер тренировки для записи."
    await message.answer(text, reply_markup=back_kb())

# =========================
# ЗАПИСЬ НА ТРЕНИРОВКУ
# =========================

@dp.message_handler(lambda m: m.text.isdigit())
async def book_or_cancel(message: types.Message):
    number = int(message.text)

    conn = get_db()
    cur = conn.cursor()

    # пользователь
    cur.execute(
        "SELECT id FROM users WHERE telegram_id = %s",
        (message.from_user.id,)
    )
    user = cur.fetchone()
    if not user:
        await message.answer("Ошибка пользователя.")
        conn.close()
        return

    user_id = user[0]

    # попытка отмены
    cur.execute("""
        DELETE FROM bookings
        USING users
        WHERE bookings.id = %s
        AND bookings.user_id = users.id
        AND users.telegram_id = %s
    """, (number, message.from_user.id))

    if cur.rowcount > 0:
        conn.commit()
        conn.close()
        await message.answer("✅ Запись отменена.", reply_markup=main_kb())
        return

    # попытка записи
    cur.execute("""
        SELECT start_time, capacity FROM trainings WHERE id = %s
    """, (number,))
    training = cur.fetchone()

    if not training:
        await message.answer("Тренировка не найдена.")
        conn.close()
        return

    start_time, capacity = training

    if start_time <= datetime.now(TZ):
        await message.answer("⛔ Тренировка уже началась.")
        conn.close()
        return

    # защита от двойной записи
    cur.execute("""
        SELECT 1 FROM bookings
        WHERE user_id = %s AND training_id = %s
    """, (user_id, number))

    if cur.fetchone():
        await message.answer("⚠️ Вы уже записаны на эту тренировку.")
        conn.close()
        return

    # проверка лимита
    if capacity is not None:
        cur.execute(
            "SELECT COUNT(*) FROM bookings WHERE training_id = %s",
            (number,)
        )
        if cur.fetchone()[0] >= capacity:
            await message.answer("⛔ Мест больше нет.")
            conn.close()
            return

    cur.execute("""
        INSERT INTO bookings (user_id, training_id, created_at)
        VALUES (%s, %s, %s)
    """, (user_id, number, datetime.now(TZ)))

    conn.commit()
    conn.close()

    await message.answer("✅ Вы успешно записались!", reply_markup=main_kb())

# =========================
# МОИ ЗАПИСИ
# =========================

@dp.message_handler(lambda m: m.text == "📋 Мои записи")
async def my_bookings(message: types.Message):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT bookings.id, trainings.title, trainings.start_time
        FROM bookings
        JOIN trainings ON bookings.training_id = trainings.id
        JOIN users ON bookings.user_id = users.id
        WHERE users.telegram_id = %s
        ORDER BY trainings.start_time
    """, (message.from_user.id,))

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("📭 У вас нет активных записей.")
        return

    text = "📋 Ваши записи:\n\n"
    for bid, title, start_time in rows:
        text += f"{bid}. {title} — {start_time.strftime('%d.%m %H:%M')}\n"

    await message.answer(text)

# =========================
# КНОПКА ОТМЕНЫ
# =========================

@dp.message_handler(lambda m: m.text == "❌ Отменить тренировку")
async def cancel_prompt(message: types.Message):
    await message.answer(
        "Введите номер записи для отмены:",
        reply_markup=back_kb()
    )

# =========================
# АДМИН-ПАНЕЛЬ
# =========================

@dp.message_handler(lambda m: m.text == "👀 Просмотр записанных")
async def admin_view(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT trainings.title, trainings.start_time, users.name
        FROM bookings
        JOIN trainings ON bookings.training_id = trainings.id
        JOIN users ON bookings.user_id = users.id
        ORDER BY trainings.start_time
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("Записей пока нет.")
        return

    text = "👀 Все записи:\n\n"
    for title, start_time, name in rows:
        text += f"{title} — {start_time.strftime('%d.%m %H:%M')} — {name}\n"

    await message.answer(text)

# =========================
# ЗАПУСК
# =========================

async def on_startup(dp):
    init_db()
    print("Bot started")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)

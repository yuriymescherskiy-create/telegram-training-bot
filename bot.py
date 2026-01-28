import os
import sqlite3
import asyncio
from datetime import datetime, timedelta, time
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен берём из Railway / .env
ADMIN_ID = 2021080653               # твой Telegram ID
TZ = pytz.timezone("Asia/Yekaterinburg") # часовой пояс

DB_NAME = "bot.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler(timezone=TZ)

# =========================
# БАЗА ДАННЫХ
# =========================

def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # пользователи
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        name TEXT
    )
    """)

    # шаблоны расписания (еженедельные)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        weekday INTEGER,      -- 0 = понедельник
        time TEXT,            -- HH:MM
        capacity INTEGER,
        active INTEGER
    )
    """)

    # конкретные тренировки
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trainings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER,
        start_time TEXT,
        capacity INTEGER
    )
    """)

    # записи пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        training_id INTEGER,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

# =========================
# НАЧАЛЬНОЕ РАСПИСАНИЕ
# =========================

def seed_templates():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM schedule_templates")
    if cur.fetchone()[0] == 0:
        templates = [
            ("Джампинг", 0, "10:00", 14, 1),
            ("Джампинг", 0, "19:30", 14, 1),
            ("Жиротопка", 2, "19:30", None, 1),
        ]
        cur.executemany(
            "INSERT INTO schedule_templates (title, weekday, time, capacity, active) VALUES (?, ?, ?, ?, ?)",
            templates
        )

    conn.commit()
    conn.close()

# =========================
# ГЕНЕРАЦИЯ ТРЕНИРОВОК
# =========================

def generate_trainings(days_ahead=14):
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now(TZ)

    cur.execute("SELECT id, title, weekday, time, capacity FROM schedule_templates WHERE active = 1")
    templates = cur.fetchall()

    for tpl_id, title, weekday, time_str, capacity in templates:
        hour, minute = map(int, time_str.split(":"))

        for i in range(days_ahead):
            day = now.date() + timedelta(days=i)
            if day.weekday() != weekday:
                continue

            start_dt = TZ.localize(datetime.combine(day, time(hour, minute)))

            cur.execute(
                "SELECT id FROM trainings WHERE template_id = ? AND start_time = ?",
                (tpl_id, start_dt.isoformat())
            )
            if cur.fetchone():
                continue

            cur.execute(
                "INSERT INTO trainings (template_id, start_time, capacity) VALUES (?, ?, ?)",
                (tpl_id, start_dt.isoformat(), capacity)
            )

    conn.commit()
    conn.close()

# =========================
# КНОПКИ
# =========================

def main_kb(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📅 Ближайшие тренировки")
    kb.add("📋 Мои записи", "❌ Отменить тренировку")
    if is_admin:
        kb.add("👀 Просмотр записанных")
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅ Назад")
    return kb

# =========================
# НАПОМИНАНИЕ
# =========================

async def send_reminder(user_id, training_time, title):
    await bot.send_message(
        user_id,
        f"⏰ Напоминание!\nТренировка «{title}» начнётся в {training_time.strftime('%d.%m %H:%M')}"
    )

def schedule_reminders():
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now(TZ)

    cur.execute("""
    SELECT users.telegram_id, trainings.start_time, schedule_templates.title
    FROM bookings
    JOIN users ON bookings.user_id = users.id
    JOIN trainings ON bookings.training_id = trainings.id
    JOIN schedule_templates ON trainings.template_id = schedule_templates.id
    """)

    for tg_id, start_time, title in cur.fetchall():
        start_dt = datetime.fromisoformat(start_time)
        remind_time = start_dt - timedelta(hours=4)

        if remind_time > now:
            scheduler.add_job(
                send_reminder,
                'date',
                run_date=remind_time,
                args=[tg_id, start_dt, title]
            )

    conn.close()

# =========================
# ХЭНДЛЕРЫ
# =========================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
        (message.from_user.id, message.from_user.full_name)
    )
    conn.commit()
    conn.close()

    await message.answer(
        "Привет! Выберите действие:",
        reply_markup=main_kb(message.from_user.id == ADMIN_ID)
    )

@dp.message_handler(lambda m: m.text == "📅 Ближайшие тренировки")
async def show_trainings(message: types.Message):
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now(TZ)

    cur.execute("""
    SELECT trainings.id, schedule_templates.title, trainings.start_time, trainings.capacity
    FROM trainings
    JOIN schedule_templates ON trainings.template_id = schedule_templates.id
    WHERE trainings.start_time > ?
    ORDER BY trainings.start_time
    LIMIT 5
    """, (now.isoformat(),))

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("Нет ближайших тренировок.")
        return

    text = "🏋 Ближайшие тренировки:\n\n"
    for tid, title, start_time, capacity in rows:
        dt = datetime.fromisoformat(start_time)
        text += f"{tid}. {title} — {dt.strftime('%d.%m %H:%M')}\n"

    await message.answer(text + "\nНапишите номер тренировки для записи.", reply_markup=back_kb())

@dp.message_handler(lambda m: m.text.isdigit())
async def book_training(message: types.Message):
    training_id = int(message.text)
    user_id = message.from_user.id

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    user_db_id = cur.fetchone()[0]

    cur.execute("SELECT start_time, capacity FROM trainings WHERE id = ?", (training_id,))
    row = cur.fetchone()
    if not row:
        await message.answer("Тренировка не найдена.")
        return

    start_dt = datetime.fromisoformat(row[0])
    capacity = row[1]

    if start_dt <= datetime.now(TZ):
        await message.answer("⛔ Тренировка уже началась.")
        return

    if capacity is not None:
        cur.execute("SELECT COUNT(*) FROM bookings WHERE training_id = ?", (training_id,))
        if cur.fetchone()[0] >= capacity:
            await message.answer("⛔ На данную дату и время мест не осталось.")
            return

    cur.execute(
        "INSERT INTO bookings (user_id, training_id, created_at) VALUES (?, ?, ?)",
        (user_db_id, training_id, datetime.now(TZ).isoformat())
    )

    conn.commit()
    conn.close()

    await message.answer("✅ Вы успешно записались!", reply_markup=main_kb())

# =========================
# ЗАПУСК
# =========================

async def on_startup(dp):
    init_db()
    seed_templates()
    generate_trainings()
    scheduler.start()
    schedule_reminders()
    print("Bot started")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)

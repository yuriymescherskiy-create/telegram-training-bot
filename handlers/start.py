from aiogram import types
from aiogram.dispatcher import Dispatcher
from keyboards.main import main_menu
from db import get_db

def register_start(dp: Dispatcher):

    @dp.message_handler(commands=["start"])
    async def start(message: types.Message):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users (telegram_id, name)
            VALUES (%s, %s)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            (message.from_user.id, message.from_user.full_name)
        )

        conn.commit()
        cur.close()
        conn.close()

        await message.answer(
            "Привет! Записывайся на тренировки 👇",
            reply_markup=main_menu()
        )

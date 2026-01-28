from aiogram import Bot, Dispatcher, executor
from config import BOT_TOKEN
from handlers.start import register_start

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

from services.schedule import generate_week_schedule

generate_week_schedule()
register_start(dp)


if __name__ == "__main__":
    executor.start_polling(dp)




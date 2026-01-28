from aiogram import Bot, Dispatcher, executor
from config import BOT_TOKEN
from handlers.start import register_start

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

register_start(dp)

if __name__ == "__main__":
    executor.start_polling(dp)



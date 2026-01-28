from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton("📅 Записаться"),
        KeyboardButton("📖 Мои записи")
    )
    return kb

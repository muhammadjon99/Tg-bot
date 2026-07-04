from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

async def safe_edit(target, text, reply_markup=None, parse_mode=None):
    """CallbackQuery yoki Message bo'lishidan qat'iy nazar xavfsiz tahrirlaydi"""
    try:
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await target.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        pass
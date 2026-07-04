from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from bot.config import settings
from bot.keyboards.inline import admin_menu_kb

router = Router()

def is_admin(user_id):
    return user_id in settings.admin_ids

@router.message(Command("admin"))
async def cmd_admin(message: Message, t):
    if not is_admin(message.from_user.id):
        return
    await message.answer(t("admin_panel"), parse_mode="HTML", reply_markup=admin_menu_kb(t))

@router.callback_query(F.data == "back_admin")
async def cb_back_admin(call: CallbackQuery, t):
    """Har qanday ichki bo'limdan asosiy admin panelga qaytaradi"""
    try:
        await call.message.edit_text(t("admin_panel"), parse_mode="HTML", reply_markup=admin_menu_kb(t))
    except TelegramBadRequest:
        pass
    await call.answer()
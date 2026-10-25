from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from database.models import User, Lesson, Category, PromoCode
from bot.utils.helpers import safe_edit

router = Router()


@router.callback_query(F.data == "adm_stats")
async def cb_admin_stats(call: CallbackQuery, session):
    total_users = (await session.execute(select(func.count(User.id)))).scalar()
    blocked_users = (await session.execute(select(func.count(User.id)).where(User.is_blocked == True))).scalar()
    active_users = total_users - blocked_users

    total_lessons = (await session.execute(select(func.count(Lesson.id)))).scalar()
    total_categories = (await session.execute(select(func.count(Category.id)))).scalar()

    active_promos = (
        await session.execute(select(func.count(PromoCode.id)).where(PromoCode.is_active == True))).scalar()

    text = (f"📊 <b>Statistika</b>\n\n"
            f"👥 <b>Foydalanuvchilar:</b>\n"
            f"   ✅ Faol: {active_users}\n"
            f"   🚫 Bloklangan: {blocked_users}\n"
            f"   📈 Jami: {total_users}\n\n"
            f"📚 <b>Kontent:</b>\n"
            f"   📂 Kategoriyalar: {total_categories}\n"
            f"   📖 Darslar: {total_lessons}\n\n"
            f"🎟 <b>Promokodlar:</b>\n"
            f"   🎫 Aktiv: {active_promos}\n\n"
            f"💡 <i>Ma'lumotlar real-time yangilanadi</i>")

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")

    await safe_edit(call, text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()
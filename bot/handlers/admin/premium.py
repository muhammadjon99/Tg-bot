from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete
from database.models import PremiumPackage, PaymentRequest
from bot.utils.helpers import safe_edit

router = Router()


class PremStates(StatesGroup):
    waiting_data = State()


def prem_list_kb(packages):
    kb = InlineKeyboardBuilder()
    for p in packages:
        kb.button(text=f"❌ {p.name_uz} ({p.price_uzs} UZS)", callback_data=f"del_prem:{p.id}")
    kb.button(text="➕ Yangi paket", callback_data="add_prem")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)
    return kb.as_markup()


async def show_prem_list(target, session):
    result = await session.execute(select(PremiumPackage))
    packages = result.scalars().all()

    text = "👑 <b>Premium paketlar:</b>\n\n"
    if not packages:
        text += "Hozircha paketlar yo'q"
    else:
        for p in packages:
            text += f"📦 <b>{p.name_uz}</b> | {p.name_ru}\n"
            text += f"   💵 {p.price_uzs} UZS | 🪙 {p.price_coins}\n"
            text += f"   📚 {p.lessons_quota} dars | 💰 {p.bonus_coins} bonus\n"
            text += f"   ⏰ {p.duration_days} kun [ID:{p.id}]\n\n"

    await safe_edit(target, text, reply_markup=prem_list_kb(packages), parse_mode="HTML")


@router.callback_query(F.data == "adm_prem")
async def cb_admin_prem(call: CallbackQuery, session):
    await show_prem_list(call, session)
    await call.answer()


@router.callback_query(F.data == "add_prem")
async def cb_add_prem(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_prem")

    text = ("👑 <b>Yangi Premium paket</b>\n\n"
            "Format:\n<code>name_uz|name_ru|price_uzs|price_coins|lessons_quota|bonus_coins|duration_days</code>\n\n"
            "Misol:\n<code>Starter|Стартер|30000|500|25|100|30</code>")

    await safe_edit(call, text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(PremStates.waiting_data)
    await call.answer()


@router.message(PremStates.waiting_data)
async def process_prem(message: Message, state: FSMContext, session):
    try:
        parts = message.text.split("|")
        pkg = PremiumPackage(
            name_uz=parts[0],
            name_ru=parts[1],
            price_uzs=int(parts[2]),
            price_coins=int(parts[3]),
            lessons_quota=int(parts[4]),
            bonus_coins=int(parts[5]),
            duration_days=int(parts[6])
        )
        session.add(pkg)
        await session.commit()
        await state.clear()
        await message.answer("✅ <b>Premium paket qo'shildi!</b>", parse_mode="HTML")
        await show_prem_list(message, session)
    except Exception:
        await message.answer("❌ Xato format! Qaytadan urinib ko'ring.")


@router.callback_query(F.data.startswith("del_prem:"))
async def cb_delete_prem(call: CallbackQuery, session):
    pkg_id = int(call.data.split(":")[1])
    await session.execute(delete(PaymentRequest).where(PaymentRequest.package_id == pkg_id))
    await session.execute(delete(PremiumPackage).where(PremiumPackage.id == pkg_id))
    await session.commit()

    await call.answer("✅ O'chirildi!", show_alert=True)
    await show_prem_list(call, session)
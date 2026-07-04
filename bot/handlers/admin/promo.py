from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete
from database.models import PromoCode, PromoCodeUsage
from datetime import datetime, timedelta
from bot.utils.helpers import safe_edit

router = Router()


class PromoStates(StatesGroup):
    waiting_code = State()
    waiting_coins = State()
    waiting_duration = State()
    waiting_max_uses = State()


def promo_list_kb(promos):
    kb = InlineKeyboardBuilder()
    for p in promos:
        kb.button(text=f"❌ {p.code} ({p.coins_amount}🪙)", callback_data=f"del_promo:{p.id}")
    kb.button(text="➕ Yangi promokod", callback_data="add_promo")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)
    return kb.as_markup()


async def show_promo_list(target, session):
    result = await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
    promos = result.scalars().all()

    text = "🎟 <b>Promokodlar:</b>\n\n"
    if not promos:
        text += "Hozircha promokodlar yo'q"
    else:
        for p in promos:
            expires = p.expires_at.strftime("%d.%m %H:%M")
            active = "✅" if p.is_active else "❌"
            text += f"{active} <code>{p.code}</code> - {p.coins_amount}🪙\n"
            text += f"   {p.used_count}/{p.max_uses} | {expires} gacha\n\n"

    await safe_edit(target, text, reply_markup=promo_list_kb(promos), parse_mode="HTML")


@router.callback_query(F.data == "adm_promo")
async def cb_admin_promo(call: CallbackQuery, session):
    await show_promo_list(call, session)
    await call.answer()


@router.callback_query(F.data == "add_promo")
async def cb_add_promo(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_promo")

    await safe_edit(
        call,
        "🎫 Promokod nomini kiriting (Bosh harflar bilan):\n\nMisol: <code>WELCOME100</code>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await state.set_state(PromoStates.waiting_code)
    await call.answer()


@router.message(PromoStates.waiting_code)
async def process_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await message.answer(f"💰 <b>{code}</b> nechta tanga beradi?\n\nMisol: <code>100</code>", parse_mode="HTML")
    await state.set_state(PromoStates.waiting_coins)


@router.message(PromoStates.waiting_coins)
async def process_promo_coins(message: Message, state: FSMContext):
    try:
        coins = int(message.text.strip())
        await state.update_data(coins=coins)

        kb = InlineKeyboardBuilder()
        kb.button(text="30 daqiqa", callback_data="dur_30")
        kb.button(text="1 soat", callback_data="dur_60")
        kb.button(text="6 soat", callback_data="dur_360")
        kb.button(text="12 soat", callback_data="dur_720")
        kb.button(text="1 kun", callback_data="dur_1440")
        kb.button(text="7 kun", callback_data="dur_10080")
        kb.adjust(2, 2, 2)

        await message.answer("⏰ Promokod qancha vaqt amal qiladi?", reply_markup=kb.as_markup())
        await state.set_state(PromoStates.waiting_duration)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


@router.callback_query(PromoStates.waiting_duration, F.data.startswith("dur_"))
async def process_promo_duration(call: CallbackQuery, state: FSMContext):
    minutes = int(call.data.split("_")[1])
    await state.update_data(minutes=minutes)
    await safe_edit(call, "📊 Maksimal nechta marta ishlatilsin?\n\nMisol: <code>100</code>", parse_mode="HTML")
    await state.set_state(PromoStates.waiting_max_uses)
    await call.answer()


@router.message(PromoStates.waiting_max_uses)
async def process_promo_max_uses(message: Message, state: FSMContext, session):
    try:
        max_uses = int(message.text.strip())
        data = await state.get_data()

        code = data.get("code")
        coins = data.get("coins")
        minutes = data.get("minutes")
        expires_at = datetime.utcnow() + timedelta(minutes=minutes)

        promo = PromoCode(
            code=code,
            coins_amount=coins,
            max_uses=max_uses,
            expires_at=expires_at
            # is_active default True
        )
        session.add(promo)
        await session.commit()
        await session.refresh(promo)

        # Tekshirish: kod haqiqatan ham yaratildimi?
        verify_result = await session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        created_promo = verify_result.scalar_one_or_none()

        print(f"[PROMO CREATED] Kod: {code}, Bazada: {bool(created_promo)}, Expires: {expires_at}")

        if not created_promo:
            await message.answer("❌ Promokod yaratilmadi! Bazada muammo.")
            return

        await message.answer(
            f"✅ <b>Promokod muvaffaqiyatli yaratildi!</b>\n\n"
            f"🎫 Kod: <code>{code}</code>\n"
            f"💰 Tanga: {coins}\n"
            f"📊 Limit: {max_uses} marta\n"
            f"⏰ Amal qiladi: <b>{expires_at.strftime('%d.%m.%Y %H:%M')}</b> gacha\n\n"
            f"<i>Hozir ishga solish uchun kodni nusxalang: <code>{code}</code></i>",
            parse_mode="HTML"
        )
        await state.clear()
        await show_promo_list(message, session)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Qaytadan urinib ko'ring:")
    except Exception as e:
        import traceback
        print(f"[PROMO ERROR] {e}\n{traceback.format_exc()}")
        await message.answer(f"❌ Xato yuz berdi: {e}")
        await state.clear()



@router.callback_query(F.data.startswith("del_promo:"))
async def cb_delete_promo(call: CallbackQuery, session):
    promo_id = int(call.data.split(":")[1])
    await session.execute(delete(PromoCodeUsage).where(PromoCodeUsage.promo_code_id == promo_id))
    await session.execute(delete(PromoCode).where(PromoCode.id == promo_id))
    await session.commit()

    await call.answer("✅ O'chirildi!", show_alert=True)
    await show_promo_list(call, session)
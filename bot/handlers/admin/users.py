from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from database.models import User, CoinTransaction
from bot.utils.helpers import safe_edit
import asyncio

router = Router()


class UserMgmtStates(StatesGroup):
    waiting_for_coins = State()
    waiting_for_broadcast = State()


@router.callback_query(F.data == "adm_users")
async def cb_admin_users(call: CallbackQuery, session):
    result = await session.execute(select(User).order_by(User.registered_at.desc()).limit(10))
    users = result.scalars().all()

    text = "👥 <b>Foydalanuvchilar (oxirgi 10 ta):</b>\n\n"
    kb = InlineKeyboardBuilder()

    for u in users:
        username = f"@{u.username}" if u.username else "—"
        blocked = "🚫" if u.is_blocked else "✅"
        text += f"{blocked} <b>{u.full_name}</b>\n"
        text += f"   🆔 <code>{u.id}</code> | {username}\n"
        text += f"   💰 {u.coins_balance} tanga | 🔥 {u.checkin_streak} kun\n\n"
        kb.button(text=f"👁 {u.full_name[:20]}", callback_data=f"view_user:{u.id}")

    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)

    await safe_edit(call, text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("view_user:"))
async def cb_view_user(call: CallbackQuery, session):
    user_id = int(call.data.split(":")[1])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return await call.answer("Foydalanuvchi topilmadi", show_alert=True)

    username = f"@{user.username}" if user.username else "—"
    blocked = "🚫 Bloklangan" if user.is_blocked else "✅ Faol"

    text = (f"👤 <b>Foydalanuvchi profili</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📛 Ism: {user.full_name}\n"
            f"📱 Username: {username}\n"
            f"🌐 Til: {user.language or '—'}\n"
            f"💰 Balans: <b>{user.coins_balance}</b> tanga\n"
            f"🔥 Streak: <b>{user.checkin_streak}</b> kun\n"
            f"📅 Ro'yxatdan: {user.registered_at.strftime('%d.%m.%Y')}\n"
            f"🚫 Status: {blocked}\n\n"
            f"<a href='tg://user?id={user.id}'>👤 Profilni ochish</a>")

    kb = InlineKeyboardBuilder()
    if user.is_blocked:
        kb.button(text="✅ Blokdan chiqarish", callback_data=f"unblock_user:{user.id}")
    else:
        kb.button(text="🚫 Bloklash", callback_data=f"block_user:{user.id}")
    kb.button(text="💰 Tanga berish", callback_data=f"give_coins:{user.id}")
    kb.button(text="◀️ Orqaga (Foydalanuvchilar)", callback_data="adm_users")
    kb.adjust(1)

    await safe_edit(call, text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("block_user:"))
async def cb_block_user(call: CallbackQuery, session):
    user_id = int(call.data.split(":")[1])
    await session.execute(update(User).where(User.id == user_id).values(is_blocked=True))
    await session.commit()
    await call.answer("✅ Foydalanuvchi bloklandi!", show_alert=True)
    await cb_view_user(call, session)


@router.callback_query(F.data.startswith("unblock_user:"))
async def cb_unblock_user(call: CallbackQuery, session):
    user_id = int(call.data.split(":")[1])
    await session.execute(update(User).where(User.id == user_id).values(is_blocked=False))
    await session.commit()
    await call.answer("✅ Foydalanuvchi blokdan chiqarildi!", show_alert=True)
    await cb_view_user(call, session)


@router.callback_query(F.data.startswith("give_coins:"))
async def cb_give_coins(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(":")[1])
    await state.update_data(target_user_id=user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data=f"view_user:{user_id}")

    await safe_edit(
        call,
        f"💰 <code>{user_id}</code> ID ga nechta tanga berasiz?\n\nMisol: <code>100</code>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(UserMgmtStates.waiting_for_coins)
    await call.answer()


# ⚠️ MUHIM: Faqat UserMgmtStates.waiting_for_coins holatida ishlaydi!
@router.message(UserMgmtStates.waiting_for_coins, F.text)
async def process_give_coins(message: Message, state: FSMContext, session):
    data = await state.get_data()
    user_id = data.get("target_user_id")

    try:
        amount = int(message.text.strip())

        await session.execute(update(User).where(User.id == user_id).values(coins_balance=User.coins_balance + amount))

        tx = CoinTransaction(user_id=user_id, amount=amount, type="admin_gift", description="Admin tomonidan berildi")
        session.add(tx)
        await session.commit()

        await message.answer(f"✅ {user_id} ID ga <b>{amount}</b> tanga berildi!", parse_mode="HTML")

        try:
            await message.bot.send_message(user_id, f"🎉 Admin sizga <b>{amount}</b> tanga sovg'a qildi!",
                                           parse_mode="HTML")
        except Exception:
            pass

        await state.clear()
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Masalan: <code>100</code>", parse_mode="HTML")


@router.callback_query(F.data == "adm_broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    await safe_edit(call, "📢 Broadcast matnini yuboring (rasm yoki text):")
    await state.set_state(UserMgmtStates.waiting_for_broadcast)
    await call.answer()


@router.message(UserMgmtStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, session):
    result = await session.execute(select(User.id).where(User.is_blocked == False))
    users = [row[0] for row in result.fetchall()]

    sent = 0
    failed = 0

    for user_id in users:
        if user_id == message.from_user.id:
            continue
        try:
            await message.send_copy(chat_id=user_id)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(f"✅ Broadcast tugadi!\n\n📤 Yuborildi: {sent}\n❌ Xato: {failed}")
    await state.clear()
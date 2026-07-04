from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete
from database.models import RequiredChannel
from bot.utils.helpers import safe_edit

router = Router()


class ChannelStates(StatesGroup):
    waiting_channel = State()


def channels_list_kb(channels):
    kb = InlineKeyboardBuilder()
    for ch in channels:
        kb.button(text=f"❌ @{ch.channel_username}", callback_data=f"del_channel:{ch.id}")
    kb.button(text="➕ Kanal qo'shish", callback_data="add_channel")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)
    return kb.as_markup()


async def show_channels_list(target, session):
    result = await session.execute(select(RequiredChannel))
    channels = result.scalars().all()

    text = "📢 <b>Majburiy kanallar:</b>\n\n"
    if not channels:
        text += "Hozircha kanallar qo'shilmagan"
    else:
        for ch in channels:
            text += f"• @{ch.channel_username} (ID: <code>{ch.channel_id}</code>)\n"

    await safe_edit(target, text, reply_markup=channels_list_kb(channels), parse_mode="HTML")


@router.callback_query(F.data == "adm_channels")
async def cb_admin_channels(call: CallbackQuery, session):
    await show_channels_list(call, session)
    await call.answer()


@router.callback_query(F.data == "add_channel")
async def cb_add_channel(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_channels")

    await safe_edit(
        call,
        "📢 Kanal ma'lumotlarini kiriting:\n\n"
        "Format: <code>channel_id|username</code>\n\n"
        "Misol: <code>-1001234567890|mychannel</code>\n\n"
        "<i>Kanal ID ni @userinfobot orqali toping</i>",
        reply_markup=kb.as_markup(), parse_mode="HTML"
    )
    await state.set_state(ChannelStates.waiting_channel)
    await call.answer()


@router.message(ChannelStates.waiting_channel)
async def process_channel(message: Message, state: FSMContext, session):
    try:
        channel_id, username = message.text.split("|")
        channel = RequiredChannel(
            channel_id=int(channel_id.strip()),
            channel_username=username.strip().lstrip("@")
        )
        session.add(channel)
        await session.commit()

        await message.answer(f"✅ Kanal @{username.strip()} qo'shildi!")
        await state.clear()
        await show_channels_list(message, session)
    except Exception:
        await message.answer("❌ Xato format!")


@router.callback_query(F.data.startswith("del_channel:"))
async def cb_delete_channel(call: CallbackQuery, session):
    channel_id = int(call.data.split(":")[1])
    await session.execute(delete(RequiredChannel).where(RequiredChannel.id == channel_id))
    await session.commit()

    await call.answer("✅ O'chirildi!", show_alert=True)
    await show_channels_list(call, session)
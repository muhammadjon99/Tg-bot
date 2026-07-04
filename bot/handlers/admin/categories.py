from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete
from database.models import Category, Lesson
from bot.utils.helpers import safe_edit

router = Router()


class CatStates(StatesGroup):
    waiting_title = State()


async def show_cats_tree(call_or_msg, session, parent_id=None, level=0):
    if parent_id is None:
        result = await session.execute(
            select(Category).where(Category.parent_id == None).order_by(Category.order_num, Category.id)
        )
    else:
        result = await session.execute(
            select(Category).where(Category.parent_id == parent_id).order_by(Category.order_num, Category.id)
        )
    cats = result.scalars().all()

    indent = "  " * level
    text = f"{indent}📂 <b>Kategoriyalar:</b>\n\n"

    kb = InlineKeyboardBuilder()

    if not cats:
        text += f"{indent}<i>Bo'sh</i>\n"
    else:
        for c in cats:
            sub_result = await session.execute(select(Category.id).where(Category.parent_id == c.id))
            has_children = sub_result.scalars().first() is not None

            prefix = "📁" if has_children else "📄"
            text += f"{indent}{prefix} <b>{c.title_uz}</b> (ID:{c.id})\n"

            # ⚠️ O'ZGARTIRILDI: adm_ prefiksi qo'shildi
            if has_children:
                kb.button(text=f"{indent}📂 {c.title_uz}", callback_data=f"adm_view_cat:{c.id}")
            kb.button(text=f"{indent}➕ Sub {c.title_uz}", callback_data=f"adm_add_sub_cat:{c.id}")
            kb.button(text=f"{indent}❌ {c.title_uz}", callback_data=f"adm_del_cat:{c.id}")

    if parent_id is not None:
        parent_res = await session.execute(select(Category).where(Category.id == parent_id))
        parent_cat = parent_res.scalar_one_or_none()
        if parent_cat and parent_cat.parent_id:
            kb.button(text="◀️ Yuqoriga", callback_data=f"adm_view_cat:{parent_cat.parent_id}")
        else:
            kb.button(text="◀️ Asosiy ro'yxat", callback_data="adm_cats")

    kb.button(text="➕ Yangi kategoriya", callback_data="adm_add_cat")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)

    await safe_edit(call_or_msg, text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "adm_cats")
async def cb_admin_cats(call: CallbackQuery, session):
    await show_cats_tree(call, session, parent_id=None)
    await call.answer()


# ⚠️ O'ZGARTIRILDI: adm_view_cat
@router.callback_query(F.data.startswith("adm_view_cat:"))
async def cb_view_category(call: CallbackQuery, session):
    cat_id = int(call.data.split(":")[1])
    await show_cats_tree(call, session, parent_id=cat_id, level=1)
    await call.answer()


# ⚠️ O'ZGARTIRILDI: adm_add_cat
@router.callback_query(F.data == "adm_add_cat")
async def cb_add_cat(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_cats")

    await safe_edit(
        call,
        "📝 <b>Yangi asosiy kategoriya</b>\n\n"
        "Format: <code>UZ nom|RU nom</code>\n"
        "Misol: <code>Dasturlash|Программирование</code>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.update_data(parent_id=None)
    await state.set_state(CatStates.waiting_title)
    await call.answer()


# ⚠️ O'ZGARTIRILDI: adm_add_sub_cat
@router.callback_query(F.data.startswith("adm_add_sub_cat:"))
async def cb_add_sub_cat(call: CallbackQuery, state: FSMContext, session):
    parent_id = int(call.data.split(":")[1])

    result = await session.execute(select(Category).where(Category.id == parent_id))
    parent = result.scalar_one_or_none()

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data=f"adm_view_cat:{parent_id}")

    await safe_edit(
        call,
        f"📝 <b>Sub-kategoriya qo'shish</b>\n\n"
        f"📁 Ota: <b>{parent.title_uz}</b>\n\n"
        f"Format: <code>UZ nom|RU nom</code>\n"
        f"Misol: <code>Python|Питон</code>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.update_data(parent_id=parent_id)
    await state.set_state(CatStates.waiting_title)
    await call.answer()


@router.message(CatStates.waiting_title)
async def process_cat(message: Message, state: FSMContext, session):
    try:
        data = await state.get_data()
        parent_id = data.get("parent_id")

        uz, ru = message.text.split("|")
        cat = Category(title_uz=uz.strip(), title_ru=ru.strip(), parent_id=parent_id)
        session.add(cat)
        await session.commit()

        await message.answer("✅ <b>Kategoriya qo'shildi!</b>", parse_mode="HTML")
        await state.clear()

        if parent_id:
            await show_cats_tree(message, session, parent_id=parent_id, level=1)
        else:
            await show_cats_tree(message, session, parent_id=None)
    except Exception:
        await message.answer("❌ Xato: <code>UZ|RU</code> formatida kiriting!", parse_mode="HTML")


# ⚠️ O'ZGARTIRILDI: adm_del_cat
@router.callback_query(F.data.startswith("adm_del_cat:"))
async def cb_delete_cat(call: CallbackQuery, session):
    cat_id = int(call.data.split(":")[1])

    result = await session.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()

    if cat:
        parent_id = cat.parent_id

        await session.execute(delete(Lesson).where(Lesson.category_id == cat_id))
        await session.execute(delete(Category).where(Category.id == cat_id))
        await session.commit()

        await call.answer("✅ O'chirildi!", show_alert=True)

        if parent_id:
            await show_cats_tree(call, session, parent_id=parent_id, level=1)
        else:
            await show_cats_tree(call, session, parent_id=None)
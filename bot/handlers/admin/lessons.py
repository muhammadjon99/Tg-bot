from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, delete
from database.models import Lesson, Category, UnlockedLesson
from bot.utils.helpers import safe_edit

router = Router()


class LessonStates(StatesGroup):
    waiting_data = State()
    waiting_content_uz = State()
    waiting_content_ru = State()
    waiting_video_choice = State()
    waiting_video_file = State()
    waiting_video_title_uz = State()
    waiting_video_title_ru = State()


def lessons_list_kb(lessons):
    kb = InlineKeyboardBuilder()
    for l in lessons:
        cost = f"{l.coin_cost}🪙" if l.coin_cost > 0 else "Bepul"
        prem = "👑" if l.is_premium_only else ""
        kb.button(text=f"❌ {l.title_uz} ({cost}){prem}", callback_data=f"del_lesson:{l.id}")
    kb.button(text="➕ Yangi dars", callback_data="add_lesson")
    kb.button(text="◀️ Orqaga (Admin Panel)", callback_data="back_admin")
    kb.adjust(1)
    return kb.as_markup()


async def show_lessons_list(target, session):
    result = await session.execute(select(Lesson).order_by(Lesson.id))
    lessons = result.scalars().all()

    text = "📖 <b>Darslar boshqaruvi:</b>\n\n"
    if not lessons:
        text += "Hozircha darslar yo'q"
    else:
        for l in lessons:
            cost = f"{l.coin_cost}🪙" if l.coin_cost > 0 else "Bepul"
            prem = " 👑" if l.is_premium_only else ""
            text += f"• <b>{l.title_uz}</b> ({cost}){prem} [ID:{l.id}]\n"

    await safe_edit(target, text, reply_markup=lessons_list_kb(lessons), parse_mode="HTML")


@router.callback_query(F.data == "adm_lessons")
async def cb_admin_lessons(call: CallbackQuery, session):
    await show_lessons_list(call, session)
    await call.answer()


@router.callback_query(F.data == "add_lesson")
async def cb_add_lesson(call: CallbackQuery, state: FSMContext, session):
    result = await session.execute(select(Category))
    cats = result.scalars().all()

    if not cats:
        await call.answer("❌ Avval kategoriya qo'shing!", show_alert=True)
        return

    text = "📂 <b>Kategoriyalar:</b>\n\n"
    for c in cats:
        text += f"<code>{c.id}</code> - {c.title_uz}\n"

    text += ("\n📝 Dars ma'lumotlarini kiriting:\n"
             "Format: <code>category_id|title_uz|title_ru|coin_cost|is_premium(0/1)</code>\n\n"
             "Misol: <code>1|Python asoslari|Основы Python|0|0</code>")

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_lessons")

    await safe_edit(call, text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(LessonStates.waiting_data)
    await call.answer()


@router.message(LessonStates.waiting_data)
async def process_lesson_data(message: Message, state: FSMContext, session):
    try:
        parts = message.text.split("|")
        cat_id, title_uz, title_ru, coin_cost, is_premium = parts
        is_premium = bool(int(is_premium))
        coin_cost = int(coin_cost)

        lesson = Lesson(
            category_id=int(cat_id),
            title_uz=title_uz.strip(),
            title_ru=title_ru.strip(),
            coin_cost=coin_cost,
            is_premium_only=is_premium
        )
        session.add(lesson)
        await session.commit()
        await session.refresh(lesson)

        await state.update_data(lesson_id=lesson.id)

        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Bekor qilish", callback_data="adm_lessons")

        await message.answer(
            f"✅ Dars yaratildi (ID: {lesson.id})\n\n📝 Endi <b>O'zbekcha matnni</b> kiriting (yoki 'skip' deb yozing):",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
        await state.set_state(LessonStates.waiting_content_uz)
    except Exception:
        await message.answer("❌ Xato format! Qaytadan kiriting.")


@router.message(LessonStates.waiting_content_uz)
async def process_content_uz(message: Message, state: FSMContext, session):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    if message.text.lower() != "skip":
        lesson.content_uz = message.text or message.caption
    await session.commit()

    await message.answer("📝 Endi <b>Ruscha matnni</b> kiriting (yoki 'skip'):")
    await state.set_state(LessonStates.waiting_content_ru)


@router.message(LessonStates.waiting_content_ru)
async def process_content_ru(message: Message, state: FSMContext, session):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    if message.text.lower() != "skip":
        lesson.content_ru = message.text or message.caption
    await session.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="🎥 Video qo'shish", callback_data="add_video")
    kb.button(text="✅ Tugatish (Videosiz)", callback_data="skip_video")
    kb.adjust(1)

    await message.answer("🎥 Darsga video qo'shmoqchimisiz?", reply_markup=kb.as_markup())
    await state.set_state(LessonStates.waiting_video_choice)


@router.callback_query(LessonStates.waiting_video_choice, F.data == "skip_video")
async def skip_video(call: CallbackQuery, state: FSMContext, session):
    await state.clear()
    await call.message.answer("✅ <b>Dars to'liq qo'shildi!</b>", parse_mode="HTML")
    await show_lessons_list(call, session)
    await call.answer()


@router.callback_query(LessonStates.waiting_video_choice, F.data == "add_video")
async def add_video_start(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="adm_lessons")

    await safe_edit(call, "🎥 Video faylni yuboring:", reply_markup=kb.as_markup())
    await state.set_state(LessonStates.waiting_video_file)
    await call.answer()


@router.message(LessonStates.waiting_video_file, F.video)
async def process_video_file(message: Message, state: FSMContext, session):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    lesson.video_file_id = message.video.file_id
    await session.commit()

    await message.answer("📝 Video uchun <b>O'zbekcha sarlavha</b> kiriting:")
    await state.set_state(LessonStates.waiting_video_title_uz)


@router.message(LessonStates.waiting_video_title_uz)
async def process_video_title_uz(message: Message, state: FSMContext, session):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    lesson.video_title_uz = message.text
    await session.commit()

    await message.answer("📝 Video uchun <b>Ruscha sarlavha</b> kiriting:")
    await state.set_state(LessonStates.waiting_video_title_ru)


@router.message(LessonStates.waiting_video_title_ru)
async def process_video_title_ru(message: Message, state: FSMContext, session):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    lesson.video_title_ru = message.text
    await session.commit()

    await state.clear()
    await message.answer("✅ <b>Video bilan dars to'liq qo'shildi!</b>", parse_mode="HTML")
    await show_lessons_list(message, session)


@router.callback_query(F.data.startswith("del_lesson:"))
async def cb_delete_lesson(call: CallbackQuery, session):
    lesson_id = int(call.data.split(":")[1])
    await session.execute(delete(UnlockedLesson).where(UnlockedLesson.lesson_id == lesson_id))
    await session.execute(delete(Lesson).where(Lesson.id == lesson_id))
    await session.commit()

    await call.answer("✅ O'chirildi!", show_alert=True)
    await show_lessons_list(call, session)
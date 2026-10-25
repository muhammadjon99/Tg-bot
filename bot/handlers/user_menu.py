from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update
from database.models import User, Category, Lesson, UnlockedLesson, PromoCode, PromoCodeUsage, RequiredChannel
from bot.keyboards.inline import main_menu_kb
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

router = Router()


# PROMOKOD UCHUN FSM HOLATI
class UserPromoStates(StatesGroup):
    waiting_for_code = State()


async def check_channel_subscription(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


@router.callback_query(F.data == "back_menu")
async def cb_back_menu(call: CallbackQuery, state: FSMContext, t):
    await state.clear()  # FSM holatlarini tozalash
    try:
        await call.message.edit_text(t("main_menu"), reply_markup=main_menu_kb(t))
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data == "menu_checkin")
async def cb_daily_checkin(call: CallbackQuery, session, t):
    user_result = await session.execute(select(User).where(User.id == call.from_user.id))
    user = user_result.scalar_one_or_none()

    now = datetime.utcnow()
    today = now.date()

    if user.last_checkin:
        last_date = user.last_checkin.date()
        if last_date == today:
            await call.answer("⏰ Bugun allaqachon tasdiqladingiz!", show_alert=True)
            return
        if last_date == today - timedelta(days=1):
            user.checkin_streak += 1
        else:
            user.checkin_streak = 1
    else:
        user.checkin_streak = 1

    user.last_checkin = now
    await session.commit()

    if user.checkin_streak == 7:
        from bot.config import settings
        for admin_id in settings.admin_ids:
            try:
                await call.bot.send_message(
                    admin_id,
                    f"🔥 <b>7 kunlik streak!</b>\n\n👤 {user.full_name} (<code>{user.id}</code>)\n7 kun ketma-ket kirdi!\n\nSovg'a bermoqchimisiz?",
                    parse_mode="HTML"
                )
            except:
                pass

    await call.answer(f"✅ Tasdiqlandi! Streak: {user.checkin_streak} kun", show_alert=True)


@router.callback_query(F.data == "menu_promo")
async def cb_enter_promo(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Bekor qilish", callback_data="back_menu")

    try:
        await call.message.edit_text(
            "🎫 <b>Promokodni kiriting:</b>\n\n"
            "Masalan: <code>WELCOME100</code>",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    # FSM holatiga o'tish
    await state.set_state(UserPromoStates.waiting_for_code)
    await call.answer()


# ⚠️ MUHIM: Faqat UserPromoStates.waiting_for_code holatida ishlaydi!
@router.message(UserPromoStates.waiting_for_code, F.text)
async def process_promo_code(message: Message, session, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id

    # Promokodni qidirish
    result = await session.execute(
        select(PromoCode).where(
            PromoCode.code == code,
            PromoCode.is_active == True,
            PromoCode.expires_at > datetime.utcnow()
        )
    )
    promo = result.scalar_one_or_none()

    if not promo:
        check_any = await session.execute(select(PromoCode).where(PromoCode.code == code))
        found_any = check_any.scalar_one_or_none()

        if found_any:
            if not found_any.is_active:
                await message.answer(f"❌ <code>{code}</code> promokod nofaol!")
            elif found_any.expires_at <= datetime.utcnow():
                await message.answer(f"❌ <code>{code}</code> promokod muddati o'tgan!")
            elif found_any.used_count >= found_any.max_uses:
                await message.answer(f"❌ <code>{code}</code> promokod limiti tugagan!")
        else:
            await message.answer(f"❌ <code>{code}</code> promokod topilmadi!", parse_mode="HTML")
        await state.clear()
        return

    if promo.used_count >= promo.max_uses:
        await message.answer("❌ Promokod limiti tugagan!")
        await state.clear()
        return

    # Avval ishlatilganmi?
    usage_result = await session.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.user_id == user_id,
            PromoCodeUsage.promo_code_id == promo.id
        )
    )
    if usage_result.scalar_one_or_none():
        await message.answer("❌ Siz bu promokodni allaqachon ishlatgansiz!")
        await state.clear()
        return

    # Coin qo'shish
    await session.execute(
        update(User).where(User.id == user_id).values(coins_balance=User.coins_balance + promo.coins_amount))

    # Usage log
    usage = PromoCodeUsage(user_id=user_id, promo_code_id=promo.id)
    session.add(usage)

    promo.used_count += 1
    if promo.used_count >= promo.max_uses:
        promo.is_active = False

    await session.commit()
    await state.clear()

    await message.answer(
        f"🎉 <b>Promokod qabul qilindi!</b>\n\n💰 +{promo.coins_amount} tanga qo'shildi!",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_lessons")
async def cb_show_categories(call: CallbackQuery, session, t):
    # Kanal obuna tekshirish
    channels_result = await session.execute(select(RequiredChannel).where(RequiredChannel.is_active == True))
    channels = channels_result.scalars().all()

    if channels:
        not_subscribed = []
        for ch in channels:
            is_subscribed = await check_channel_subscription(call.bot, call.from_user.id, ch.channel_id)
            if not is_subscribed:
                not_subscribed.append(ch)

        if not_subscribed:
            text = "⚠️ <b>Darslarni ko'rish uchun kanallarga obuna bo'ling:</b>\n\n"
            kb = InlineKeyboardBuilder()
            for ch in not_subscribed:
                text += f"• <a href='https://t.me/{ch.channel_username}'>{ch.channel_username}</a>\n"
                kb.button(text=f"📢 {ch.channel_username}", url=f"https://t.me/{ch.channel_username}")
            kb.button(text="✅ Obuna bo'ldim", callback_data="check_subscription")
            kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
            kb.adjust(1)
            try:
                await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
            except TelegramBadRequest:
                pass
            return await call.answer()

    # Faqat asosiy kategoriyalarni ko'rsatish
    await show_categories_level(call, session, t, parent_id=None)
    await call.answer()


async def show_categories_level(call, session, t, parent_id=None):
    """Kategoriyalar darajasini ko'rsatish"""
    if parent_id is None:
        result = await session.execute(
            select(Category).where(Category.parent_id == None).order_by(Category.order_num, Category.id)
        )
    else:
        result = await session.execute(
            select(Category).where(Category.parent_id == parent_id).order_by(Category.order_num, Category.id)
        )
    cats = result.scalars().all()

    if not cats and parent_id is None:
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
        try:
            await call.message.edit_text(t("no_categories"), reply_markup=kb.as_markup())
        except TelegramBadRequest:
            pass
        return

    kb = InlineKeyboardBuilder()

    for c in cats:
        # Sub-kategoriyalar bormi?
        sub_result = await session.execute(
            select(Category.id).where(Category.parent_id == c.id)
        )
        has_children = sub_result.scalars().first() is not None

        title = c.title_uz if call.from_user.language_code == "uz" or not call.from_user.language_code else c.title_ru
        icon = "📁" if has_children else "📄"

        kb.button(text=f"{icon} {title}", callback_data=f"cat_{c.id}")

    if parent_id is not None:
        # Ota kategoriyani topish
        parent_result = await session.execute(select(Category).where(Category.id == parent_id))
        parent = parent_result.scalar_one_or_none()
        if parent and parent.parent_id:
            kb.button(text="◀️ Orqaga", callback_data=f"cat_{parent.parent_id}")
        else:
            kb.button(text="◀️ Asosiy kategoriyalar", callback_data="menu_lessons")
    else:
        kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")

    kb.adjust(1)

    try:
        await call.message.edit_text(t("select_category"), reply_markup=kb.as_markup())
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("cat_"))
async def cb_show_category_content(call: CallbackQuery, session, t):
    cat_id = int(call.data.split("_")[1])

    # Sub-kategoriyalar bormi?
    sub_result = await session.execute(
        select(Category).where(Category.parent_id == cat_id).order_by(Category.order_num, Category.id)
    )
    sub_cats = sub_result.scalars().all()

    # Darslar bormi?
    lessons_result = await session.execute(
        select(Lesson).where(Lesson.category_id == cat_id).order_by(Lesson.order_num, Lesson.id)
    )
    lessons = lessons_result.scalars().all()

    if sub_cats:
        # Sub-kategoriyalar bor - ularni ko'rsatish
        await show_categories_level(call, session, t, parent_id=cat_id)
    elif lessons:
        # Faqat darslar bor - ularni ko'rsatish
        await show_lessons_list(call, session, t, cat_id)
    else:
        # Bo'sh
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Orqaga", callback_data="menu_lessons")
        try:
            await call.message.edit_text(t("no_lessons"), reply_markup=kb.as_markup())
        except TelegramBadRequest:
            pass

    await call.answer()


async def show_lessons_list(call, session, t, cat_id):
    """Kategoriyadagi darslarni ko'rsatish"""
    result = await session.execute(
        select(Lesson).where(Lesson.category_id == cat_id).order_by(Lesson.order_num, Lesson.id)
    )
    lessons = result.scalars().all()

    if not lessons:
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Orqaga", callback_data="menu_lessons")
        try:
            await call.message.edit_text(t("no_lessons"), reply_markup=kb.as_markup())
        except TelegramBadRequest:
            pass
        return

    kb = InlineKeyboardBuilder()
    for l in lessons:
        title = l.title_uz if call.from_user.language_code == "uz" or not call.from_user.language_code else l.title_ru
        icon = "🔒" if l.coin_cost > 0 else "🔓"
        if l.is_premium_only:
            icon = "👑"
        kb.button(text=f"{icon} {title}", callback_data=f"lesson_{l.id}")

    # Ota kategoriyani topish
    cat_result = await session.execute(select(Category).where(Category.id == cat_id))
    cat = cat_result.scalar_one_or_none()

    if cat and cat.parent_id:
        kb.button(text="◀️ Orqaga", callback_data=f"cat_{cat.parent_id}")
    else:
        kb.button(text="◀️ Asosiy kategoriyalar", callback_data="menu_lessons")

    kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
    kb.adjust(1)

    try:
        await call.message.edit_text(t("select_lesson"), reply_markup=kb.as_markup())
    except TelegramBadRequest:
        pass
@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(call: CallbackQuery, session, t):
    channels_result = await session.execute(select(RequiredChannel).where(RequiredChannel.is_active == True))
    channels = channels_result.scalars().all()

    all_subscribed = True
    for ch in channels:
        is_subscribed = await check_channel_subscription(call.bot, call.from_user.id, ch.channel_id)
        if not is_subscribed:
            all_subscribed = False
            break

    if all_subscribed:
        await call.answer("✅ Obuna tasdiqlandi!", show_alert=True)
        await cb_show_categories(call, session, t)
    else:
        await call.answer("❌ Hali hammasiga obuna bo'lmagansiz!", show_alert=True)


@router.callback_query(F.data.startswith("cat_"))
async def cb_show_lessons(call: CallbackQuery, session, t):
    cat_id = int(call.data.split("_")[1])
    result = await session.execute(select(Lesson).where(Lesson.category_id == cat_id).order_by(Lesson.order_num))
    lessons = result.scalars().all()

    if not lessons:
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Orqaga (Kategoriyalar)", callback_data="menu_lessons")
        kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
        kb.adjust(1)
        try:
            await call.message.edit_text(t("no_lessons"), reply_markup=kb.as_markup())
        except TelegramBadRequest:
            pass
        return await call.answer()

    kb = InlineKeyboardBuilder()
    for l in lessons:
        title = l.title_uz if call.from_user.language_code == "uz" or not call.from_user.language_code else l.title_ru
        icon = "🔒" if l.coin_cost > 0 else "🔓"
        if l.is_premium_only:
            icon = "👑"
        kb.button(text=f"{icon} {title}", callback_data=f"lesson_{l.id}")
    kb.button(text="◀️ Orqaga (Kategoriyalar)", callback_data="menu_lessons")
    kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
    kb.adjust(1)

    try:
        await call.message.edit_text(t("select_lesson"), reply_markup=kb.as_markup())
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("lesson_"))
async def cb_open_lesson(call: CallbackQuery, session, t):
    lesson_id = int(call.data.split("_")[1])
    user_id = call.from_user.id

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    lesson_result = await session.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = lesson_result.scalar_one_or_none()

    if not lesson:
        return await call.answer("Dars topilmadi")

    unlocked_result = await session.execute(
        select(UnlockedLesson).where(
            UnlockedLesson.user_id == user_id,
            UnlockedLesson.lesson_id == lesson_id
        )
    )
    is_unlocked = unlocked_result.scalar_one_or_none() is not None

    is_premium = user.premium_until and user.premium_until > datetime.utcnow()

    can_access = False

    if lesson.coin_cost == 0 and not lesson.is_premium_only:
        can_access = True
    elif lesson.is_premium_only and is_premium:
        can_access = True
    elif is_unlocked:
        can_access = True
    elif lesson.is_premium_only:
        await call.answer(t("lesson_premium_only"), show_alert=True)
        return
    elif lesson.coin_cost > 0:
        if user.coins_balance >= lesson.coin_cost:
            user.coins_balance -= lesson.coin_cost
            unlock = UnlockedLesson(user_id=user_id, lesson_id=lesson_id)
            session.add(unlock)
            await session.commit()
            can_access = True
            await call.message.answer(t("lesson_unlocked", cost=lesson.coin_cost))
        else:
            await call.answer(
                t("lesson_locked", cost=lesson.coin_cost, balance=user.coins_balance).replace("<b>", "").replace("</b>",
                                                                                                                 ""),
                show_alert=True)
            return

    if can_access:
        title = lesson.title_uz if user.language == "uz" else lesson.title_ru
        content = lesson.content_uz if user.language == "uz" else lesson.content_ru

        kb = InlineKeyboardBuilder()
        kb.button(text=f"◀️ Orqaga (Darslar)", callback_data=f"cat_{lesson.category_id}")
        kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")
        kb.adjust(1)

        if lesson.video_file_id:
            video_title = lesson.video_title_uz if user.language == "uz" else lesson.video_title_ru
            await call.message.answer_video(
                lesson.video_file_id,
                caption=f"🎥 <b>{video_title}</b>\n\n{content or ''}",
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        else:
            await call.message.answer(
                t("lesson_content", title=title, content=content or "Bo'sh"),
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )

    await call.answer()


@router.callback_query(F.data == "menu_profile")
async def cb_profile(call: CallbackQuery, session, t):
    user_result = await session.execute(select(User).where(User.id == call.from_user.id))
    user = user_result.scalar_one_or_none()

    premium_status = t("premium_inactive")
    if user.premium_until and user.premium_until > datetime.utcnow():
        premium_status = t("premium_active", until=user.premium_until.strftime("%d.%m.%Y"))

    ref_link = f"https://t.me/EduTrackBot?start=ref_{user.id}"
    text = t("profile_text",
             id=user.id,
             name=user.full_name,
             language=user.language.upper() if user.language else "UZ",
             coins=user.coins_balance,
             streak=user.checkin_streak,
             premium=premium_status,
             used=user.premium_lessons_used,
             quota=user.premium_lessons_quota,
             ref=ref_link)

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")

    try:
        await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data == "menu_myid")
async def cb_myid(call: CallbackQuery, t):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Asosiy menyu", callback_data="back_menu")

    try:
        await call.message.edit_text(t("myid_text", id=call.from_user.id), reply_markup=kb.as_markup(),
                                     parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data == "menu_premium")
async def cb_show_packages(call: CallbackQuery, session, t):
    from database.models import PremiumPackage
    result = await session.execute(select(PremiumPackage).where(PremiumPackage.is_active == True))
    packages = result.scalars().all()

    if not packages:
        kb = InlineKeyboardBuilder()
        kb.button(text="◀️ Orqaga", callback_data="back_menu")
        try:
            await call.message.edit_text("❌ Hozircha paketlar yo'q", reply_markup=kb.as_markup())
        except TelegramBadRequest:
            pass
        return await call.answer()

    kb = InlineKeyboardBuilder()
    text = "👑 <b>Premium paketlar:</b>\n\n"

    for p in packages:
        name = p.name_uz if call.from_user.language_code == "uz" or not call.from_user.language_code else p.name_ru
        text += f"📦 <b>{name}</b>\n"
        text += f"💵 Narxi: <b>{p.price_uzs}</b> so'm yoki <b>{p.price_coins}</b> tanga\n"
        text += f"📚 {p.lessons_quota} ta pullik dars\n"
        text += f"💰 Bonus: {p.bonus_coins} tanga\n"
        text += f"⏰ Muddat: {p.duration_days} kun\n\n"
        kb.button(text=f"💵 {name} - {p.price_uzs} so'm", callback_data=f"buy_pkg:{p.id}:uzs")
        kb.button(text=f"🪙 {p.price_coins} tanga", callback_data=f"buy_pkg:{p.id}:coins")

    kb.button(text="◀️ Orqaga", callback_data="back_menu")
    kb.adjust(1)

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    except TelegramBadRequest:
        pass
    await call.answer()
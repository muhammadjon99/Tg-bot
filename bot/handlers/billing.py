from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.models import User, PremiumPackage, PaymentRequest
from bot.config import settings
from bot.keyboards.inline import payment_approval_kb
from datetime import datetime

router = Router()


class BuyStates(StatesGroup):
    waiting_screenshot = State()


@router.callback_query(F.data == "menu_premium")
async def cb_show_packages(call: CallbackQuery, session, t):
    result = await session.execute(select(PremiumPackage).where(PremiumPackage.is_active == True))
    packages = result.scalars().all()

    if not packages:
        await call.message.answer("❌ Hozircha paketlar yo'q")
        return await call.answer()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    text = "👑 <b>Premium paketlar:</b>\n\n"

    for p in packages:
        text += f"📦 <b>{p.name_uz if t.__name__ == 't' else p.name_ru}</b>\n"
        text += f"💵 Narxi: <b>{p.price_uzs}</b> so'm yoki <b>{p.price_coins}</b> tanga\n"
        text += f"📚 {p.lessons_quota} ta pullik dars\n"
        text += f"💰 Bonus: {p.bonus_coins} tanga\n"
        text += f"⏰ Muddat: {p.duration_days} kun\n\n"
        kb.button(text=f"💵 {p.name_uz} - {p.price_uzs} so'm", callback_data=f"buy_pkg:{p.id}:uzs")
        kb.button(text=f"🪙 {p.price_coins} tanga", callback_data=f"buy_pkg:{p.id}:coins")

    kb.adjust(1)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("buy_pkg:"))
async def cb_buy_package(call: CallbackQuery, state: FSMContext, session, t):
    _, pkg_id, pay_type = call.data.split(":")
    pkg_id = int(pkg_id)

    result = await session.execute(select(PremiumPackage).where(PremiumPackage.id == pkg_id))
    package = result.scalar_one_or_none()

    user_result = await session.execute(select(User).where(User.id == call.from_user.id))
    user = user_result.scalar_one_or_none()

    if pay_type == "coins":
        if user.coins_balance >= package.price_coins:
            user.coins_balance -= package.price_coins
            user.premium_lessons_quota += package.lessons_quota
            user.premium_lessons_used = 0
            user.premium_until = datetime.utcnow() + __import__('datetime').timedelta(days=package.duration_days)
            user.coins_balance += package.bonus_coins
            await session.commit()

            await call.message.answer(
                t("payment_approved",
                  name=package.name_uz,
                  coins=package.bonus_coins,
                  quota=package.lessons_quota,
                  days=package.duration_days),
                parse_mode="HTML"
            )
        else:
            await call.message.answer(t("not_enough_coins"))
        return await call.answer()

    # UZS to'lov - screenshot/PDF kerak
    await state.update_data(package_id=pkg_id)
    await state.set_state(BuyStates.waiting_screenshot)

    await call.message.answer(
        t("payment_card",
          card=settings.payment_card,
          amount=package.price_uzs,
          user_id=call.from_user.id),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(BuyStates.waiting_screenshot, F.photo | F.document)
async def process_payment_file(message: Message, state: FSMContext, session, t):
    data = await state.get_data()
    pkg_id = data.get("package_id")

    result = await session.execute(select(PremiumPackage).where(PremiumPackage.id == pkg_id))
    package = result.scalar_one_or_none()

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        file_id = message.document.file_id
        file_type = "document"

    payment = PaymentRequest(
        user_id=message.from_user.id,
        package_id=pkg_id,
        file_id=file_id,
        file_type=file_type
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    # Adminga yuborish
    for admin_id in settings.admin_ids:
        try:
            caption = t("admin_new_payment",
                        user_id=message.from_user.id,
                        name=message.from_user.full_name,
                        username=f"@{message.from_user.username}" if message.from_user.username else "—",
                        package=package.name_uz,
                        amount=package.price_uzs,
                        time=datetime.now().strftime("%d.%m.%Y %H:%M"))

            if file_type == "photo":
                await message.bot.send_photo(admin_id, file_id, caption=caption,
                                             parse_mode="HTML",
                                             reply_markup=payment_approval_kb(payment.id))
            else:
                await message.bot.send_document(admin_id, file_id, caption=caption,
                                                parse_mode="HTML",
                                                reply_markup=payment_approval_kb(payment.id))
        except Exception as e:
            print(f"Admin xatosi: {e}")

    await message.answer(t("payment_sent"))
    await state.clear()
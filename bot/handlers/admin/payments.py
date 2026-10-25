from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from database.models import PaymentRequest, User, PremiumPackage
from datetime import datetime, timedelta
from bot.config import settings

router = Router()


@router.callback_query(F.data.startswith("pay_ok:"))
async def cb_approve(call: CallbackQuery, session):
    if call.from_user.id not in settings.admin_ids:
        return

    payment_id = int(call.data.split(":")[1])
    result = await session.execute(select(PaymentRequest).where(PaymentRequest.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment or payment.status != "pending":
        return await call.answer("Allaqachon ko'rib chiqilgan", show_alert=True)

    pkg_result = await session.execute(select(PremiumPackage).where(PremiumPackage.id == payment.package_id))
    package = pkg_result.scalar_one_or_none()

    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one_or_none()

    # Premium berish
    user.coins_balance += package.bonus_coins
    user.premium_lessons_quota += package.lessons_quota
    user.premium_lessons_used = 0
    user.premium_until = datetime.utcnow() + timedelta(days=package.duration_days)

    payment.status = "approved"
    await session.commit()

    await call.message.edit_caption(call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")

    # Foydalanuvchiga xabar
    try:
        from bot.middlewares.i18n import I18nMiddleware
        i18n = I18nMiddleware()
        t = lambda k, **kw: i18n.t(user.language or "uz", k, **kw)

        msg = t("payment_approved",
                name=package.name_uz,
                coins=package.bonus_coins,
                quota=package.lessons_quota,
                days=package.duration_days)
        await call.bot.send_message(user.id, msg, parse_mode="HTML")
    except:
        pass

    await call.answer("✅ Tasdiqlandi!", show_alert=True)


@router.callback_query(F.data.startswith("pay_no:"))
async def cb_reject(call: CallbackQuery, session):
    if call.from_user.id not in settings.admin_ids:
        return

    payment_id = int(call.data.split(":")[1])
    result = await session.execute(select(PaymentRequest).where(PaymentRequest.id == payment_id))
    payment = result.scalar_one_or_none()

    if payment:
        payment.status = "rejected"
        await session.commit()

        await call.message.edit_caption(call.message.caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")

        # Foydalanuvchiga xabar
        try:
            user_result = await session.execute(select(User).where(User.id == payment.user_id))
            user = user_result.scalar_one_or_none()
            from bot.middlewares.i18n import I18nMiddleware
            i18n = I18nMiddleware()
            t = lambda k, **kw: i18n.t(user.language or "uz", k, **kw)
            await call.bot.send_message(user.id, t("payment_rejected"))
        except:
            pass

    await call.answer("❌ Rad etildi!", show_alert=True)
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject, CommandStart
from sqlalchemy import select
from database.models import User
from bot.keyboards.inline import lang_kb, main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session):
    result = await session.execute(select(User).where(User.id == message.from_user.id))
    user = result.scalar_one_or_none()

    if not user:
        ref_id = None
        if command.args and command.args.startswith("ref_"):
            try:
                ref_id = int(command.args.split("_")[1])
                if ref_id == message.from_user.id:
                    ref_id = None
            except:
                pass

        user = User(
            id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            referral_by=ref_id
        )
        session.add(user)

        if ref_id:
            ref_result = await session.execute(select(User).where(User.id == ref_id))
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referrer.coins_balance += 50

        await session.commit()

    if not user.language:
        await message.answer(
            "👋 EduTrack ga xush kelibsiz!\nIltimos, tilni tanlang:\n\nДобро пожаловать!\nВыберите язык:",
            reply_markup=lang_kb()
        )
    else:
        from bot.middlewares.i18n import I18nMiddleware
        i18n = I18nMiddleware()
        t = lambda key, **kw: i18n.t(user.language, key, **kw)
        await message.answer(t("main_menu"), reply_markup=main_menu_kb(t))


@router.callback_query(F.data.startswith("lang_"))
async def cb_select_lang(call: CallbackQuery, session):
    lang = call.data.split("_")[1]
    result = await session.execute(select(User).where(User.id == call.from_user.id))
    user = result.scalar_one_or_none()
    user.language = lang
    await session.commit()

    from bot.middlewares.i18n import I18nMiddleware
    i18n = I18nMiddleware()
    t = lambda key, **kw: i18n.t(lang, key, **kw)

    await call.message.edit_text(t("lang_selected"))
    await call.message.answer(t("main_menu"), reply_markup=main_menu_kb(t))
    await call.answer()


@router.message(Command("myid"))
async def cmd_myid(message: Message, t):
    await message.answer(t("myid_text", id=message.from_user.id), parse_mode="HTML")
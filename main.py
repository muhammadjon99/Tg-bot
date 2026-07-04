import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import settings
from bot.middlewares.db import DBMiddleware
from bot.middlewares.i18n import I18nMiddleware
from database.session import init_db
from bot.handlers import start, billing, user_menu
from bot.handlers.admin import panel, payments, categories, lessons, premium, users, promo, stats, channels


async def main():
    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DBMiddleware())
    dp.update.outer_middleware(I18nMiddleware())

    # User handlers
    dp.include_router(start.router)
    dp.include_router(user_menu.router)
    dp.include_router(billing.router)

    # Admin handlers
    dp.include_router(panel.router)
    dp.include_router(payments.router)
    dp.include_router(categories.router)
    dp.include_router(lessons.router)
    dp.include_router(premium.router)
    dp.include_router(users.router)
    dp.include_router(promo.router)
    dp.include_router(stats.router)
    dp.include_router(channels.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
from aiogram import BaseMiddleware
from aiogram.types import Update
from database.session import async_session

class DBMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
import json
import os
import logging
from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy import select
from database.models import User

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseMiddleware):
    def __init__(self):
        self.translations = {}
        for lang in ["uz", "ru"]:
            path = f"bot/locales/{lang}.json"
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)

    def t(self, lang: str, key: str, **kwargs):
        text = self.translations.get(lang, self.translations.get("uz", {})).get(key, key)
        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.error(f"I18n KeyError: {e} for key '{key}' with kwargs: {kwargs}")
            # Agar xatolik bo'lsa, bo'sh joy qo'yamiz
            try:
                return text.format(**{k: kwargs.get(k, "") for k in kwargs})
            except:
                return text
        except Exception as e:
            logger.error(f"I18n format error: {e}")
            return text

    async def __call__(self, handler, event: Update, data: dict):
        user = event.message.from_user if event.message else (
            event.callback_query.from_user if event.callback_query else None)
        session = data.get("session")

        if user and session:
            result = await session.execute(select(User).where(User.id == user.id))
            db_user = result.scalar_one_or_none()

            if db_user and db_user.language:
                data["lang"] = db_user.language
                data["t"] = lambda key, **kwargs: self.t(db_user.language, key, **kwargs)
            else:
                data["lang"] = "uz"
                data["t"] = lambda key, **kwargs: self.t("uz", key, **kwargs)

        return await handler(event, data)
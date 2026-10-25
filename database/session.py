from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base
import os

DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///edutrack.db")
engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
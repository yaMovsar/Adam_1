import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database.db import init_db, get_pool
from handlers import admin, manager, adam, client, common
from utils.scheduler import start_scheduler
from utils.pg_storage import PostgresStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=BOT_TOKEN)

    await init_db()
    pool = await get_pool()
    storage = await PostgresStorage.create(pool)

    dp = Dispatcher(storage=storage)

    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(manager.router)
    dp.include_router(adam.router)
    dp.include_router(client.router)

    start_scheduler(bot)

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

"""Main bot file."""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN

from handlers import (
    auth,
    students,
    groups,
    payments,
    employees,
    attendance,
    common,
    reports,
    documents
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the bot."""
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register routers
    dp.include_router(auth.router)
    dp.include_router(students.router)
    dp.include_router(groups.router)
    dp.include_router(payments.router)
    dp.include_router(employees.router)
    dp.include_router(attendance.router)
    dp.include_router(common.router)
    dp.include_router(reports.router)
    dp.include_router(documents.router)
    
    logger.info("Bot is starting...")
    
    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        # Close Redis connection
        from storage import user_storage
        await user_storage.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

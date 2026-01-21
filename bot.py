"""Main bot file."""
import asyncio
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from config import (
    BOT_TOKEN,
    BOT_MODE,
    WEBHOOK_HOST,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    WEBHOOK_PORT
)

from handlers import (
    auth,
    students,
    groups,
    payments,
    employees,
    attendance,
    common,
    documents
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot):
    """Set up bot commands menu."""
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot):
    """Actions to perform on bot startup."""
    logger.info("Bot is starting up...")
    
    # Set up bot commands
    await setup_bot_commands(bot)
    
    # Set webhook if in prod mode
    if BOT_MODE == 'prod':
        # Validate webhook URL
        if not WEBHOOK_HOST:
            raise ValueError("WEBHOOK_HOST is required when BOT_MODE=prod")
        
        if not WEBHOOK_HOST.startswith('https://'):
            raise ValueError(f"WEBHOOK_HOST must start with https://, got: {WEBHOOK_HOST}")
        
        # Remove trailing slash if exists
        webhook_host = WEBHOOK_HOST.rstrip('/')
        webhook_path = WEBHOOK_PATH.lstrip('/')  # Remove leading slash if exists
        webhook_url = f"{webhook_host}/{webhook_path}" if webhook_path else webhook_host
        
        logger.info(f"Setting webhook to: {webhook_url}")
        
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
                allowed_updates=["message", "callback_query", "chat_member"]
            )
            logger.info(f"✅ Webhook successfully set to: {webhook_url}")
            
            # Verify webhook info
            webhook_info = await bot.get_webhook_info()
            logger.info(f"Webhook info: pending_update_count={webhook_info.pending_update_count}, "
                       f"last_error_date={webhook_info.last_error_date}, "
                       f"last_error_message={webhook_info.last_error_message}")
            
            if webhook_info.last_error_message:
                logger.warning(f"⚠️ Webhook error: {webhook_info.last_error_message}")
                
        except Exception as e:
            logger.error(f"❌ Failed to set webhook: {str(e)}")
            logger.error(f"   Webhook URL: {webhook_url}")
            logger.error(f"   Please check:")
            logger.error(f"   1. WEBHOOK_HOST is correct and DNS resolves: {WEBHOOK_HOST}")
            logger.error(f"   2. Server is accessible from internet (not localhost)")
            logger.error(f"   3. HTTPS is properly configured")
            raise
    else:
        # Delete webhook if exists (when switching from prod to dev)
        try:
            await bot.delete_webhook()
            logger.info("Webhook deleted (using polling mode)")
        except Exception as e:                                                                                                                                                                                                                                                                                                              
            logger.warning(f"Failed to delete webhook: {str(e)}")


async def on_shutdown(bot: Bot):
    """Actions to perform on bot shutdown."""
    logger.info("Bot is shutting down...")
                            
    # Close bot session
    await bot.session.close()
    
    # Close Redis connection
    from storage import user_storage
    await user_storage.close()
    
    logger.info("Bot shutdown complete")


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
    dp.include_router(documents.router)
    
    runner = None
    try:
        if BOT_MODE == 'prod':
            # Production mode: use webhook
            logger.info(f"Starting bot in PRODUCTION mode (webhook) on port {WEBHOOK_PORT}")
            
            # Run startup actions
            await on_startup(bot)
            
            # Create aiohttp application
            app = web.Application()
            
            # Register webhook handler
            webhook_requests_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=WEBHOOK_SECRET
            )
            webhook_requests_handler.register(app, path=WEBHOOK_PATH)
            
            # Setup application
            setup_application(app, dp, bot=bot)
            
            # Create runner
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host='0.0.0.0', port=WEBHOOK_PORT)
            await site.start()
            
            logger.info(f"Webhook server started on http://0.0.0.0:{WEBHOOK_PORT}{WEBHOOK_PATH}")
            logger.info(f"Webhook URL: {WEBHOOK_HOST}{WEBHOOK_PATH}")
            
            # Keep the server running
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
            finally:
                if runner:
                    await runner.cleanup()
                await on_shutdown(bot)
            
        else:
            # Development mode: use polling
            logger.info("Starting bot in DEVELOPMENT mode (polling)")
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                on_startup=on_startup,
                on_shutdown=on_shutdown
            )

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}", exc_info=True)
        if BOT_MODE == 'prod' and runner:
            try:
                await runner.cleanup()
            except:
                pass
        await on_shutdown(bot)
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

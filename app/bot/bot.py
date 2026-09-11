from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import router
from app.config import settings

if not settings.bot_token:
    raise RuntimeError("BOT_TOKEN is required to run the bot service")

bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = RedisStorage.from_url(settings.redis_url)
dp = Dispatcher(storage=storage)
dp.include_router(router)

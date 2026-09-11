from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.crud import get_or_create_user
from app.database import async_session

router = Router()

WELCOME = (
    "👋 Привет! Я слежу за ценами на OZON и присылаю уведомление, когда цена "
    "резко падает.\n\n"
    "<b>Команды:</b>\n"
    "/add — добавить товар в отслеживание\n"
    "/products — список отслеживаемых товаров\n"
    "/remove — удалить товар\n"
    "/pause — приостановить/возобновить мониторинг\n"
    "/status — статус системы"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(WELCOME)

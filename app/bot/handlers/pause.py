from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.crud import get_or_create_user, toggle_pause
from app.database import async_session

router = Router()


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        is_paused = await toggle_pause(session, user)

    if is_paused:
        await message.answer("⏸ Мониторинг приостановлен. Пришли /pause ещё раз, чтобы возобновить.")
    else:
        await message.answer("▶️ Мониторинг возобновлён.")

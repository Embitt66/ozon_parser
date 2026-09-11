from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.crud import get_or_create_user, list_products
from app.database import async_session

router = Router()


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        products = await list_products(session, user)

    active = [p for p in products if p.is_active]
    with_errors = [p for p in products if p.last_error]
    last_check = max((p.last_checked_at for p in products if p.last_checked_at), default=None)

    lines = [
        "<b>Статус мониторинга</b>",
        f"Мониторинг: {'⏸ на паузе' if user.is_paused else '▶️ работает'}",
        f"Товаров отслеживается: {len(products)} (активных: {len(active)})",
        f"Последняя проверка: {last_check.strftime('%Y-%m-%d %H:%M:%S') if last_check else '—'}",
    ]
    if with_errors:
        lines.append(f"⚠️ Товаров с ошибками при проверке: {len(with_errors)}")

    await message.answer("\n".join(lines))

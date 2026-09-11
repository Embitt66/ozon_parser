from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import confirm_remove_keyboard, product_detail_keyboard, products_keyboard
from app.crud import get_or_create_user, get_product, list_products, remove_product
from app.database import async_session
from app.services.notifier import format_price

router = Router()


def _product_text(p) -> str:
    lines = [f"<b>{p.title}</b>", f"Статус: {'▶️ активен' if p.is_active else '⏸ на паузе'}"]
    if p.current_price is not None:
        lines.append(f"Текущая цена: {format_price(p.current_price)}")
    if p.previous_price is not None:
        lines.append(f"Предыдущая цена: {format_price(p.previous_price)}")
    if p.min_price_threshold:
        lines.append(f"Порог цены: {format_price(p.min_price_threshold)}")
    if p.percent_threshold:
        lines.append(f"Порог снижения: {p.percent_threshold:.0f}%")
    lines.append(f"Последняя проверка: {p.last_checked_at.strftime('%Y-%m-%d %H:%M') if p.last_checked_at else '—'}")
    lines.append(f"Ссылка: {p.ozon_url}")
    return "\n".join(lines)


@router.message(Command("products"))
async def cmd_products(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        products = await list_products(session, user)

    if not products:
        await message.answer("Список пуст. Добавь товар командой /add")
        return

    await message.answer("Отслеживаемые товары:", reply_markup=products_keyboard(products))


@router.message(Command("remove"))
async def cmd_remove(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        products = await list_products(session, user)

    if not products:
        await message.answer("Список пуст, удалять нечего.")
        return

    await message.answer("Выбери товар для удаления:", reply_markup=products_keyboard(products))


@router.callback_query(F.data.startswith("product:"))
async def show_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        product = await get_product(session, product_id, user)

    await callback.answer()
    if product is None:
        await callback.message.edit_text("Товар не найден.")
        return

    await callback.message.edit_text(_product_text(product), reply_markup=product_detail_keyboard(product))


@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        products = await list_products(session, user)

    await callback.answer()
    if not products:
        await callback.message.edit_text("Список пуст. Добавь товар командой /add")
        return
    await callback.message.edit_text("Отслеживаемые товары:", reply_markup=products_keyboard(products))


@router.callback_query(F.data.startswith("remove:"))
async def ask_remove(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await callback.message.edit_text(
        "Удалить товар из отслеживания?", reply_markup=confirm_remove_keyboard(product_id)
    )


@router.callback_query(F.data.startswith("remove_confirm:"))
async def do_remove(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        product = await get_product(session, product_id, user)
        if product:
            await remove_product(session, product)

    await callback.answer("Удалено")
    await back_to_list(callback)

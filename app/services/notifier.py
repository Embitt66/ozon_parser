from aiogram import Bot

from app.models import Product


def format_price(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


async def send_price_drop_alert(
    bot: Bot, telegram_id: int, product: Product, old_price: float, new_price: float
) -> None:
    drop_percent = (old_price - new_price) / old_price * 100 if old_price else 0
    text = (
        "📉 <b>Цена снизилась!</b>\n\n"
        f"Товар: {product.title}\n"
        f"Было: {format_price(old_price)}\n"
        f"Стало: {format_price(new_price)}\n"
        f"Снижение: {drop_percent:.1f}%\n\n"
        f"Ссылка: {product.ozon_url}"
    )
    await bot.send_message(telegram_id, text)

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.models import Product


def threshold_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Минимальная цена", callback_data="thr:min")],
            [InlineKeyboardButton(text="📉 Процент снижения", callback_data="thr:percent")],
            [InlineKeyboardButton(text="✅ Оба условия", callback_data="thr:both")],
            [
                InlineKeyboardButton(
                    text=f"⚡ По умолчанию (-{settings.default_percent_threshold:.0f}%)",
                    callback_data="thr:default",
                )
            ],
        ]
    )


def products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        status = "⏸" if not p.is_active else "▶️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {p.title[:40]}",
                    callback_data=f"product:{p.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Пусто", callback_data="noop")]])


def product_detail_keyboard(product: Product) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"remove:{product.id}")],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data="back_to_list")],
        ]
    )


def confirm_remove_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"remove_confirm:{product_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_list"),
            ]
        ]
    )

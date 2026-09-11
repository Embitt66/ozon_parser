"""Background price-monitoring loop.

Implements the algorithm from the spec:

    fetch price -> compare with previous price -> check notify conditions
    -> if a sharp drop is detected -> re-check the price to confirm it
    -> send a Telegram notification

Runs as a single asyncio task with a bounded semaphore so many products can be
checked concurrently without hammering OZON (and risking anti-bot blocks).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app import crud
from app.config import settings
from app.database import async_session
from app.models import Product, User
from app.services.notifier import send_price_drop_alert
from app.services.parser_client import ParseError, get_product_data

logger = logging.getLogger(__name__)


def _is_triggered(product: Product, old_price: float | None, new_price: float) -> bool:
    if old_price is None:
        return False
    if product.min_price_threshold is not None and new_price <= product.min_price_threshold:
        return True
    if product.percent_threshold is not None and old_price > 0:
        drop_percent = (old_price - new_price) / old_price * 100
        if drop_percent >= product.percent_threshold:
            return True
    return False


async def _check_product(bot: Bot, semaphore: asyncio.Semaphore, product_id: int) -> None:
    async with semaphore:
        async with async_session() as session:
            product = await session.get(Product, product_id)
            if product is None or not product.is_active:
                return

            try:
                data = await get_product_data(product.ozon_url)
            except (ParseError, Exception) as exc:  # noqa: BLE001
                logger.warning("Failed to check product %s: %s", product.id, exc)
                await crud.record_check(session, product, None, str(exc))
                return

            old_price = product.current_price
            await crud.record_check(session, product, data.price, None)

            if not _is_triggered(product, old_price, data.price):
                return

            logger.info("Potential price drop for product %s, confirming...", product.id)
            await asyncio.sleep(settings.confirm_delay_seconds)

            try:
                confirm_data = await get_product_data(product.ozon_url)
            except (ParseError, Exception) as exc:  # noqa: BLE001
                logger.warning("Confirmation check failed for product %s: %s", product.id, exc)
                return

            if not _is_triggered(product, old_price, confirm_data.price):
                logger.info("Price drop for product %s not confirmed on re-check", product.id)
                return

            user = await session.get(User, product.user_id)
            if user is None:
                return

            await send_price_drop_alert(bot, user.telegram_id, product, old_price, confirm_data.price)
            product.current_price = confirm_data.price
            await session.commit()


async def run_scheduler(bot: Bot) -> None:
    semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
    logger.info("Price monitor scheduler started")
    while True:
        try:
            async with async_session() as session:
                products = await crud.due_products(session)
                product_ids = [p.id for p in products]

            if product_ids:
                await asyncio.gather(
                    *(_check_product(bot, semaphore, pid) for pid in product_ids),
                    return_exceptions=True,
                )
        except Exception:  # noqa: BLE001
            logger.exception("Scheduler tick failed")

        await asyncio.sleep(settings.scheduler_tick_seconds)

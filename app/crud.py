from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceHistory, Product, User


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def toggle_pause(session: AsyncSession, user: User) -> bool:
    user.is_paused = not user.is_paused
    await session.commit()
    return user.is_paused


async def add_product(
    session: AsyncSession,
    user: User,
    title: str,
    ozon_url: str,
    ozon_id: str,
    current_price: float,
    min_price_threshold: float | None,
    percent_threshold: float | None,
    priority: bool,
    check_interval_seconds: int,
) -> Product:
    product = Product(
        user_id=user.id,
        title=title,
        ozon_url=ozon_url,
        ozon_id=ozon_id,
        current_price=current_price,
        previous_price=current_price,
        min_price_threshold=min_price_threshold,
        percent_threshold=percent_threshold,
        priority=priority,
        check_interval_seconds=check_interval_seconds,
        last_checked_at=datetime.now(timezone.utc),
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    session.add(PriceHistory(product_id=product.id, price=current_price))
    await session.commit()
    return product


async def list_products(session: AsyncSession, user: User) -> list[Product]:
    result = await session.execute(
        select(Product).where(Product.user_id == user.id).order_by(Product.created_at.desc())
    )
    return list(result.scalars().all())


async def get_product(session: AsyncSession, product_id: int, user: User) -> Product | None:
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.user_id == user.id)
    )
    return result.scalar_one_or_none()


async def remove_product(session: AsyncSession, product: Product) -> None:
    await session.delete(product)
    await session.commit()


async def due_products(session: AsyncSession) -> list[Product]:
    """Products belonging to active, non-paused users whose check interval has elapsed."""
    result = await session.execute(
        select(Product).join(User).where(Product.is_active.is_(True), User.is_paused.is_(False))
    )
    products = result.scalars().all()
    now = datetime.now(timezone.utc)
    due = []
    for p in products:
        if p.last_checked_at is None:
            due.append(p)
            continue
        last = p.last_checked_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() >= p.check_interval_seconds:
            due.append(p)
    return due


async def record_check(
    session: AsyncSession, product: Product, new_price: float | None, error: str | None
) -> None:
    product.last_checked_at = datetime.now(timezone.utc)
    if error is not None:
        product.last_error = error
        await session.commit()
        return

    product.last_error = None
    product.previous_price = product.current_price
    product.current_price = new_price
    await session.commit()
    session.add(PriceHistory(product_id=product.id, price=new_price))
    await session.commit()


async def counts(session: AsyncSession) -> dict:
    total_products = (await session.execute(select(Product))).scalars().all()
    total_users = (await session.execute(select(User))).scalars().all()
    return {
        "products": len(total_products),
        "active_products": len([p for p in total_products if p.is_active]),
        "users": len(total_users),
        "paused_users": len([u for u in total_users if u.is_paused]),
    }

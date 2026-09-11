from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import threshold_type_keyboard
from app.bot.states import AddProduct
from app.config import settings
from app.crud import add_product, get_or_create_user
from app.database import async_session
from app.services.notifier import format_price
from app.services.parser_client import ParseError, get_product_data

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddProduct.waiting_for_url)
    await message.answer("Пришли ссылку на товар OZON (или его ID).")


@router.message(AddProduct.waiting_for_url)
async def process_url(message: Message, state: FSMContext) -> None:
    url = (message.text or "").strip()
    status = await message.answer("🔎 Проверяю товар...")

    try:
        data = await get_product_data(url)
    except ParseError as exc:
        await status.edit_text(f"❌ {exc}\nПопробуй прислать ссылку ещё раз.")
        return
    except Exception:  # noqa: BLE001
        await status.edit_text(
            "❌ Не удалось получить данные о товаре. OZON мог временно заблокировать запрос — "
            "попробуй ещё раз чуть позже, либо пришли другую ссылку."
        )
        return

    await state.update_data(
        title=data.title,
        ozon_url=data.url,
        ozon_id=data.ozon_id,
        price=data.price,
    )
    await state.set_state(AddProduct.choosing_threshold_type)
    await status.edit_text(
        f"✅ Найден товар:\n<b>{data.title}</b>\nТекущая цена: {format_price(data.price)}\n\n"
        "При каком условии присылать уведомление?",
        reply_markup=threshold_type_keyboard(),
    )


@router.callback_query(AddProduct.choosing_threshold_type, F.data.startswith("thr:"))
async def choose_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    await callback.answer()

    if choice == "default":
        await state.update_data(percent_threshold=settings.default_percent_threshold, min_price_threshold=None)
        await finalize_product(callback.message, state)
        return

    if choice == "min":
        await state.update_data(need_percent_after_min=False)
        await state.set_state(AddProduct.waiting_for_min_price)
        await callback.message.edit_text("Укажи минимальную цену в рублях, при достижении которой прислать уведомление:")
        return

    if choice == "percent":
        await state.set_state(AddProduct.waiting_for_percent)
        await callback.message.edit_text("Укажи процент снижения цены, при котором прислать уведомление (например 20):")
        return

    if choice == "both":
        await state.update_data(need_percent_after_min=True)
        await state.set_state(AddProduct.waiting_for_min_price)
        await callback.message.edit_text("Укажи минимальную цену в рублях:")


def _parse_number(text: str) -> float | None:
    cleaned = (text or "").replace(",", ".").replace(" ", "").replace("₽", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


@router.message(AddProduct.waiting_for_min_price)
async def process_min_price(message: Message, state: FSMContext) -> None:
    value = _parse_number(message.text)
    if value is None or value <= 0:
        await message.answer("Пришли число, например: 7000")
        return

    data = await state.get_data()
    await state.update_data(min_price_threshold=value)

    if data.get("need_percent_after_min"):
        await state.set_state(AddProduct.waiting_for_percent)
        await message.answer("Теперь укажи процент снижения цены (например 20):")
        return

    await state.update_data(percent_threshold=None)
    await finalize_product(message, state)


@router.message(AddProduct.waiting_for_percent)
async def process_percent(message: Message, state: FSMContext) -> None:
    value = _parse_number(message.text)
    if value is None or not (0 < value <= 100):
        await message.answer("Пришли процент от 1 до 100, например: 20")
        return

    await state.update_data(percent_threshold=value)
    data = await state.get_data()
    if "min_price_threshold" not in data:
        await state.update_data(min_price_threshold=None)
    await finalize_product(message, state)


async def finalize_product(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with async_session() as session:
        user = await get_or_create_user(session, message.chat.id, None)
        product = await add_product(
            session,
            user=user,
            title=data["title"],
            ozon_url=data["ozon_url"],
            ozon_id=data["ozon_id"],
            current_price=data["price"],
            min_price_threshold=data.get("min_price_threshold"),
            percent_threshold=data.get("percent_threshold"),
            priority=False,
            check_interval_seconds=settings.default_check_interval_seconds,
        )

    await state.clear()

    conditions = []
    if product.min_price_threshold:
        conditions.append(f"цена ≤ {format_price(product.min_price_threshold)}")
    if product.percent_threshold:
        conditions.append(f"снижение ≥ {product.percent_threshold:.0f}%")

    await message.answer(
        f"✅ Товар добавлен в отслеживание!\n<b>{product.title}</b>\n"
        f"Условие уведомления: {', '.join(conditions) if conditions else 'по умолчанию'}"
    )

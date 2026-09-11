"""OZON product parsing.

OZON has no public API for looking up arbitrary catalog prices (the Seller API only
exposes a seller's own products), so this module scrapes the storefront:

1. "api" strategy - calls OZON's unofficial internal JSON endpoint
   (api.ozon.ru/composer-api.bx/page/json/v2) that the website itself uses to render
   a product page. Fast and cheap, but undocumented and can change or get blocked by
   anti-bot protection at any time.
2. "selenium" strategy - drives a real (headless) Chrome browser to render the page
   and extracts the price from the DOM with BeautifulSoup. Slower but far more
   resilient to anti-bot checks and markup that requires JS.

`get_product_data(mode="auto")` tries the API first and transparently falls back to
Selenium if it fails, unless a specific mode is forced.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class ParseError(Exception):
    pass


@dataclass
class ProductData:
    ozon_id: str
    title: str
    price: float
    url: str


def extract_ozon_id(url_or_id: str) -> tuple[str, str]:
    """Returns (ozon_id, normalized_url). Accepts a full OZON URL or a bare numeric id."""
    raw = url_or_id.strip()
    if raw.isdigit():
        return raw, f"https://www.ozon.ru/product/{raw}/"

    parsed = urlparse(raw if raw.startswith("http") else f"https://{raw}")
    if "ozon.ru" not in parsed.netloc and "ozon.by" not in parsed.netloc:
        raise ParseError("Ссылка не похожа на ozon.ru")

    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        raise ParseError("Не удалось разобрать ссылку OZON")

    # slug is typically ".../product/<name>-<digits>/"
    slug = segments[-1]
    match = re.search(r"(\d{4,})$", slug)
    if not match:
        raise ParseError("Не удалось найти ID товара в ссылке")

    ozon_id = match.group(1)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return ozon_id, normalized


async def _fetch_via_api(url: str) -> ProductData:
    ozon_id, normalized_url = extract_ozon_id(url)
    path = urlparse(normalized_url).path

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": normalized_url,
    }
    endpoint = "https://api.ozon.ru/composer-api.bx/page/json/v2"

    async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:
        resp = await client.get(endpoint, params={"url": path})
        resp.raise_for_status()
        data = resp.json()

    widget_states: dict = data.get("widgetStates", {})

    title = None
    seo = data.get("seo") or {}
    if isinstance(seo, dict):
        title = seo.get("header") or seo.get("title")

    price = None
    for key, value in widget_states.items():
        if not isinstance(value, str):
            continue
        if not key.startswith(("webPrice", "webSingleProductScore", "webProductMainInfo")):
            continue
        try:
            payload = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            continue

        if title is None:
            title = payload.get("title") or payload.get("name")

        candidate = payload.get("price") or payload.get("cardPrice") or payload.get("finalPrice")
        if candidate:
            price = _parse_price(candidate)
            if price is not None:
                break

    if price is None or title is None:
        raise ParseError("API OZON не вернул цену/название (возможно, изменился формат ответа)")

    return ProductData(ozon_id=ozon_id, title=title, price=price, url=normalized_url)


def _parse_price(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            return float(digits)
    return None


def _fetch_via_selenium_sync(url: str) -> ProductData:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    ozon_id, normalized_url = extract_ozon_id(url)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        if settings.selenium_remote_url:
            driver = webdriver.Remote(command_executor=settings.selenium_remote_url, options=options)
        else:
            driver = webdriver.Chrome(options=options)

        driver.set_page_load_timeout(20)
        driver.get(normalized_url)

        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-widget='webPrice']"))
            )
        except TimeoutException:
            pass  # fall through and try to parse whatever loaded

        html = driver.page_source
    except WebDriverException as exc:
        raise ParseError(f"Selenium ошибка: {exc}") from exc
    finally:
        if driver is not None:
            driver.quit()

    soup = BeautifulSoup(html, "lxml")

    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else None

    price = None
    price_widget = soup.select_one("[data-widget='webPrice']")
    if price_widget:
        text = price_widget.get_text(" ", strip=True)
        match = re.search(r"[\d\s]{3,}\s*₽", text)
        if match:
            price = _parse_price(match.group(0))

    if price is None:
        # broad fallback: first ruble price anywhere on the page
        match = re.search(r"[\d][\d\s]{2,}\s*₽", soup.get_text(" ", strip=True))
        if match:
            price = _parse_price(match.group(0))

    if price is None or title is None:
        raise ParseError("Не удалось извлечь цену/название со страницы OZON")

    return ProductData(ozon_id=ozon_id, title=title, price=price, url=normalized_url)


async def _fetch_via_selenium(url: str) -> ProductData:
    import asyncio

    return await asyncio.to_thread(_fetch_via_selenium_sync, url)


async def get_product_data(url: str, mode: str | None = None) -> ProductData:
    mode = mode or settings.parser_mode

    if mode == "selenium":
        return await _fetch_via_selenium(url)

    if mode == "api":
        return await _fetch_via_api(url)

    # auto: try API first, fall back to selenium
    try:
        return await _fetch_via_api(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OZON API parse failed (%s), falling back to selenium", exc)
        return await _fetch_via_selenium(url)

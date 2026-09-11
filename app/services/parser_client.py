"""Product-data lookup used by the bot/scheduler.

If PARSER_SERVICE_URL is configured, delegates over HTTP to a standalone
parser service (see app/parser_api.py, run via app.parser_main) - meant to run
on a separate machine with a "clean" IP that OZON doesn't anti-bot-block,
while this process (bot + scheduler + DB) runs wherever Telegram is reachable
(e.g. behind a VPN). Otherwise falls back to parsing locally, same as before.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.services.ozon_parser import ParseError, ProductData
from app.services.ozon_parser import get_product_data as _get_product_data_local


async def get_product_data(url: str, mode: str | None = None) -> ProductData:
    if settings.parser_service_url:
        return await _get_product_data_remote(url, mode)
    return await _get_product_data_local(url, mode=mode)


async def _get_product_data_remote(url: str, mode: str | None) -> ProductData:
    endpoint = settings.parser_service_url.rstrip("/") + "/parse"
    headers = {}
    if settings.parser_api_key:
        headers["X-API-Key"] = settings.parser_api_key

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json={"query": url, "mode": mode}, headers=headers)
    except httpx.HTTPError as exc:
        raise ParseError(f"Парсер-сервис недоступен: {exc}") from exc

    if resp.status_code == 422:
        detail = "Не удалось разобрать товар"
        try:
            detail = resp.json().get("detail", detail)
        except ValueError:
            pass
        raise ParseError(detail)

    if resp.status_code != 200:
        raise ParseError(f"Парсер-сервис вернул ошибку {resp.status_code}")

    data = resp.json()
    return ProductData(ozon_id=data["ozon_id"], title=data["title"], price=data["price"], url=data["url"])

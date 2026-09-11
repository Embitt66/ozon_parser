"""Standalone parser HTTP service.

Wraps app.services.ozon_parser behind a small FastAPI app so it can run on
its own machine (e.g. one without a VPN, where OZON isn't anti-bot-blocking
requests) while the bot/DB run elsewhere. See app/services/parser_client.py
for the caller side, and app/parser_main.py for the entrypoint.
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.ozon_parser import ParseError, get_product_data

app = FastAPI(title="OZON Parser Service")


class ParseRequest(BaseModel):
    query: str
    mode: str | None = None


class ParseResponse(BaseModel):
    ozon_id: str
    title: str
    price: float
    url: str


def _check_api_key(x_api_key: str | None) -> None:
    if settings.parser_api_key and x_api_key != settings.parser_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/parse", response_model=ParseResponse)
async def parse(request: ParseRequest, x_api_key: str | None = Header(default=None)) -> ParseResponse:
    _check_api_key(x_api_key)

    try:
        data = await get_product_data(request.query, mode=request.mode)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Unexpected parser error: {exc}") from exc

    return ParseResponse(ozon_id=data.ozon_id, title=data.title, price=data.price, url=data.url)

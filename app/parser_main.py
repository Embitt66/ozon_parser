"""Entrypoint for the standalone parser service (no bot, no DB required).

Run this on the machine that should talk to OZON directly (e.g. one without
a VPN). It only needs PARSER_MODE / SELENIUM_REMOTE_URL / PARSER_API_KEY /
WEB_HOST / WEB_PORT configured - BOT_TOKEN and DATABASE_URL are unused here.
"""

import logging

import uvicorn

from app.config import settings
from app.parser_api import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.web_host, port=settings.web_port, log_level="info")

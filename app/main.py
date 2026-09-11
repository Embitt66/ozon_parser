import asyncio
import logging

import uvicorn

from app.bot.bot import bot, dp
from app.config import settings
from app.database import init_db
from app.scheduler.monitor_loop import run_scheduler
from app.web import app as web_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    server = uvicorn.Server(
        uvicorn.Config(web_app, host=settings.web_host, port=settings.web_port, log_level="warning")
    )

    await asyncio.gather(
        dp.start_polling(bot),
        run_scheduler(bot),
        server.serve(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down")

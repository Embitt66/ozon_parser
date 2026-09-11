from fastapi import FastAPI

from app.crud import counts
from app.database import async_session

app = FastAPI(title="OZON Price Monitor")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict:
    async with async_session() as session:
        return await counts(session)

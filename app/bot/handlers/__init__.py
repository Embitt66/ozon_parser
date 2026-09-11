from aiogram import Router

from app.bot.handlers import add_product, pause, products, start, status

router = Router()
router.include_router(start.router)
router.include_router(add_product.router)
router.include_router(products.router)
router.include_router(pause.router)
router.include_router(status.router)

from aiogram import Router

from bot.handlers import admin, buyer


def setup_routers() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(buyer.router)
    return router

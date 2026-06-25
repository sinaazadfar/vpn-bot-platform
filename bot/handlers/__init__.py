from aiogram import Router

from bot.handlers import admin, admin_users, buyer


def setup_routers() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(admin_users.router)
    router.include_router(buyer.router)
    return router

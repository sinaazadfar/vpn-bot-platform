from aiogram import Router

from bot.handlers import admin, admin_features, admin_payments, admin_users, buyer, buyer_features


def setup_routers() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(admin_features.router)
    router.include_router(admin_payments.router)
    router.include_router(admin_users.router)
    router.include_router(buyer.router)
    router.include_router(buyer_features.router)
    return router

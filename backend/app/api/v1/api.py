from fastapi import APIRouter

from app.api.v1 import auth, health, kitchen, menu, orders, payments, restaurants, tables, uploads, users

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(restaurants.router)
api_router.include_router(users.router)
api_router.include_router(menu.router)
api_router.include_router(tables.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(kitchen.router)
api_router.include_router(uploads.router)
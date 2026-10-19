from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    customers,
    expenses,
    health,
    inventory,
    kitchen,
    menu,
    notifications,
    orders,
    payments,
    platform,
    print_agent,
    printers,
    public,
    reports,
    restaurants,
    search,
    subscription,
    tables,
    telegram,
    uploads,
    users,
)

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
api_router.include_router(inventory.router)
api_router.include_router(expenses.router)
api_router.include_router(reports.router)
api_router.include_router(customers.router)
api_router.include_router(public.router)
api_router.include_router(telegram.router)
api_router.include_router(notifications.router)
api_router.include_router(audit.router)
api_router.include_router(search.router)
api_router.include_router(printers.router)
api_router.include_router(subscription.router)
api_router.include_router(platform.router)
api_router.include_router(print_agent.router)

from fastapi import APIRouter
from app.controllers.web.admin_controller import router as admin_router

web_router = APIRouter()
web_router.include_router(admin_router)

__all__ = ["web_router", "admin_router"]

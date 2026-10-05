from fastapi import APIRouter
from app.api.ai_assistant import router as ai_router
from app.controllers.api.rag_controller import router as rag_router

api_router = APIRouter()
api_router.include_router(ai_router)
api_router.include_router(rag_router)

__all__ = ["api_router", "ai_router", "rag_router"]

from app.api.ai_assistant import router as ai_router
from app.api.rag_internal import router as rag_router

__all__ = [
    "ai_router",
    "rag_router",
]

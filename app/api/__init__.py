from app.controllers.api.ai_controller import router as ai_router

api_router = APIRouter()
api_router.include_router(ai_router)

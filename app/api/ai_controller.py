import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    PCBuilderCompatibilityRequest,
    PCBuilderCompatibilityResponse
)
from app.services.ai_service import ai_sales_assistant
from app.services.pc_builder_service import pc_builder_service

router = APIRouter(prefix="/ai", tags=["AI Sales Assistant"])

@router.post("/chat", response_model=AIChatResponse)
def ai_chat_consultation(request: AIChatRequest, db: Session = Depends(get_db)):
    """Tư vấn bán hàng thông thường (chờ hoàn tất câu trả lời)."""
    return ai_sales_assistant.process_consultation(db, request)

@router.post("/chat/stream")
def ai_chat_consultation_stream(request: AIChatRequest, db: Session = Depends(get_db)):
    """Tư vấn bán hàng thời gian thực Server-Sent Events (SSE) gõ từng chữ."""
    def event_generator():
        for event in ai_sales_assistant.process_consultation_stream(db, request):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/pc-builder-check", response_model=PCBuilderCompatibilityResponse)
def check_pc_compatibility(req: PCBuilderCompatibilityRequest, db: Session = Depends(get_db)):
    """Kiểm tra tính tương thích giữa các linh kiện trong dàn PC đã chọn."""
    return pc_builder_service.check_compatibility(db, req)

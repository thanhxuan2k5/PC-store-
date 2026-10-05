from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.views import templates
from app.models.internal_doc import InternalDoc

router = APIRouter(prefix="/admin", tags=["Admin RAG Web Controller"])

@router.get("/dashboard")
def admin_dashboard(request: Request):
    """Chuyển hướng về trang Tra cứu quy định nội bộ"""
    return RedirectResponse(url="/admin/rag")

@router.get("/rag")
def admin_rag_page(request: Request, db: Session = Depends(get_db)):
    """Trang quản trị Không gian tri thức nội bộ"""
    docs = db.query(InternalDoc).order_by(desc(InternalDoc.created_at)).all()
    raw_spaces = db.query(InternalDoc.category).distinct().all()
    spaces = [s[0] for s in raw_spaces if s[0]]
    default_spaces = ["Chính sách bảo hành", "Tiêu chuẩn kỹ thuật", "Chính sách nội bộ", "Quy trình vận hành"]
    for ds in default_spaces:
        if ds not in spaces:
            spaces.append(ds)

    return templates.TemplateResponse(
        "admin/rag_internal.html",
        {
            "request": request,
            "docs": docs,
            "spaces": spaces,
            "active_page": "rag"
        }
    )

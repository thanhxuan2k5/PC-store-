from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AIChatMessage(BaseModel):
    role: str
    content: str

class AIChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[AIChatMessage]] = []
    budget: Optional[float] = None
    category_slug: Optional[str] = None

class RecommendedProductItem(BaseModel):
    id: int
    name: str
    slug: str
    brand: str
    promo_price: float
    original_price: float
    thumbnail: Optional[str] = None
    specs: Dict[str, Any] = {}
    reason: str

class AIChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = "consultation"
    recommended_products: List[RecommendedProductItem] = []
    suggested_questions: List[str] = []

class PCBuilderCompatibilityRequest(BaseModel):
    cpu_id: Optional[int] = None
    mainboard_id: Optional[int] = None
    ram_id: Optional[int] = None
    vga_id: Optional[int] = None
    psu_id: Optional[int] = None
    case_id: Optional[int] = None
    cooler_id: Optional[int] = None
    storage_id: Optional[int] = None

class PCBuilderCompatibilityResponse(BaseModel):
    is_compatible: bool
    issues: List[str] = []
    warnings: List[str] = []
    estimated_wattage: int = 0
    recommended_psu_wattage: int = 500
    total_price: float = 0.0

# Schema riêng cho AI Auto PC Builder
class AIAutoPCBuildRequest(BaseModel):
    budget: float = Field(..., description="Ngân sách dự kiến (VND)")
    purpose: str = Field("gaming", description="Mục đích sử dụng: 'gaming', 'do_hoa', 'van_phong'")
    notes: Optional[str] = None

class AIAutoPCBuildResponse(BaseModel):
    total_price: float
    target_budget: float
    is_compatible: bool
    summary_advice: str
    parts: Dict[str, Optional[RecommendedProductItem]] = {}

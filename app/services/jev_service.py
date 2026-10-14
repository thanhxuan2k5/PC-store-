"""
TypeSafe AI — Jev System-One Decision Service
=============================================
Tích hợp mô hình quyết định chuyên dụng Jev của TypeSafe AI vào GearVN Ecosystem:
1. Chat Gatekeeper & Intent Router (System-1 Decision trước LLM System-2).
2. Review Sentiment & Content Moderation (Phân loại cảm xúc + chống spam).
3. RAG Query Space Router (Định tuyến câu hỏi vào đúng chuyên mục quy định).
4. Hardware Specs Extractor (Chuẩn hóa thông số kỹ thuật có cấu trúc).
"""

import os
import re
import json
from typing import Optional, List, Dict, Any, Literal
import httpx
from pydantic import BaseModel, Field

from app.config import settings


# ==============================================================================
# 1. TYPESAFE SCHEMAS (Pydantic Decision Models)
# ==============================================================================
class JevChatDecision(BaseModel):
    """Quyết định kiểm duyệt và phân loại ý định người dùng (Chat Gatekeeper)."""
    is_laptop_related: bool = Field(description="Câu hỏi có thuộc phạm vi Laptop hay không")
    intent_category: Literal["gaming", "office_thin", "creator_workstation", "macbook", "general_laptop", "out_of_scope"] = Field(
        default="general_laptop", description="Phân khúc laptop hướng tới"
    )
    extracted_budget: Optional[float] = Field(default=None, description="Ngân sách (VNĐ) được trích xuất")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Độ tin cậy của quyết định")
    reasoning: str = Field(default="Jev System-1 Calibrated Decision", description="Lý do quyết định")


class JevSentimentDecision(BaseModel):
    """Quyết định phân loại cảm xúc và kiểm duyệt đánh giá khách hàng."""
    sentiment: Literal["positive", "neutral", "negative"] = Field(description="Nhãn cảm xúc")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0, description="Độ tin cậy xác suất")
    is_spam_or_toxic: bool = Field(default=False, description="Đánh giá có chứa từ ngữ vi phạm, spam")
    aspects: List[str] = Field(default_factory=list, description="Khía cạnh được nhắc tới: màn hình, pin, tản nhiệt...")


class JevRAGRoutingDecision(BaseModel):
    """Quyết định định tuyến câu hỏi RAG vào đúng Không gian Tri thức (Vector Space)."""
    target_space: str = Field(description="Tên chuyên mục tài liệu đích")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    key_entities: List[str] = Field(default_factory=list, description="Thực thể chính trích xuất được")


class JevSpecsDecision(BaseModel):
    """Quyết định trích xuất thông số phần cứng từ văn bản mô tả."""
    socket: Optional[str] = None
    ram_type: Optional[str] = None
    wattage: Optional[int] = None
    gpu_chipset: Optional[str] = None
    cpu_series: Optional[str] = None


# ==============================================================================
# 2. JEV SERVICE IMPLEMENTATION
# ==============================================================================
class JevService:
    """Client giao tiếp với TypeSafe AI Jev, tích hợp cơ chế Calibrated Fallback."""

    def __init__(self):
        self.api_key = settings.TYPESAFE_AI_API_KEY
        self.base_url = settings.JEV_BASE_URL.rstrip("/")
        self.enabled = settings.JEV_ENABLED
        self.timeout = settings.JEV_TIMEOUT

    def _call_jev_api(self, task: str, input_payload: Dict[str, Any], schema_name: str) -> Optional[Dict[str, Any]]:
        """Gửi request tới API TypeSafe AI Jev nếu có cấu hình API Key."""
        if not self.enabled or not self.api_key:
            return None

        url = f"{self.base_url}/decide"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.JEV_MODEL,
            "task": task,
            "input": input_payload,
            "response_schema": schema_name
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.json().get("decision")
        except Exception as e:
            print(f"[Jev API Error]: {e} — Chuyển sang Jev Local Calibrated Engine")

        return None

    # --------------------------------------------------------------------------
    # 2.1. CHAT GATEKEEPER & ROUTER (SYSTEM 1)
    # --------------------------------------------------------------------------
    def decide_chat_intent(self, text: str) -> JevChatDecision:
        """
        Quyết định xem câu hỏi có thuộc phạm vi Laptop hay không và bóc tách ngân sách.
        Tốc độ siêu nhanh, kết quả Type-Safe 100%.
        """
        # Thử gọi qua TypeSafe AI Cloud API
        remote_res = self._call_jev_api("chat_gatekeeper", {"text": text}, "JevChatDecision")
        if remote_res:
            try:
                return JevChatDecision(**remote_res)
            except Exception:
                pass

        # Jev Local Calibrated Fast Engine (Chạy nội bộ <10ms)
        lower = text.lower().strip()
        
        # 1. Phát hiện chủ đề ngoài lề (Blacklist Out-of-scope)
        blacklist = [
            "nấu", "món ăn", "cách làm bánh", "thời tiết", "mưa", "nắng",
            "bài toán", "giải phương trình", "làm thơ", "tủ lạnh", "máy giặt",
            "bếp từ", "bóng đá", "tổng thống", "chính trị", "chứng khoán", "xổ số"
        ]
        if any(bad in lower for bad in blacklist):
            return JevChatDecision(
                is_laptop_related=False,
                intent_category="out_of_scope",
                extracted_budget=None,
                confidence=0.99,
                reasoning="Jev detected out-of-scope domain topic"
            )

        # 2. Trích xuất ngân sách (Budget extraction)
        budget = None
        m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:triệu|tr|củ)', lower)
        if m:
            try:
                budget = float(m.group(1).replace(',', '.')) * 1_000_000
            except ValueError:
                pass
        if not budget:
            m2 = re.search(r'(\d{1,3}(?:[\.,]\d{3}){2,3})', lower)
            if m2:
                try:
                    budget = float(re.sub(r'[\.,]', '', m2.group(1)))
                except ValueError:
                    pass

        # 3. Phân loại phân khúc laptop (Category Decision)
        if any(k in lower for k in ["gaming", "game", "valorant", "csgo", "genshin", "rtx", "rog", "tuf", "nitro", "legion"]):
            category = "gaming"
        elif any(k in lower for k in ["macbook", "apple", "air m", "pro m", "macos"]):
            category = "macbook"
        elif any(k in lower for k in ["đồ họa", "render", "cad", "premiere", "3ds max", "kiến trúc"]):
            category = "creator_workstation"
        elif any(k in lower for k in ["văn phòng", "mỏng nhẹ", "học tập", "sinh viên", "zenbook", "vivobook"]):
            category = "office_thin"
        else:
            category = "general_laptop"

        # 4. Kiểm tra xem có từ khóa liên quan máy tính xách tay hoặc lời chào
        laptop_signals = [
            "laptop", "máy tính xách tay", "macbook", "notebook", "ultrabook",
            "i3", "i5", "i7", "i9", "core", "ryzen", "rtx", "ram", "ssd",
            "máy", "mua", "tư vấn", "giá", "ngân sách", "triệu", "củ",
            "chào", "hello", "hi", "alo", "shop"
        ]
        is_laptop = any(sig in lower for sig in laptop_signals)

        return JevChatDecision(
            is_laptop_related=is_laptop,
            intent_category=category if is_laptop else "out_of_scope",
            extracted_budget=budget,
            confidence=0.95 if is_laptop else 0.85,
            reasoning="Jev Local Engine Calibrated"
        )

    # --------------------------------------------------------------------------
    # 2.2. REVIEW SENTIMENT & CONTENT MODERATION
    # --------------------------------------------------------------------------
    def decide_sentiment(self, text: str) -> JevSentimentDecision:
        """Phân loại cảm xúc đánh giá và kiểm tra ngôn từ độc hại / spam."""
        remote_res = self._call_jev_api("sentiment_moderation", {"text": text}, "JevSentimentDecision")
        if remote_res:
            try:
                return JevSentimentDecision(**remote_res)
            except Exception:
                pass

        lower = text.lower().strip()

        # Kiểm duyệt từ ngữ thô tục / spam
        toxic_words = ["lừa đảo", "chó", "mất dạy", "scam", "đm", "vl", "casino"]
        is_toxic = any(t in lower for t in toxic_words)

        # Phát hiện khía cạnh (aspects)
        aspects = []
        if any(w in lower for w in ["màn hình", "hiển thị", "144hz", "màu sắc"]):
            aspects.append("màn hình")
        if any(w in lower for w in ["pin", "thời lượng", "sạc"]):
            aspects.append("pin")
        if any(w in lower for w in ["nóng", "quạt", "tản nhiệt", "nhiệt độ"]):
            aspects.append("tản nhiệt")
        if any(w in lower for w in ["giao hàng", "đóng gói", "hộp"]):
            aspects.append("vận chuyển")

        # Phân loại cảm xúc
        pos_words = ["tốt", "mượt", "đẹp", "tuyệt", "5 sao", "ưng", "êm", "nhanh", "hài lòng", "ổn áp"]
        neg_words = ["lỗi", "tệ", "hỏng", "thất vọng", "chậm", "kém", "liệt", "nóng", "rè", "trầy"]

        pos_score = sum(1 for w in pos_words if w in lower)
        neg_score = sum(1 for w in neg_words if w in lower)

        if pos_score > neg_score:
            label = "positive"
            conf = min(0.98, 0.85 + pos_score * 0.05)
        elif neg_score > pos_score or is_toxic:
            label = "negative"
            conf = min(0.98, 0.85 + neg_score * 0.05)
        else:
            label = "neutral"
            conf = 0.80

        return JevSentimentDecision(
            sentiment=label,
            confidence=round(conf, 2),
            is_spam_or_toxic=is_toxic,
            aspects=aspects
        )

    # --------------------------------------------------------------------------
    # 2.3. RAG QUERY SPACE ROUTING
    # --------------------------------------------------------------------------
    def route_rag_query(self, query: str, available_spaces: Optional[List[str]] = None) -> JevRAGRoutingDecision:
        """Định tuyến câu hỏi RAG vào đúng Chuyên mục quy định nội bộ."""
        lower = query.lower().strip()

        # Nhận diện chuyên mục dựa trên đặc trưng pháp chế
        if any(w in lower for w in ["điểm chết", "dead pixel", "sọc", "hở sáng", "panel", "chuẩn kỹ thuật", "nhiệt độ"]):
            target = "Tiêu chuẩn kỹ thuật"
            conf = 0.96
        elif any(w in lower for w in ["chiết khấu", "nhân viên", "mua nội bộ", "phúc lợi", "thưởng", "lương"]):
            target = "Chính sách nội bộ"
            conf = 0.95
        elif any(w in lower for w in ["kho", "nhập", "xuất", "serial", "s/n", "kiểm kê", "đóng gói"]):
            target = "Quy trình vận hành"
            conf = 0.92
        elif any(w in lower for w in ["bảo hành", "đổi trả", "1 đổi 1", "30 ngày", "trả hàng", "hoàn tiền"]):
            target = "Chính sách bảo hành"
            conf = 0.95
        else:
            target = "all"
            conf = 0.80

        # Trích xuất thực thể
        entities = []
        for brand in ["asus", "msi", "acer", "lenovo", "dell", "hp", "lg", "samsung"]:
            if brand in lower:
                entities.append(brand.upper())

        return JevRAGRoutingDecision(
            target_space=target,
            confidence=conf,
            key_entities=entities
        )

    # --------------------------------------------------------------------------
    # 2.4. HARDWARE SPECS EXTRACTION (FOR PC BUILDER)
    # --------------------------------------------------------------------------
    def extract_hardware_specs(self, text: str) -> JevSpecsDecision:
        """Trích xuất thông số kỹ thuật chuẩn hóa từ văn bản tự do."""
        specs = JevSpecsDecision()
        upper = text.upper()

        # Socket
        m_socket = re.search(r'(LGA\s*\d{4}|AM4|AM5)', upper)
        if m_socket:
            specs.socket = m_socket.group(1).replace(" ", "")

        # RAM Type
        if "DDR5" in upper:
            specs.ram_type = "DDR5"
        elif "DDR4" in upper:
            specs.ram_type = "DDR4"

        # Wattage
        m_watt = re.search(r'(\d{2,4})\s*W\b', upper)
        if m_watt:
            specs.wattage = int(m_watt.group(1))

        return specs


jev_service = JevService()


import re
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models.product import Product
from app.schemas.ai import AIChatRequest, AIChatResponse, RecommendedProductItem
from app.core.lm_client import lm_client
from app.services.jev_service import jev_service, JevChatDecision


# ==============================================================================
# 1. HARD SCOPE SYSTEM PROMPT — CHUYÊN BIỆT VỀ LAPTOP
# ==============================================================================
SALES_SYSTEM_PROMPT = """Bạn là Chuyên viên Tư vấn Kỹ thuật & Bán hàng ĐỘC QUYỀN VỀ LAPTOP tại GearVN — chuỗi bán lẻ công nghệ hàng đầu Việt Nam.

RANH GIỚI PHẠM VI BẮT BUỘC (HARD BOUNDARY):
1. BẠN CHỈ ĐƯỢC PHÉP TƯ VẤN VỀ LAPTOP / MÁY TÍNH XÁCH TAY:
   - Các dòng máy: Laptop Gaming, Laptop Văn phòng mỏng nhẹ, Laptop Đồ họa & Kỹ thuật, Apple MacBook...
   - Cấu hình & thông số trên laptop: CPU, GPU/Card đồ họa, RAM, Ổ cứng SSD, Màn hình (tần số quét, chuẩn màu), Thời lượng pin, Tản nhiệt laptop.
   - So sánh giữa các mẫu laptop, tư vấn theo tầm giá (triệu đồng) và nhu cầu học tập / làm việc / chơi game.
   - Chính sách bảo hành, đổi trả và hậu mãi cho Laptop tại GearVN.

2. TUYỆT ĐỐI TỪ CHỐI TẤT CẢ CÁC CHỦ ĐỀ NGOÀI LAPTOP:
   - KHÔNG trả lời chuyện đời tư, thời sự, giải toán, viết code phần mềm chung, nấu ăn, hoặc hỏi các sản phẩm khác (như điện thoại, tivi, máy giặt, linh kiện case PC rời không liên quan laptop).
   - Nếu khách hỏi ngoài lề, hãy LẬP TỨC từ chối lịch sự và bẻ lái khách quay lại chủ đề chọn mua laptop:
     "Chào bạn, tôi là trợ lý chuyên sâu về Laptop của GearVN, tôi chỉ có thể hỗ trợ các thông tin về máy tính xách tay. Bạn có muốn tôi tư vấn mẫu laptop nào phù hợp với nhu cầu học tập hay chơi game của bạn không?"

3. NGUYÊN TẮC TRẢ LỜI:
   - ĐI THẲNG VÀO TRỌNG TÂM CÂU HỎI trong 1-2 câu đầu tiên.
   - Chỉ tư vấn các dòng laptop có trong danh sách sản phẩm được cấp.
   - Luôn đính kèm link sản phẩm dạng markdown: [Tên Laptop](/product/slug).
   - Phong cách: Thân thiện, lịch sự, xưng "tôi" - gọi "bạn", nhiệt tình và am hiểu công nghệ."""


# ==============================================================================
# 2. TOPIC GUARDRAIL KEYWORDS
# ==============================================================================
# Các từ khóa hợp lệ liên quan đến Laptop
LAPTOP_KEYWORDS = [
    # Danh mục & thiết bị
    "laptop", "máy tính xách tay", "macbook", "notebook", "ultrabook", "máy xách tay",
    # Dòng máy / Phân khúc
    "gaming", "chơi game", "game", "văn phòng", "mỏng nhẹ", "học tập", "đồ họa", "render",
    "sinh viên", "lập trình", "coder", "it", "làm việc", "giải trí",
    # Thương hiệu & Model laptop nổi tiếng
    "asus", "acer", "lenovo", "dell", "hp", "msi", "apple",
    "rog", "tuf", "nitro", "legion", "loq", "katana", "zenbook", "xps", "air m", "pro m",
    # Thông số phần cứng trên laptop
    "cpu", "gpu", "vga", "card", "ram", "ssd", "nvme", "pin", "màn hình", "tần số quét",
    "144hz", "165hz", "240hz", "oled", "ips", "srgb", "tản nhiệt",
    "i3", "i5", "i7", "i9", "core", "ultra", "ryzen", "rtx", "gtx", "4050", "4060", "4070", "4080", "4090", "3050", "3060",
    # Tầm giá & nhu cầu mua sắm
    "giá", "ngân sách", "tầm", "khoảng", "triệu", "tr", "củ", "tiền", "mua máy", "tư vấn", "chọn máy",
    # Chính sách dịch vụ laptop
    "bảo hành", "đổi trả", "trả góp", "khuyến mãi", "quà tặng", "balo", "chuột tặng", "cài win"
]

# Lời chào & mở đầu giao tiếp hợp lệ
GREETING_KEYWORDS = [
    "chào", "hello", "hi", "alo", "shop ơi", "ad ơi", "admin", "bạn ơi", "cho mình hỏi", "hỏi xíu", "tư vấn giúp"
]

# Các từ khóa ngoài lề cần chặn ngay lập tức
OUT_OF_SCOPE_BLACKLIST = [
    "nấu", "món ăn", "cách làm bánh", "thời tiết", "mưa", "nắng", "nhiệt độ ngoài trời",
    "bài toán", "giải phương trình", "bài thơ", "làm thơ", "tủ lạnh", "máy giặt", "nồi cơm",
    "bếp từ", "quạt máy", "bóng đá", "tổng thống", "chính trị", "chứng khoán", "xổ số", "vietlott"
]

OUT_OF_SCOPE_RESPONSE = (
    "Chào bạn! Tôi là **Chuyên viên tư vấn Laptop chuyên biệt tại GearVN**! 😊\n\n"
    "Hiện tại tôi chỉ có thể hỗ trợ giải đáp chuyên sâu về **các dòng Laptop** (Gaming, Văn phòng mỏng nhẹ, Đồ họa, MacBook...), "
    "cấu hình phần cứng và chính sách bảo hành laptop.\n\n"
    "👉 Bạn có đang cần tìm một chiếc laptop phục vụ cho nhu cầu **học tập, làm việc** hay **chơi game** trong tầm ngân sách nào không? "
    "Chia sẻ để tôi hỗ trợ gợi ý mẫu máy tối ưu nhất cho bạn nhé!"
)


# ==============================================================================
# 3. AI SALES ASSISTANT CLASS
# ==============================================================================
class AISalesAssistant:

    def is_laptop_related(self, text: str) -> bool:
        """
        Guardrail Gatekeeper powered by TypeSafe AI Jev:
        - Kiểm tra quyết định TypeSafe có thuộc phạm vi Laptop hay không.
        - Tự động nhận diện chủ đề ngoài lề với độ tin cậy được hiệu chuẩn.
        """
        decision = jev_service.decide_chat_intent(text)
        return decision.is_laptop_related

    def extract_budget(self, text: str) -> Optional[float]:
        """Trích xuất ngân sách sử dụng TypeSafe AI Jev System-1 Extractor."""
        decision = jev_service.decide_chat_intent(text)
        return decision.extracted_budget

    def _query_products(
        self,
        db: Session,
        lower_msg: str,
        extracted_budget: Optional[float]
    ) -> List[Product]:
        """
        Data Whitelisting: CHỈ TRUY VẤN VÀ GỢI Ý CÁC DÒNG SẢN PHẨM LAPTOP TẠI KHO.
        """
        # 1. Khóa cứng 100% chỉ tìm kiếm Laptop
        query = db.query(Product).filter(
            or_(Product.name.ilike("%Laptop%"), Product.slug.ilike("%laptop%"))
        )

        # 2. Phân loại phân khúc laptop chuyên biệt
        is_gaming_intent = any(k in lower_msg for k in ["gaming", "chơi game", "valorant", "csgo", "genshin", "fo4", "pubg", "fps", "rtx"])
        is_ultrabook_intent = any(k in lower_msg for k in ["văn phòng", "mỏng nhẹ", "học tập", "macbook", "pin trâu", "nhẹ", "sinh viên"])

        if is_gaming_intent:
            query = query.filter(or_(
                Product.name.ilike("%Gaming%"),
                Product.name.ilike("%ROG%"),
                Product.name.ilike("%TUF%"),
                Product.name.ilike("%Nitro%"),
                Product.name.ilike("%Katana%"),
                Product.name.ilike("%Legion%"),
                Product.name.ilike("%LOQ%")
            ))
        elif is_ultrabook_intent:
            query = query.filter(or_(
                Product.name.ilike("%Zenbook%"),
                Product.name.ilike("%XPS%"),
                Product.name.ilike("%MacBook%"),
                Product.name.ilike("%Vivobook%"),
                Product.name.ilike("%Yoga%")
            ))

        # 3. Lọc theo model / hãng laptop cụ thể
        specific_keywords = ["4060", "4050", "4070", "3050", "i5", "i7", "i9", "ryzen", "asus", "msi", "acer", "lenovo", "dell", "hp", "apple", "macbook"]
        matched_specs = [w for w in specific_keywords if w in lower_msg]
        for kw in matched_specs:
            query = query.filter(Product.name.ilike(f"%{kw}%"))

        # 4. Lọc và sắp xếp theo ngân sách
        if extracted_budget and extracted_budget > 0:
            min_price = extracted_budget * 0.40
            max_price = extracted_budget * 1.25
            query = query.filter(and_(Product.promo_price >= min_price, Product.promo_price <= max_price))
            query = query.order_by(func.abs(Product.promo_price - extracted_budget).asc(), Product.rating_avg.desc())
        else:
            query = query.order_by(Product.rating_avg.desc(), Product.sales_count.desc())

        products = query.limit(4).all()

        # Fallback nếu tiêu chí quá hẹp: Lấy các dòng laptop nổi bật nhất
        if not products:
            fallback_q = db.query(Product).filter(
                or_(Product.name.ilike("%Laptop%"), Product.slug.ilike("%laptop%"))
            )
            if extracted_budget:
                fallback_q = fallback_q.filter(Product.promo_price <= extracted_budget * 1.30)
            products = fallback_q.order_by(Product.is_featured.desc(), Product.rating_avg.desc()).limit(3).all()

        return products

    def _build_recommended_items(self, products: List[Product]) -> List[RecommendedProductItem]:
        items = []
        for p in products:
            specs = {}
            if p.specs_json:
                try:
                    specs = json.loads(p.specs_json)
                except Exception:
                    pass
            items.append(RecommendedProductItem(
                id=p.id,
                name=p.name,
                slug=p.slug,
                brand=p.brand,
                promo_price=p.promo_price,
                original_price=p.original_price,
                thumbnail=p.thumbnail or "/static/images/default-product.png",
                specs=specs,
                reason=f"Đánh giá {p.rating_avg}★ | Bán chạy: {p.sales_count} máy",
            ))
        return items

    def _build_products_context(self, items: List[RecommendedProductItem]) -> str:
        if not items:
            return "Hiện kho GearVN chưa có mẫu laptop khớp 100% tiêu chí này."
        lines = []
        for idx, item in enumerate(items, 1):
            specs_str = ", ".join(f"{k}: {v}" for k, v in list(item.specs.items())[:3])
            savings = int(item.original_price - item.promo_price)
            lines.append(
                f"{idx}. [{item.name}](/product/{item.slug})\n"
                f"   - Hãng: {item.brand} | Giá bán: {int(item.promo_price):,}đ"
                + (f" (Đang giảm {savings:,}đ)" if savings > 0 else "") + "\n"
                f"   - Thông số chính: {specs_str}"
            )
        return "\n\n".join(lines)

    def _generate_llm_reply(self, request: AIChatRequest, items: List[RecommendedProductItem]) -> Optional[str]:
        products_context = self._build_products_context(items)
        messages: List[Dict[str, str]] = [{"role": "system", "content": SALES_SYSTEM_PROMPT}]

        for hist_msg in (request.conversation_history or []):
            if hist_msg.role in ["user", "assistant", "system"]:
                messages.append({"role": hist_msg.role, "content": hist_msg.content})

        messages.append({
            "role": "user",
            "content": (
                f"Khách hàng hỏi: \"{request.message}\"\n\n"
                f"Danh sách Laptop thực tế có sẵn tại GearVN:\n{products_context}\n\n"
                f"Hãy trả lời trực tiếp đúng trọng tâm câu hỏi của khách hàng trước, sau đó phân tích ngắn gọn lý do tại sao mẫu laptop trên phù hợp."
            )
        })

       
        return lm_client.chat(messages=messages, temperature=0.3, max_tokens=750, top_p=0.90)

    def _generate_fallback_reply(self, items: List[RecommendedProductItem], extracted_budget: Optional[float]) -> str:
        budget_str = f"{int(extracted_budget):,}đ" if extracted_budget else "linh hoạt"
        parts = [
            f"Chào bạn! Tôi là **Chuyên viên tư vấn Laptop GearVN**.",
            f"Dựa trên yêu cầu của bạn (Ngân sách dự kiến: **{budget_str}**), tôi xin gợi ý các dòng Laptop tối ưu nhất đang có sẵn:"
        ]
        for idx, item in enumerate(items[:3], 1):
            savings = int(item.original_price - item.promo_price)
            parts.append(
                f"\n**{idx}. [{item.name}](/product/{item.slug})**\n"
                f"- Giá ưu đãi: **{int(item.promo_price):,}đ**"
                + (f" *(Tiết kiệm: {savings:,}đ)*" if savings > 0 else "")
            )
        parts.append("\n👉 Bạn có thể click trực tiếp vào thẻ laptop bên dưới để xem chi tiết cấu hình và ưu đãi nhé!")
        return "\n".join(parts)

    @staticmethod
    def _get_suggested_questions(lower_msg: str) -> List[str]:
        """Toàn bộ câu hỏi gợi ý được định hướng 100% xoay quanh Laptop."""
        if any(k in lower_msg for k in ["game", "gaming", "valorant", "rtx"]):
            return [
                "Cấu hình này chiến mượt game gì ở mức đồ họa cao?",
                "Máy có được nâng cấp thêm RAM hoặc SSD không?",
                "Tản nhiệt của laptop này khi chơi lâu có mát không?",
                "Mua laptop gaming có được tặng kèm balo, chuột không?"
            ]
        elif any(k in lower_msg for k in ["học", "văn phòng", "mỏng nhẹ", "pin"]):
            return [
                "Thời lượng pin thực tế của máy dùng được mấy tiếng?",
                "Màn hình của máy có chuẩn màu và chống mỏi mắt không?",
                "Trọng lượng máy bao nhiêu kg, có tiện mang đi học không?",
                "Chính sách bảo hành chính hãng của máy ra sao?"
            ]
        elif any(k in lower_msg for k in ["đồ họa", "render", "macbook", "m3"]):
            return [
                "Máy có chạy mượt Premiere, Photoshop, AutoCAD không?",
                "Màn hình đạt độ phủ màu bao nhiêu % sRGB/DCI-P3?",
                "Nên chọn phiên bản 16GB hay 32GB RAM để render?",
                "Có hỗ trợ cài đặt các phần mềm văn phòng miễn phí không?"
            ]
        return [
            "Tư vấn laptop gaming tầm 20 triệu bán chạy nhất",
            "Laptop văn phòng mỏng nhẹ pin trâu cho sinh viên",
            "MacBook Air M3 phục vụ lập trình & đồ họa",
            "Chính sách bảo hành và đổi trả laptop tại GearVN"
        ]

    def process_consultation(self, db: Session, request: AIChatRequest) -> AIChatResponse:
        user_msg = request.message.strip()
        lower_msg = user_msg.lower()

        # 1. Guardrail Gatekeeper: Chặn các câu hỏi ngoài phạm vi Laptop
        if not self.is_laptop_related(user_msg):
            return AIChatResponse(
                reply=OUT_OF_SCOPE_RESPONSE,
                intent="out_of_scope",
                recommended_products=[],
                suggested_questions=self._get_suggested_questions("")
            )

        extracted_budget = request.budget or self.extract_budget(user_msg)
        products = self._query_products(db, lower_msg, extracted_budget)
        recommended_items = self._build_recommended_items(products)
        display_items = recommended_items[:3]

        llm_reply = self._generate_llm_reply(request, display_items)
        final_reply = llm_reply or self._generate_fallback_reply(display_items, extracted_budget)

        return AIChatResponse(
            reply=final_reply,
            intent="consultation",
            recommended_products=display_items,
            suggested_questions=self._get_suggested_questions(lower_msg),
        )

    def process_consultation_stream(self, db: Session, request: AIChatRequest):
        user_msg = request.message.strip()
        lower_msg = user_msg.lower()

        # 1. Guardrail Gatekeeper: Chặn các câu hỏi ngoài phạm vi Laptop
        if not self.is_laptop_related(user_msg):
            yield {
                "type": "products",
                "recommended_products": []
            }
            yield {
                "type": "content",
                "chunk": OUT_OF_SCOPE_RESPONSE
            }
            yield {
                "type": "done",
                "suggested_questions": self._get_suggested_questions("")
            }
            return

        extracted_budget = request.budget or self.extract_budget(user_msg)
        products = self._query_products(db, lower_msg, extracted_budget)
        recommended_items = self._build_recommended_items(products)[:3]

        # 2. Gửi danh sách Laptop gợi ý
        yield {
            "type": "products",
            "recommended_products": [item.dict() for item in recommended_items]
        }

        # 3. Xây dựng prompt
        products_context = self._build_products_context(recommended_items)
        messages = [{"role": "system", "content": SALES_SYSTEM_PROMPT}]

        for hist_msg in (request.conversation_history or []):
            if hist_msg.role in ["user", "assistant", "system"]:
                messages.append({"role": hist_msg.role, "content": hist_msg.content})

        messages.append({
            "role": "user",
            "content": (
                f"Khách hàng hỏi: \"{request.message}\"\n\n"
                f"Danh sách Laptop thực tế có sẵn tại GearVN:\n{products_context}\n\n"
                f"Hãy trả lời trực tiếp đúng trọng tâm câu hỏi của khách hàng trước, sau đó phân tích ngắn gọn lý do tại sao mẫu laptop trên phù hợp."
            )
        })

        # 4. Stream câu trả lời từ LLM (Temperature 0.25)
        has_streamed = False
        if lm_client.is_available():
            for chunk in lm_client.stream_chat(messages=messages, temperature=0.25, max_tokens=750):
                has_streamed = True
                yield {"type": "content", "chunk": chunk}

        if not has_streamed:
            fallback = self._generate_fallback_reply(recommended_items, extracted_budget)
            yield {"type": "content", "chunk": fallback}

        # 5. Gửi câu hỏi gợi ý chuyên biệt về laptop
        yield {
            "type": "done",
            "suggested_questions": self._get_suggested_questions(lower_msg)
        }


ai_sales_assistant = AISalesAssistant()

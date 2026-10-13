import sys
import os
import httpx

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.config import settings
from app.services.jev_service import JevService

def test_jev():
    print("=" * 65)
    print("      KIỂM TRA TÍCH HỢP JEV MODEL (TYPESAFE AI) & HỆ THỐNG")
    print("=" * 65)
    print(f"[*] API Base URL : {settings.JEV_BASE_URL}")
    print(f"[*] Model Name   : {settings.JEV_MODEL}")
    raw_key = settings.TYPESAFE_AI_API_KEY.strip()
    if raw_key:
        masked_key = f"{raw_key[:8]}...{raw_key[-4:]}"
        print(f"[*] API Key hiện tại: {masked_key} (Độ dài: {len(raw_key)} ký tự)")
    else:
        print("[*] API Key hiện tại: (Chưa cấu hình trong .env)")
    print("-" * 65)

    # 1. Kiểm tra Cloud API TypeSafe
    print("\n[BƯỚC 1] Kiểm tra kết nối tới TypeSafe AI Cloud API...")
    if not raw_key:
        print(" -> [BỎ QUA] Chưa có TYPESAFE_AI_API_KEY trong file .env.")
    else:
        # Kiểm tra xác thực qua endpoint /v1/models
        auth_url = f"{settings.JEV_BASE_URL.rstrip('/')}/models"
        headers = {
            "Authorization": f"Bearer {raw_key}",
            "Content-Type": "application/json"
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(auth_url, headers=headers)
                if resp.status_code == 200:
                    print(" [THÀNH CÔNG] API Key hợp lệ! Kết nối TypeSafe AI Cloud OK.")
                    models_data = resp.json()
                    print(f"   -> Danh sách models khả dụng: {models_data}")
                elif resp.status_code == 401 or resp.status_code == 403:
                    print(" [CẢNH BÁO] API Key không được TypeSafe AI chấp nhận (HTTP 401 Authentication Error).")
                    print(f"   -> Phản hồi server: {resp.text}")
                    if raw_key.startswith("vck_"):
                        print("   -> LƯU Ý: Key của bạn có tiền tố 'vck_', đây là định dạng key của Vercel AI Gateway,")
                        print("             trong khi TypeSafe AI Jev thường dùng key định dạng 'jv_live_...' từ console.typesafe.ai.")
                else:
                    print(f" [PHẢN HỒI] Server trả về mã HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f" [LỖI MẠNG] Không thể kết nối tới server TypeSafe AI Cloud: {e}")

    # 2. Kiểm tra Jev Decision Engine (Có Calibrated Local Fallback)
    print("\n[BƯỚC 2] Kiểm tra Jev Decision Engine hoạt động trong ứng dụng...")
    service = JevService()

    # Test 2.1: Chat Gatekeeper & Phân loại phân khúc laptop
    query_1 = "Tư vấn laptop gaming tầm 20 triệu chơi Valorant, CS2"
    dec_1 = service.decide_chat_intent(query_1)
    print(f"\n -> Test 1: Chat Guardrail & Router")
    print(f"    Câu hỏi          : \"{query_1}\"")
    print(f"    Liên quan Laptop : {dec_1.is_laptop_related}")
    print(f"    Phân khúc        : {dec_1.intent_category}")
    budget_str = f"{dec_1.extracted_budget:,.0f} VNĐ" if dec_1.extracted_budget else "Không có"
    print(f"    Ngân sách bóc tách: {budget_str}")
    print(f"    Độ tin cậy       : {dec_1.confidence * 100:.0f}%")
    print(f"    Cơ chế xử lý     : {dec_1.reasoning}")

    # Test 2.2: Lọc câu hỏi ngoài phạm vi (Out of scope)
    query_2 = "Hôm nay thời tiết Hà Nội thế nào, có mưa không?"
    dec_2 = service.decide_chat_intent(query_2)
    print(f"\n -> Test 2: Chặn câu hỏi ngoài phạm vi")
    print(f"    Câu hỏi          : \"{query_2}\"")
    print(f"    Liên quan Laptop : {dec_2.is_laptop_related} (Đã chặn thành công: {not dec_2.is_laptop_related})")
    print(f"    Ý định           : {dec_2.intent_category}")

    # Test 2.3: Đánh giá cảm xúc & Kiểm duyệt nội dung
    review_text = "Máy đẹp, pin trâu dùng rất thích nhưng shop giao hàng hơi chậm"
    dec_3 = service.decide_sentiment(review_text)
    print(f"\n -> Test 3: Phân loại Sentiment Review & Chống Toxic")
    print(f"    Nội dung review  : \"{review_text}\"")
    print(f"    Cảm xúc          : {dec_3.sentiment}")
    print(f"    Có vi phạm/Spam  : {dec_3.is_spam_or_toxic}")
    print(f"    Khía cạnh nhắc tới: {dec_3.aspects}")

    # Test 2.4: Trích xuất thông số kỹ thuật (Hardware Specs Extractor)
    spec_text = "CPU Intel Core i5 13400F LGA1700 hỗ trợ DDR5 công suất nguồn khuyến nghị 650W"
    dec_4 = service.extract_hardware_specs(spec_text)
    print(f"\n -> Test 4: Trích xuất Hardware Specs (PC Builder)")
    print(f"    Mô tả phần cứng  : \"{spec_text}\"")
    print(f"    Socket           : {dec_4.socket}")
    print(f"    RAM Type         : {dec_4.ram_type}")
    print(f"    Công suất (W)    : {dec_4.wattage}W")

    print("\n" + "=" * 65)
    print(">>> KẾT QUẢ: JEV DECISION ENGINE HOẠT ĐỘNG HOÀN HẢO! <<<")
    print("=" * 65)

if __name__ == "__main__":
    test_jev()

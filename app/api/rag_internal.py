import os
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.internal_doc import InternalDoc
from app.models.user import User
from app.schemas.rag import (
    InternalDocCreate, InternalDocUpdate, InternalDocOut,
    RAGQueryRequest, RAGQueryResponse
)
from app.core.security import require_staff_or_admin
from app.services.rag_service import rag_service
from app.services.doc_extractor import extract_text_from_file

router = APIRouter(prefix="/rag", tags=["Internal RAG Knowledge Base"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

SAMPLE_DOCS = [
    {
        "title": "Chính Sách Bảo Hành & Đổi Trả Sản Phẩm Công Nghệ GearVN 2026",
        "category": "Chính sách bảo hành",
        "tags": "bao hanh, doi tra, 1 doi 1, loi nha san xuat, tu choi bao hanh",
        "content_text": """1. QUY ĐỊNH ĐỔI TRẢ 1 ĐỔI 1 TRONG 30 NGÀY ĐẦU TIÊN:
- Phạm vi áp dụng: Toàn bộ Laptop Gaming, Laptop Văn phòng, Dàn PC G-Studio, và Linh kiện phần cứng chính hãng (CPU, Mainboard, VGA, RAM, SSD, Nguồn PSU).
- Điều kiện hưởng chính sách 1 đổi 1:
  + Sản phẩm phát sinh lỗi kỹ thuật phần cứng do nhà sản xuất (được xác nhận bởi kỹ thuật viên GearVN hoặc TTBH của hãng).
  + Sản phẩm còn nguyên vẹn 100% ngoại quan: Không móp méo, nứt vỡ, trầy xước nặng, không có dấu hiệu vào nước hay oxy hóa.
  + Đầy đủ hộp (box) trùng số Serial Number (S/N), sách hướng dẫn, phiếu bảo hành và toàn bộ phụ kiện kèm theo.
- Phương án xử lý khi hết hàng: Khách hàng được đổi sang model tương đương hoặc nhận hoàn tiền 100% giá trị mua ban đầu.

2. QUY TRÌNH TIẾP NHẬN BẢO HÀNH CHUẨN TẠI QUẦY:
- Bước 1: Tiếp nhận và tra cứu lịch sử mua hàng qua Số điện thoại hoặc mã Serial Number (S/N) trên hệ thống ERP GearVN.
- Bước 2: Kỹ thuật viên thẩm định ngoại quan và test lỗi nhanh trong vòng 15 - 30 phút.
- Bước 3: Trong 30 ngày đầu, xuất kho đổi ngay sản phẩm mới 100% tại quầy. Sau 30 ngày, gửi TTBH chính hãng xử lý từ 7 - 14 ngày làm việc (hỗ trợ cho mượn máy/linh kiện dùng tạm).

3. CÁC TRƯỜNG HỢP TỪ CHỐI BẢO HÀNH:
- Tem bảo hành hoặc tem niêm phong bị rách, mờ, cạo sửa hoặc dán đè.
- Sản phẩm có dấu hiệu can thiệp, sửa chữa hoặc tháo rời tại các cơ sở không được ủy quyền.
- Cháy nổ IC, cong gãy chân socket CPU, cấn móp màn hình, rơi rớt, sét đánh hoặc chất lỏng xâm nhập."""
    },
    {
        "title": "Quy Định Bảo Hành Màn Hình và Tiêu Chuẩn Điểm Chết (Dead Pixel)",
        "category": "Tiêu chuẩn kỹ thuật",
        "tags": "man hinh, diem chet, dead pixel, asus, lg, samsung, dell, ho sang",
        "content_text": """1. PHÂN LOẠI ĐIỂM CHẾT TRÊN MÀN HÌNH:
- Điểm chết sáng (Bright Dot): Điểm ảnh luôn phát sáng màu trắng, đỏ, xanh trên nền đen hoàn toàn.
- Điểm chết tối (Dark Dot): Điểm ảnh luôn có màu đen trên nền trắng hoặc nền sáng.
- Hiện tượng hở sáng (IPS Glow): Đặc tính vật lý của tấm nền IPS, chỉ bảo hành khi hở sáng quá mức thành vệt sáng lớn thấy rõ dưới ánh đèn bình thường.

2. TIÊU CHUẨN BẢO HÀNH ĐỔI MỚI THEO TỪNG HÃNG:
- Hãng ASUS: Đổi mới màn hình nếu có từ 3 điểm sáng hoặc 5 điểm tối trở lên trong 36 tháng. Riêng dòng ROG và ProArt áp dụng chuẩn Zero Bright Dot (ZBD) đổi mới ngay nếu có từ 1 điểm sáng trong 12 tháng đầu.
- Hãng LG: Đổi mới/thay panel nếu phát hiện từ 3 điểm chết bất kỳ trong 24 tháng đối với màn hình UltraGear và UltraFine.
- Hãng Samsung: Tiêu chuẩn tối thiểu từ 5 điểm chết trở lên đối với dòng Odyssey Gaming.
- Hãng Dell UltraSharp: Đổi màn hình mới ngay khi xuất hiện từ 1 điểm sáng (Premium Panel Exchange) trong suốt 3 năm bảo hành.

3. GÓI 'BẢO HÀNH MÀN HÌNH VIP GEARVN':
- Hỗ trợ 1 đổi 1 ngay lập tức nếu xuất hiện từ 1 điểm chết bất kỳ trong 90 ngày đầu tiên.
- Miễn phí cân màu màn hình bằng thiết bị SpyderX Elite trọn đời máy."""
    },
    {
        "title": "Chính Sách Bảo Hành Pin, Bộ Sạc & Bản Lề Laptop GearVN",
        "category": "Chính sách bảo hành",
        "tags": "pin laptop, chai pin, adapter, ban le, laptop",
        "content_text": """1. QUY ĐỊNH BẢO HÀNH PIN LAPTOP:
- Pin laptop tích hợp liền máy được bảo hành tiêu chuẩn 12 tháng kể từ ngày kích hoạt hóa đơn mua hàng.
- Điều kiện thay pin mới miễn phí:
  + Pin bị phồng rộp làm cong vênh vỏ máy hoặc bàn phím trong 12 tháng đầu.
  + Dung lượng pin thực tế (Full Charge Capacity) tụt dưới 70% so với thiết kế ban đầu khi số chu kỳ sạc (Cycle Count) dưới 350 lần.
  + Máy không nhận pin hoặc rút sạc là sập nguồn ngay lập tức do lỗi mạch điều khiển pin (BMS).

2. BẢO HÀNH CỦ SẠC & DÂY NGUỒN:
- Củ sạc chính hãng đi kèm máy được bảo hành đổi mới 12 tháng nếu không vào điện do lỗi linh kiện bên trong (không nứt vỡ vỏ, không đứt gãy dây cáp).

3. CHÍNH SÁCH BẢO DƯỠNG BẢN LÈ LAPTOP TRỌN ĐỜI:
- Miễn phí vệ sinh, tra dầu bôi trơn và nới lỏng/siết chặt độ căng bản lề trọn đời máy tại tất cả showroom GearVN.
- Nếu bản lề bị kẹt cứng tự phát do lỗi khung kim loại trong thời hạn bảo hành: Đổi cụm vỏ/bản lề mới miễn phí.
- Nếu gãy do va đập ngoại lực: GearVN hỗ trợ hàn gia cố chân ốc hoặc trợ giá 50% chi phí linh kiện thay thế từ hãng."""
    },
    {
        "title": "Quy Trình Kiểm Tra Kỹ Thuật & Lắp Ráp Dàn PC Gaming G-Studio",
        "category": "Tiêu chuẩn kỹ thuật",
        "tags": "lap rap pc, thermal paste, psu, nguon, furmark, cinebench, stress test",
        "content_text": """1. TIÊU CHUẨN AN TOÀN TRƯỚC KHI LẮP RÁP:
- Bắt buộc đeo vòng tay khử tĩnh điện ESD trước khi chạm vào linh kiện trần.
- Soi kính lúp kiểm tra chân socket CPU (LGA1700, AM5), đảm bảo 100% không cong lệch chân socket trước khi lắp CPU.

2. NGUYÊN TẮC KỸ THUẬT LẮP ĐẶT:
- Tra keo tản nhiệt CPU: Dùng keo cao cấp (Noctua NT-H1, Kryonaut, MX-4), phương pháp 1 chấm hạt đậu ở tâm. Tuyệt đối không để keo tràn xuống socket.
- Tính toán công suất bộ nguồn (PSU): Công suất nguồn danh định phải đạt tối thiểu bằng Tổng TDP hệ thống x 1.25 (dư tải 25% an toàn).
- Cấp nguồn cho VGA RTX 40 Series: Từ RTX 4070 trở lên bắt buộc dùng cáp PCIe 8-pin riêng biệt từ nguồn, KHÔNG dùng cáp chia Y daisy-chain. Đầu nối 12VHPWR phải cắm ngập sát khớp, không bẻ gập dây sát đầu cắm.

3. CHECKLIST KIỂM THỬ TRƯỚC KHI BÀN GIAO:
- Kích hoạt XMP / EXPO trong BIOS để RAM chạy đúng tốc độ danh định.
- Chạy Cinebench R23 trong 10 phút: Nhiệt độ CPU tối đa không quá 88 độ C (AIO) hoặc 92 độ C (tản khí).
- Chạy FurMark Burn-in 15 phút: Nhiệt độ GPU Hotspot dưới 85 độ C, quạt êm ái, không có tiếng rít coil whine bất thường."""
    },
    {
        "title": "Chính Sách Mua Hàng Nội Bộ, Chiết Khấu & Phúc Lợi Nhân Viên GearVN",
        "category": "Chính sách nội bộ",
        "tags": "chiet khau nhan vien, phuc loi, tra gop tru luong, mua hang noi bo",
        "content_text": """1. ĐỐI TƯỢNG VÀ MỨC GIẢM GIÁ CHIẾT KHẤU:
- Áp dụng cho Cán bộ - Nhân viên (CBNV) chính thức ký HĐLĐ từ 3 tháng trở lên.
- Linh kiện PC (CPU, Main, VGA, RAM, SSD, Nguồn): Giảm trực tiếp 8% trên giá niêm yết hoặc tính theo giá vốn nhập kho + 2% chi phí vận hành (áp dụng mức nào thấp hơn).
- Gaming Gear (Bàn phím, Chuột, Tai nghe): Giảm từ 12% đến 15%.
- Laptop Gaming, Laptop Văn phòng & PC G-Studio: Giảm 7%, tối đa 3.000.000 VNĐ/sản phẩm.
- Màn hình máy tính: Giảm 6% trên giá khuyến mãi.

2. HẠN MỨC & CHÍNH SÁCH TRẢ GÓP TRỪ LƯƠNG:
- Hạn mức mua hàng ưu đãi: Tối đa 50.000.000 VNĐ/năm/nhân viên (làm mới ngày 01/01 hàng năm).
- Trả góp 0% trừ lương: Đơn hàng từ 10.000.000đ đến 35.000.000đ được chia đều khấu trừ vào lương trong 3 đến 6 tháng.

3. QUY TRÌNH PHÊ DUYỆT:
- Nhân viên gửi yêu cầu qua Portal HR trước 24 giờ để HR và Kế toán phê duyệt mã Internal Coupon."""
    },
    {
        "title": "Quy Trình Thu Cũ Đổi Mới (Trade-in) Laptop & Linh Kiện PC",
        "category": "Quy trình vận hành",
        "tags": "trade in, thu cu doi moi, len doi laptop, dinh gia may cu, tro gia",
        "content_text": """1. ĐIỀU KIỆN TIẾP NHẬN TRADE-IN:
- Laptop Gaming và Ultrabook văn phòng chính hãng sản xuất từ năm 2020 trở lại đây.
- VGA NVIDIA GTX 16 Series trở lên, RTX 20/30/40 Series (không nhận VGA rỉ sét, trâu cày nặng).

2. TIÊU CHUẨN ĐỊNH GIÁ 4 CẤP ĐỘ:
- Loại A (Đẹp như mới 98 - 99%, pin chai <15%, đủ sạc và hộp): Thu 75% - 80% giá thị trường máy cũ.
- Loại B (Xước xát nhẹ 90 - 95%, pin chai 15-25%, đủ sạc): Thu 65% - 70% giá thị trường.
- Loại C (Cấn móp nhẹ 80 - 85%, pin chai >25%, màn hình có đốm sáng nhẹ): Thu 50% - 60% giá thị trường.
- Loại D (Lỗi chức năng: liệt phím, chết cổng, bể màn): Định giá thu theo xác linh kiện.

3. CHÍNH SÁCH TRỢ GIÁ LÊN ĐỜI (TRADE-UP BONUS):
- Lên đời máy mới trên 20 triệu: Trợ giá thêm 500.000 VNĐ vào giá thu máy cũ.
- Lên đời máy mới trên 35 triệu: Trợ giá thêm 1.000.000 VNĐ.
- Lên đời máy mới trên 50 triệu: Trợ giá thêm 1.500.000 VNĐ.
- Miễn phí 100% công sao lưu và chuyển dữ liệu từ máy cũ sang máy mới tại quầy."""
    },
    {
        "title": "Quy Trình Hướng Dẫn Mua Hàng Trả Góp 0% Lãi Suất Tại GearVN",
        "category": "Quy trình vận hành",
        "tags": "tra gop 0%, the tin dung, home credit, hd saison, can cuoc cong dan",
        "content_text": """1. HÌNH THỨC 1: TRẢ GÓP 0% QUA THẺ TÍN DỤNG (CREDIT CARD):
- Ngân hàng hỗ trợ: Hơn 25 ngân hàng lớn (Vietcombank, Techcombank, MB, VPBank, ACB, TPBank, Sacombank, HSBC, VIB...).
- Điều kiện: Thẻ tín dụng Visa/Mastercard/JCB còn hạn mức khả dụng bằng hoặc lớn hơn giá trị chuyển đổi.
- Kỳ hạn linh hoạt: 3, 6, 9, 12 tháng với 0% lãi suất hàng tháng.
- Phí chuyển đổi giao dịch: Từ 1.8% đến 3.8% thu một lần duy nhất theo biểu phí cổng thanh toán MPOS/Alepay.
- Thời gian duyệt: Quẹt thẻ tại quầy hoặc thanh toán online trên web, hoàn tất chuyển đổi trong 3 phút.

2. HÌNH THỨC 2: TRẢ GÓP QUA CÔNG TY TÀI CHÍNH (HOME CREDIT / HD SAISON):
- Độ tuổi áp dụng: Công dân Việt Nam từ đủ 18 tuổi đến 60 tuổi.
- Giấy tờ yêu cầu: Bản gốc Căn cước công dân (CCCD) gắn chip còn hiệu lực.
- Tỷ lệ trả trước: Trả trước từ 10% - 30% đối với đơn dưới 25 triệu; trả trước 30% - 40% đối với đơn trên 25 triệu.
- Thời gian thẩm định: Nhân viên tài chính duyệt hồ sơ tại quầy từ 15 - 20 phút, duyệt xong nhận máy ngay."""
    },
    {
        "title": "Quy Trình Đóng Gói Bảo Vệ Linh Kiện & Giao Hàng Hỏa Tốc Toàn Quốc",
        "category": "Quy trình vận hành",
        "tags": "giao hang hoa toc, dong goi, xop khi, chong soc, dong kiem",
        "content_text": """1. GIAO HÀNG HỎA TỐC 2 GIỜ NỘI THÀNH (TP.HCM & HÀ NỘI):
- Cam kết giao hàng tận tay trong 2 giờ kể từ khi xác nhận đơn đối với đơn đặt trước 17h30.
- Miễn phí vận chuyển 100% cho đơn hàng từ 3.000.000 VNĐ trở lên trong bán kính 10km.
- Khách hàng được quyền kiểm tra ngoại quan cùng shipper trước khi thanh toán COD.

2. TIÊU CHUẨN ĐÓNG GÓI 4 LỚP CHO ĐƠN LIÊN TỈNH:
- Lớp 1: Bọc màng PE chống thấm nước và bụi bẩn.
- Lớp 2: Quấn tối thiểu 3 đến 4 vòng xốp bóng khí (Bubble wrap) dày quanh toàn bộ 6 mặt hộp.
- Lớp 3: Đặt vào thùng carton 5 lớp cứng cáp, chèn chặt mút xốp chống xê dịch.
- Lớp 4: Dán băng dán cảnh báo màu đỏ 'HÀNG DỄ VỠ - XIN NHẸ TAY' và tem niêm phong bảo mật GearVN.

3. CAM KẾT ĐỀN BÙ SỰ CỐ VẬN CHUYỂN:
- Nếu hàng bị móp méo, nứt vỡ hoặc thất lạc trong quá trình vận chuyển, GearVN xuất kho gửi ngay sản phẩm mới 100% trong vòng 24 giờ. Toàn bộ chi phí khiếu nại với đơn vị vận chuyển do GearVN tự chịu trách nhiệm."""
    }
]

@router.post("/query", response_model=RAGQueryResponse)
def query_internal_rag(
    req: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """
    RAG Chatbot nội bộ dành cho Nhân viên & Quản trị viên
    Hỗ trợ lọc theo Không gian tài liệu (Vector Space / Category)
    """
    return rag_service.answer_query(db, query=req.query, top_k=req.top_k, space_category=req.space_category)

@router.get("/spaces")
def get_vector_spaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """Lấy danh sách các Không gian Vector (Vector Spaces) hiện có và số lượng tài liệu"""
    spaces = db.query(
        InternalDoc.category,
        func.count(InternalDoc.id).label("doc_count")
    ).group_by(InternalDoc.category).all()

    return [{"space_name": s[0], "doc_count": s[1]} for s in spaces]

@router.get("/docs", response_model=List[InternalDocOut])
def get_internal_docs(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    query = db.query(InternalDoc)
    if category and category != "all":
        query = query.filter(InternalDoc.category == category)
    return query.order_by(InternalDoc.created_at.desc()).all()

@router.post("/upload-file", response_model=InternalDocOut)
async def upload_document_file(
    file: UploadFile = File(...),
    category: str = Form("Chính sách bảo hành"),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """
    Tải lên tài liệu dạng file Word (.docx, .doc), PDF (.pdf), Markdown (.md), Text (.txt)
    Tự động giải mã, trích xuất nội dung văn bản và nạp vào Vector DB
    """
    filename = file.filename or "uploaded_document"
    ext = os.path.splitext(filename)[1].lower()

    allowed_exts = [".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"]
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file '{ext}' không hợp lệ. Chỉ chấp nhận các định dạng: .pdf, .docx, .md, .txt"
        )

    # Save file to disk
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{filename}"
    saved_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu trữ file: {str(e)}")

    # Extract text
    try:
        content_text = extract_text_from_file(saved_path, filename)
    except Exception as e:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=400, detail=f"Không thể đọc nội dung file: {str(e)}")

    # Determine Doc Title
    doc_title = title.strip() if (title and title.strip()) else os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")

    # Create record
    doc = InternalDoc(
        title=doc_title,
        category=category.strip() if category else "Chính sách chung",
        filename=filename,
        file_path=saved_path,
        content_text=content_text,
        tags=tags
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.get("/docs/{doc_id}/download")
def download_document_file(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """Tải về file đính kèm gốc của tài liệu nếu có"""
    doc = db.query(InternalDoc).filter(InternalDoc.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File gốc không tồn tại trên hệ thống")

    return FileResponse(
        path=doc.file_path,
        filename=doc.filename or f"doc_{doc_id}.pdf",
        media_type="application/octet-stream"
    )

@router.post("/docs", response_model=InternalDocOut)
def create_internal_doc(
    doc_in: InternalDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    doc = InternalDoc(**doc_in.dict())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.put("/docs/{doc_id}", response_model=InternalDocOut)
def update_internal_doc(
    doc_id: int,
    doc_in: InternalDocUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    doc = db.query(InternalDoc).filter(InternalDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    for field, val in doc_in.dict(exclude_unset=True).items():
        if val is not None:
            setattr(doc, field, val)

    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/docs/{doc_id}")
def delete_internal_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    doc = db.query(InternalDoc).filter(InternalDoc.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    # Remove physical file if exists
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    db.delete(doc)
    db.commit()
    return {"message": "Đã xóa tài liệu khỏi Vector DB thành công", "doc_id": doc_id}

@router.delete("/spaces/{space_name}")
def clear_vector_space(
    space_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """Xóa toàn bộ tài liệu trong một Không gian Vector (Vector Space) cụ thể"""
    deleted_count = db.query(InternalDoc).filter(InternalDoc.category == space_name).delete()
    db.commit()
    return {"message": f"Đã xóa sạch không gian '{space_name}' ({deleted_count} tài liệu)", "deleted_count": deleted_count}

@router.post("/reset-sample-docs")
def reset_sample_docs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin)
):
    """Khôi phục/Nạp lại các tài liệu mẫu chuẩn GearVN vào Vector DB"""
    db.query(InternalDoc).delete()
    db.commit()

    for item in SAMPLE_DOCS:
        doc = InternalDoc(**item)
        db.add(doc)
    db.commit()

    return {"message": "Đã khôi phục thành công các tài liệu mẫu vào Vector DB!", "total_docs": len(SAMPLE_DOCS)}

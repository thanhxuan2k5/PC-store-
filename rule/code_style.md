# Rule: Code Style - PEP8

## Mô tả

Tất cả code Python trong dự án **BẮT BUỘC** phải tuân thủ chuẩn PEP8 và các quy tắc bổ sung dưới đây.

## Quy tắc chính

### 1. Formatting
- **Indentation**: 4 spaces, không dùng tab.
- **Max line length**: 88 ký tự (theo chuẩn Black formatter).
- **Blank lines**: 2 dòng trống giữa các function/class top-level, 1 dòng trống giữa methods trong class.
- **Imports**: Sắp xếp theo thứ tự: stdlib → third-party → local, ngăn cách bằng dòng trống.

### 2. Naming Conventions
- `snake_case` cho biến, hàm, module.
- `PascalCase` cho class.
- `UPPER_SNAKE_CASE` cho hằng số.
- Tên biến/hàm phải **mô tả rõ ràng** mục đích (không dùng `x`, `tmp`, `data` nếu không có ngữ cảnh).

### 3. Type Hints
- **Bắt buộc** type hints cho tất cả function signatures (tham số và return type).
- Sử dụng `typing` module cho các kiểu phức tạp (`Optional`, `List`, `Dict`, `Union`).

```python
# ✅ Đúng
def detect_defects(image: np.ndarray, confidence: float = 0.5) -> list[dict]:
    ...

# ❌ Sai
def detect_defects(image, confidence=0.5):
    ...
```

### 4. Docstrings
- **Bắt buộc** docstring cho tất cả module, class, và public functions.
- Sử dụng format Google-style docstrings.

```python
def load_model(model_path: str, device: str = "cpu") -> YOLO:
    """Tải model YOLO từ file weights.

    Args:
        model_path: Đường dẫn tới file weights (.pt hoặc .onnx).
        device: Thiết bị chạy inference ("cpu", "cuda", "cuda:0").

    Returns:
        Instance YOLO model đã được load.

    Raises:
        FileNotFoundError: Nếu model_path không tồn tại.
    """
```

### 5. Error Handling
- Sử dụng **specific exceptions**, không bắt `Exception` chung chung.
- Luôn log lỗi trước khi raise hoặc xử lý.
- Sử dụng `logging` module, **KHÔNG** dùng `print()` trong production code.

### 6. Modular Design
- Mỗi file/module chỉ đảm nhận **một trách nhiệm** (Single Responsibility).
- Tách logic xử lý ảnh, inference, và API thành các module riêng biệt.
- Functions không quá **50 dòng**. Nếu dài hơn, tách thành helper functions.

### 7. Constants & Config
- Không hardcode giá trị magic numbers trong code.
- Đặt cấu hình trong `config/` hoặc biến môi trường.

```python
# ❌ Sai
if confidence > 0.7:
    ...

# ✅ Đúng
from config import CONFIDENCE_THRESHOLD
if confidence > CONFIDENCE_THRESHOLD:
    ...
```

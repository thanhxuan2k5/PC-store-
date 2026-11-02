# ==============================================================================
# GearVN PC Store & AI Assistant — Production Dockerfile
# ==============================================================================
FROM python:3.10-slim

# Thiết lập biến môi trường Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết (build tool cho C/C++ dependencies như FAISS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tách riêng lớp cài đặt requirements để tận dụng Docker Cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng
COPY app ./app
COPY sessions ./sessions

# Đảm bảo các thư mục dữ liệu tồn tại
RUN mkdir -p /app/data/uploads /app/data/internal_docs

# Khai báo cổng ứng dụng
EXPOSE 8000

# Kiểm tra tình trạng hoạt động (Healthcheck)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Lệnh khởi chạy ứng dụng FastAPI qua Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

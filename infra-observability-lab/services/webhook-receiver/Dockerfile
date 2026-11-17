FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .

# Chạy root để ghi được vào thư mục bind-mount ./data/alerts trên Windows/WSL
# (container chỉ lắng nghe trên mạng lab nội bộ và 127.0.0.1 của host).
EXPOSE 5001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001", "--no-access-log"]

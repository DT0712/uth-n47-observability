"""Cấu hình đọc từ biến môi trường (cùng tên với .env.example ở gốc repo).

Khi phát triển trên Windows chỉ cần DATABASE_URL trỏ tới SQLite (mặc định), không cần lab.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    # CSDL: PostgreSQL trong Compose (postgresql+psycopg://...) hoặc SQLite khi phát triển/test
    database_url: str = Field("sqlite:///./portal-dev.db", alias="DATABASE_URL")

    jwt_secret: str = Field("change-me-generate-a-random-string", alias="PORTAL_JWT_SECRET")
    jwt_expire_minutes: int = Field(60, alias="PORTAL_JWT_EXPIRE_MINUTES", ge=1, le=24 * 60)
    bootstrap_admin_user: str = Field("admin", alias="PORTAL_BOOTSTRAP_ADMIN_USER")
    bootstrap_admin_password: str = Field("change-me-lab-only", alias="PORTAL_BOOTSTRAP_ADMIN_PASSWORD")
    webhook_token: str = Field("change-me-lab-only", alias="PORTAL_WEBHOOK_TOKEN")

    prometheus_url: str = Field("http://prometheus:9090", alias="PORTAL_PROMETHEUS_URL")
    # CHỈ để xem thử giao diện trên Windows: thay Prometheus bằng bộ sinh số giả (không kết nối mạng)
    fake_prometheus: bool = Field(False, alias="PORTAL_FAKE_PROMETHEUS")
    grafana_public_url: str = Field("http://localhost:3000", alias="PORTAL_GRAFANA_PUBLIC_URL")
    runbooks_dir: str = Field("/runbooks", alias="PORTAL_RUNBOOKS_DIR")  # không có thì dùng runbooks/ của repo
    load_runbooks: bool = Field(True, alias="PORTAL_LOAD_RUNBOOKS")  # nạp lúc khởi động
    fault_max_duration_s: int = Field(840, alias="PORTAL_FAULT_MAX_DURATION_S", ge=30, le=840)
    lab_keys_dir: str = Field("/lab-keys", alias="PORTAL_LAB_KEYS_DIR")  # không có thì dùng .lab-keys/ của repo
    vm_web_ip: str = Field("192.168.56.11", alias="VM_WEB_IP")
    vm_db_ip: str = Field("192.168.56.12", alias="VM_DB_IP")
    fault_background: bool = Field(True, alias="PORTAL_FAULT_BACKGROUND")  # luồng nền theo dõi lần chạy (test tắt)
    fault_resolve_wait_s: float = Field(180, alias="PORTAL_FAULT_RESOLVE_WAIT_S", ge=0)

    # Nạp 3 VM mẫu (monitor, web, db) khi bảng hosts còn trống
    seed_inventory: bool = Field(True, alias="PORTAL_SEED_INVENTORY")

    # bcrypt cost (NFR-02); test hạ xuống 4 cho nhanh
    bcrypt_rounds: int = Field(12, alias="PORTAL_BCRYPT_ROUNDS", ge=4, le=15)
    # Đăng nhập sai: chờ bấy nhiêu giây trước khi trả lỗi (test đặt 0)
    login_failure_delay_s: float = Field(1.0, alias="PORTAL_LOGIN_FAILURE_DELAY_S", ge=0)

    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()

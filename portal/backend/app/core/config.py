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
    grafana_public_url: str = Field("http://localhost:3000", alias="PORTAL_GRAFANA_PUBLIC_URL")
    runbooks_dir: str = Field("/runbooks", alias="PORTAL_RUNBOOKS_DIR")
    fault_max_duration_s: int = Field(840, alias="PORTAL_FAULT_MAX_DURATION_S", ge=30, le=840)

    # Đăng nhập sai: chờ bấy nhiêu giây trước khi trả lỗi (test đặt 0)
    login_failure_delay_s: float = Field(1.0, alias="PORTAL_LOGIN_FAILURE_DELAY_S", ge=0)

    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()

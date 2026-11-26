"""Fixture chung: app với SQLite trong bộ nhớ (đã chạy migration), đồng hồ giả, TestClient.

Không cần lab, Prometheus hay mạng: mọi phụ thuộc ngoài được thay bằng bản giả.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.config import Settings
from app.db.migrate import upgrade
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(DATABASE_URL="sqlite://", PORTAL_JWT_SECRET="test-secret-" + "x" * 32,
                    PORTAL_WEBHOOK_TOKEN="test-webhook-token", PORTAL_LOGIN_FAILURE_DELAY_S=0)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(settings: Settings, clock: FakeClock):
    application = create_app(settings, clock)
    upgrade(application.state.db.engine)
    yield application
    application.state.db.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db(app) -> Session:
    with app.state.db.SessionLocal() as s:
        yield s

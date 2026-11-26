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
from tests.fakes import FakeFaultSSH, FakeLabChecks, FakePrometheus


@pytest.fixture
def settings() -> Settings:
    return Settings(DATABASE_URL="sqlite://", PORTAL_JWT_SECRET="test-secret-" + "x" * 32,
                    PORTAL_WEBHOOK_TOKEN="test-webhook-token", PORTAL_LOGIN_FAILURE_DELAY_S=0,
                    PORTAL_BCRYPT_ROUNDS=4, PORTAL_BOOTSTRAP_ADMIN_USER="admin",
                    PORTAL_BOOTSTRAP_ADMIN_PASSWORD="admin-pass-123", PORTAL_FAULT_BACKGROUND=False)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def prom(clock: FakeClock) -> FakePrometheus:
    return FakePrometheus(now=clock.now().timestamp())


@pytest.fixture
def ssh(clock: FakeClock) -> FakeFaultSSH:
    return FakeFaultSSH(clock)


@pytest.fixture
def checks() -> FakeLabChecks:
    return FakeLabChecks()


@pytest.fixture
def app(settings: Settings, clock: FakeClock, prom: FakePrometheus, ssh: FakeFaultSSH, checks: FakeLabChecks):
    # Không bao giờ gọi Prometheus hay SSH thật trong test
    application = create_app(settings, clock, prom, ssh, checks)
    upgrade(application.state.db.engine)
    yield application
    application.state.db.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as c:  # "with" chạy lifespan: tạo admin đầu tiên
        yield c


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_h(client) -> dict[str, str]:
    return login(client, "admin", "admin-pass-123")


@pytest.fixture
def operator_h(client, admin_h) -> dict[str, str]:
    r = client.post("/api/users", headers=admin_h, json={"username": "op1", "password": "op1-pass-123", "role": "operator"})
    assert r.status_code == 201, r.text
    return login(client, "op1", "op1-pass-123")


@pytest.fixture
def db(app) -> Session:
    with app.state.db.SessionLocal() as s:
        yield s

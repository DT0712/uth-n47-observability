"""Phần 2: đăng nhập JWT, phân quyền admin/operator, quản lý người dùng, nhật ký thao tác."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from tests.conftest import login


def _err(r) -> str:
    return r.json()["error"]["code"]


# ------------------------------------------------------------------ đăng nhập
def test_admin_dau_tien_duoc_tao_va_dang_nhap(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"]["role"] == "admin"
    assert body["expires_at"].startswith("2026-11-26T08:00:00")  # FakeClock 07:00 + 60 phút
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "admin" and me.json()["last_login_at"] is not None


def test_bootstrap_chi_chay_khi_chua_co_user(app, client, db):
    from app.db import models as m
    from app.services.users import ensure_bootstrap_admin
    assert ensure_bootstrap_admin(db, app.state.settings, app.state.clock) is None
    assert db.query(m.User).count() == 1


@pytest.mark.parametrize("username,password", [("admin", "sai-mat-khau"), ("khong-co", "admin-pass-123")])
def test_dang_nhap_sai_thong_bao_chung(client, admin_h, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 401 and _err(r) == "invalid_credentials"
    assert "mật khẩu" in r.json()["error"]["message"]  # cùng một thông báo, không lộ tài khoản có tồn tại
    log = client.get("/api/audit?action=login_failed", headers=admin_h).json()
    assert log["total"] == 1 and log["items"][0]["detail"]["username"] == username


def test_khong_co_token_sai_token_het_han(client, clock, admin_h):
    assert _err(client.get("/api/auth/me")) == "not_authenticated"
    assert client.get("/api/auth/me").headers["WWW-Authenticate"] == "Bearer"
    assert _err(client.get("/api/auth/me", headers={"Authorization": "Bearer abc"})) == "not_authenticated"
    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "khoa-khac", algorithm="HS256")
    assert _err(client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})) == "not_authenticated"
    clock.advance(timedelta(minutes=59, seconds=59).total_seconds())
    assert client.get("/api/auth/me", headers=admin_h).status_code == 200
    clock.advance(1)
    r = client.get("/api/auth/me", headers=admin_h)
    assert r.status_code == 401 and _err(r) == "token_expired"


def test_doi_mat_khau(client, admin_h):
    bad = client.post("/api/auth/password", headers=admin_h, json={"current_password": "sai", "new_password": "moi-pass-456"})
    assert bad.status_code == 422 and bad.json()["error"]["details"][0]["field"] == "current_password"
    short = client.post("/api/auth/password", headers=admin_h,
                        json={"current_password": "admin-pass-123", "new_password": "ngan"})
    assert short.status_code == 422
    ok = client.post("/api/auth/password", headers=admin_h,
                     json={"current_password": "admin-pass-123", "new_password": "moi-pass-456"})
    assert ok.status_code == 204
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"}).status_code == 401
    login(client, "admin", "moi-pass-456")


def test_dang_xuat_ghi_nhat_ky(client, admin_h):
    assert client.post("/api/auth/logout", headers=admin_h).status_code == 204
    assert client.get("/api/audit?action=logout", headers=admin_h).json()["total"] == 1


# ------------------------------------------------------------------ phân quyền
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/users", None),
    ("post", "/api/users", {"username": "x12", "password": "12345678", "role": "operator"}),
    ("patch", "/api/users/1", {"is_active": False}),
    ("get", "/api/audit", None),
])
def test_operator_bi_cam_api_admin(client, operator_h, method, path, body):
    r = getattr(client, method)(path, headers=operator_h, **({"json": body} if body else {}))
    assert r.status_code == 403 and _err(r) == "forbidden"


def test_operator_dung_duoc_api_operator(client, operator_h):
    assert client.get("/api/auth/me", headers=operator_h).json()["role"] == "operator"


def test_khoa_tai_khoan_co_hieu_luc_ngay(client, admin_h, operator_h):
    op_id = client.get("/api/auth/me", headers=operator_h).json()["id"]
    assert client.patch(f"/api/users/{op_id}", headers=admin_h, json={"is_active": False}).status_code == 200
    r = client.get("/api/auth/me", headers=operator_h)  # token cũ vẫn còn hạn nhưng bị chặn
    assert r.status_code == 401 and _err(r) == "account_disabled"
    assert client.post("/api/auth/login", json={"username": "op1", "password": "op1-pass-123"}).status_code == 401


def test_nang_quyen_co_hieu_luc_ngay(client, admin_h, operator_h):
    op_id = client.get("/api/auth/me", headers=operator_h).json()["id"]
    assert client.get("/api/users", headers=operator_h).status_code == 403
    client.patch(f"/api/users/{op_id}", headers=admin_h, json={"role": "admin"})
    assert client.get("/api/users", headers=operator_h).status_code == 200


# ------------------------------------------------------------------ quản lý người dùng
def test_tao_va_liet_ke_nguoi_dung(client, admin_h):
    r = client.post("/api/users", headers=admin_h, json={"username": "op2", "password": "op2-pass-123", "role": "operator"})
    assert r.status_code == 201 and "password" not in r.text and "password_hash" not in r.text
    dup = client.post("/api/users", headers=admin_h, json={"username": "op2", "password": "op2-pass-123", "role": "operator"})
    assert dup.status_code == 409 and _err(dup) == "duplicate"
    page = client.get("/api/users?page=1&page_size=1", headers=admin_h).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["items"][0]["username"] == "admin"


@pytest.mark.parametrize("body", [
    {"username": "AB", "password": "12345678", "role": "operator"},       # chữ hoa, quá ngắn
    {"username": "op3", "password": "1234567", "role": "operator"},       # mật khẩu < 8
    {"username": "op3", "password": "12345678", "role": "root"},          # vai trò lạ
])
def test_tao_nguoi_dung_du_lieu_sai(client, admin_h, body):
    r = client.post("/api/users", headers=admin_h, json=body)
    assert r.status_code == 422 and _err(r) == "validation_error" and r.json()["error"]["details"]


def test_khong_tu_khoa_khong_mat_admin_cuoi(client, admin_h):
    admin_id = client.get("/api/auth/me", headers=admin_h).json()["id"]
    r = client.patch(f"/api/users/{admin_id}", headers=admin_h, json={"is_active": False})
    assert r.status_code == 409 and _err(r) == "self_modification"
    r = client.patch(f"/api/users/{admin_id}", headers=admin_h, json={"role": "operator"})
    assert r.status_code == 409 and _err(r) == "self_modification"
    # admin thứ hai hạ admin thứ nhất được; nhưng không được hạ admin cuối cùng
    client.post("/api/users", headers=admin_h, json={"username": "admin2", "password": "admin2-pass", "role": "admin"})
    h2 = login(client, "admin2", "admin2-pass")
    assert client.patch(f"/api/users/{admin_id}", headers=h2, json={"role": "operator"}).status_code == 200
    admin2_id = client.get("/api/auth/me", headers=h2).json()["id"]
    r = client.patch(f"/api/users/{admin2_id}", headers=h2, json={"role": "operator"})
    assert _err(r) == "self_modification"


def test_sua_nguoi_dung_rong_hoac_khong_ton_tai(client, admin_h):
    assert client.patch("/api/users/1", headers=admin_h, json={}).status_code == 422
    assert _err(client.patch("/api/users/999", headers=admin_h, json={"is_active": True})) == "not_found"


def test_dat_lai_mat_khau_khong_ghi_vao_nhat_ky(client, admin_h, operator_h):
    op_id = client.get("/api/auth/me", headers=operator_h).json()["id"]
    client.patch(f"/api/users/{op_id}", headers=admin_h, json={"password": "mat-khau-moi-1"})
    login(client, "op1", "mat-khau-moi-1")
    entry = client.get("/api/audit?action=update", headers=admin_h).json()["items"][0]
    assert entry["detail"] == {"password": "đặt lại"} and "mat-khau-moi-1" not in str(entry)


# ------------------------------------------------------------------ nhật ký thao tác
def test_nhat_ky_ghi_du_va_loc_duoc(client, clock, admin_h, operator_h):
    log = client.get("/api/audit", headers=admin_h).json()
    actions = [i["action"] for i in log["items"]]
    assert actions[:3] == ["login", "create", "login"]  # mới nhất trước: op1 đăng nhập, admin tạo op1, admin đăng nhập
    created = next(i for i in log["items"] if i["action"] == "create")
    assert created["user"] == "admin" and created["object_type"] == "user" and created["client_ip"]
    assert created["detail"] == {"username": "op1", "role": "operator"}
    op_id = client.get("/api/auth/me", headers=operator_h).json()["id"]
    assert client.get(f"/api/audit?user_id={op_id}", headers=admin_h).json()["total"] == 1
    assert client.get("/api/audit?from=2026-11-26T07:00:01Z", headers=admin_h).json()["total"] == 0


# ------------------------------------------------------------------ giới hạn đăng nhập sai (B3)
def _sai(client, username="admin"):
    return client.post("/api/auth/login", json={"username": username, "password": "sai-mat-khau"})


def test_sai_5_lan_tam_khoa_cap_ten_ip(client, clock, admin_h):
    for _ in range(4):
        assert _sai(client).status_code == 401
    r = _sai(client)  # lần thứ 5: khóa
    assert r.status_code == 429 and _err(r) == "too_many_login_attempts"
    assert r.headers["Retry-After"] == "300" and "5 phút" in r.json()["error"]["message"]
    # Đang khóa: mật khẩu đúng cũng bị từ chối (không kiểm mật khẩu, không cho dò tiếp)
    r = client.post("/api/auth/login", json={"username": "ADMIN", "password": "admin-pass-123"})
    assert r.status_code == 429
    clock.advance(200)
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"}).headers[
        "Retry-After"] == "100"
    # Hết khóa thì tự mở: admin không bao giờ bị khóa vĩnh viễn
    clock.advance(100)
    login(client, "admin", "admin-pass-123")
    log = client.get("/api/audit?action=login_locked", headers=admin_h).json()
    assert log["total"] == 1
    d = log["items"][0]["detail"]
    assert d["username"] == "admin" and d["failures"] == 5 and d["lockout_s"] == 300
    # Lần chặn trong lúc khóa không ghi login_failed (chỉ 5 lần sai thật)
    assert client.get("/api/audit?action=login_failed", headers=admin_h).json()["total"] == 5


def test_dang_nhap_dung_xoa_bo_dem_va_cua_so_truot(client, clock):
    for _ in range(4):
        assert _sai(client).status_code == 401
    login(client, "admin", "admin-pass-123")  # xóa bộ đếm
    for _ in range(4):
        assert _sai(client).status_code == 401
    clock.advance(301)  # 4 lần sai cũ ra khỏi cửa sổ 5 phút
    assert _sai(client).status_code == 401


def test_khoa_theo_ten_khong_anh_huong_ten_khac(client):
    for _ in range(5):
        _sai(client, "khong-co")
    assert _sai(client, "khong-co").status_code == 429  # tên không tồn tại cũng bị khóa như nhau (không lộ tài khoản)
    login(client, "admin", "admin-pass-123")


def test_khoa_theo_ip_khong_anh_huong_ip_khac(app, client):
    import asyncio
    import httpx

    async def run():
        async def post(ip, password):
            transport = httpx.ASGITransport(app=app, client=(ip, 50000))
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return await c.post("/api/auth/login", json={"username": "admin", "password": password})
        for _ in range(5):
            await post("10.0.0.9", "sai-mat-khau")
        assert (await post("10.0.0.9", "admin-pass-123")).status_code == 429
        assert (await post("10.0.0.10", "admin-pass-123")).status_code == 200  # admin ở máy khác vẫn vào được

    asyncio.run(run())


def test_cho_khi_sai_khong_giu_luong_xu_ly(app, client):
    """3 lần sai đồng thời, chỉ 1 luồng trong threadpool: nếu chờ bằng time.sleep thì mất ~3 x 0,4 s."""
    import asyncio
    import time

    import anyio.to_thread
    import httpx

    app.state.settings.login_failure_delay_s = 0.4

    async def run():
        anyio.to_thread.current_default_thread_limiter().total_tokens = 1
        transport = httpx.ASGITransport(app=app, client=("10.0.0.20", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            t0 = time.monotonic()
            # Tài khoản có thật (bcrypt cost 4 trong test): phần chạy trong threadpool gần như bằng 0
            rs = await asyncio.gather(*[c.post("/api/auth/login", json={"username": "admin", "password": "x"})
                                        for _ in range(3)])
            return time.monotonic() - t0, [r.status_code for r in rs]

    elapsed, codes = asyncio.run(run())
    assert codes == [401, 401, 401]
    assert elapsed < 0.9, elapsed  # chạy tuần tự sẽ ≥ 1,2 s


def test_guard_gioi_han_bo_nho():
    from app.services import login_guard as lg
    g = lg.LoginGuard(5, 300, 300)
    for i in range(lg.MAX_KEYS + 50):
        g.failure(g.key(f"u{i}", "1.1.1.1"), 1000.0)
    assert len(g._entries) <= lg.MAX_KEYS

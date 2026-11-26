"""Mọi endpoint backend đã hiện thực phải có trong hợp đồng docs/02-thiet-ke/api/openapi.yaml, đúng vai trò tối thiểu."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi.routing import APIRoute

SPEC = Path(__file__).resolve().parents[3] / "docs" / "02-thiet-ke" / "api" / "openapi.yaml"
ROLE_DEPS = {"require_operator": "operator", "require_admin": "admin"}


def _spec() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def _min_role(route: APIRoute) -> str | None:
    found = []

    def walk(dep):
        name = getattr(dep.call, "__name__", "")
        if name in ROLE_DEPS:
            found.append(ROLE_DEPS[name])
        for d in dep.dependencies:
            walk(d)

    walk(route.dependant)
    return found[0] if found else None


def test_endpoint_co_trong_hop_dong_va_dung_vai_tro(app):
    spec = _spec()["paths"]
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        path = re.sub(r"\{(\w+)\}", r"{\1}", route.path)
        assert path in spec, f"{path} không có trong openapi.yaml"
        for method in route.methods - {"HEAD"}:
            op = spec[path].get(method.lower())
            assert op is not None, f"{method} {path} không có trong openapi.yaml"
            assert _min_role(route) == op.get("x-min-role"), f"{method} {path}: vai trò lệch hợp đồng"
            checked += 1
    assert checked >= 17  # tăng dần theo từng phần của GĐ5

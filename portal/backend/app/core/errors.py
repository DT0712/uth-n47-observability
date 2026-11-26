"""Định dạng lỗi thống nhất của API: {"error": {"code", "message", "details"}} (docs/02-thiet-ke/api/README.md mục 2)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Lỗi nghiệp vụ có mã. Ném ở bất kỳ đâu trong request, handler đổi thành JSON."""

    def __init__(self, status: int, code: str, message: str, details: list[dict[str, Any]] | None = None,
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details, self.headers = status, code, message, details, headers


def not_found(what: str = "đối tượng") -> ApiError:
    return ApiError(404, "not_found", f"Không tìm thấy {what}")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def _body(code: str, message: str, details: list | None = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"error": err}


_HTTP_CODES = {401: "not_authenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"], "type": e["type"]}
                   for e in exc.errors()]
        return JSONResponse(_body("validation_error", "Dữ liệu không hợp lệ", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Lỗi"
        if exc.status_code == 404 and message == "Not Found":
            message = "Không tìm thấy"
        return JSONResponse(_body(code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None))

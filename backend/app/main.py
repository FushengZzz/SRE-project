# -*- coding: utf-8 -*-
"""FastAPI 入口（NFR-01：依 README 启动后即可完成 UC-02 / UC-03）。

启动：在 backend/ 目录执行
    uvicorn app.main:app --host 127.0.0.1 --port 8000
或： python -m uvicorn app.main:app --reload   （开发热重载）
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import get_settings
from .errors import AppError

logger = logging.getLogger("uvicorn")


def _error_body(code: str, message: str, request_id: str) -> dict:
    """SRS 7.1 错误结构：code / message / request_id。"""
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version="0.1.0",
        description="智能体动态记忆管理 · 后端 API（M4 最小链路）",
    )

    # 本地前端联调（单用户本地应用，仅放开本机来源）
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, rid),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", "")
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = first.get("msg", "请求参数无效")
        detail = f"{loc}: {msg}" if loc else msg
        # 参数校验错误统一为 validation_error（SRS 7.1 可区分）
        return JSONResponse(
            status_code=400,
            content=_error_body("validation_error", f"参数校验失败：{detail}", rid),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "")
        logger.exception("未处理异常（request_id=%s）: %s", rid, exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", f"服务内部错误（request_id={rid}）", rid),
        )

    app.include_router(router)

    # 可选：前端已构建（frontend/dist）时由同一进程托管，便于单命令启动（NFR-01）。
    # API 路由先注册，因此 /api/* 不会被静态挂载覆盖。
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dist), html=True),
            name="frontend",
        )
    return app


app = create_app()

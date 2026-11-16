import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .database import Base, SessionLocal, engine, run_migrations
from .models import *  # noqa: F401,F403
from .seed import seed
from .routers import (
    auth,
    users,
    devices,
    areas,
    alarms,
    plans,
    linkage,
    emergencies,
    patrols,
    repairs,
    drills,
    stats,
)

IS_PRODUCTION = os.getenv("FIRE_ALARM_ENV", "").lower() == "production"


class SecurityHeadersMiddleware:
    """为所有 HTTP 响应注入轻量安全头（含 CORS 预检）。"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                headers = [
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-Frame-Options", b"DENY"),
                    (b"Referrer-Policy", b"no-referrer"),
                    (b"Content-Security-Policy", b"default-src 'self'"),
                ] + [h for h in headers if h[0].lower() not in (
                    b"x-content-type-options",
                    b"x-frame-options",
                    b"referrer-policy",
                    b"content-security-policy",
                )]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="消防报警联动控制系统",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# CORS 白名单收敛：读环境变量 FIRE_ALARM_ORIGINS（逗号分隔），默认前端开发代理地址。
_origins_str = os.getenv(
    "FIRE_ALARM_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
allow_origins = [o.strip() for o in _origins_str.split(",") if o.strip()]

# 安全头中间件置于 CORS 外层：对包括预检在内的所有 HTTP 响应注入安全头。
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    # 仅当白名单非通配符时才允许携带凭据（"*" + allow_credentials=True 违规）
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(areas.router)
app.include_router(devices.router)
app.include_router(alarms.router)
app.include_router(plans.router)
app.include_router(linkage.router)
app.include_router(emergencies.router)
app.include_router(patrols.router)
app.include_router(repairs.router)
app.include_router(drills.router)
app.include_router(stats.router)
app.include_router(users.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """通用未捕获异常兜底：记录日志、返回统一文案，不向客户端泄露堆栈。"""
    logging.exception("未捕获异常: %s %s -> %r", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


@app.get("/")
def root():
    return {"service": "fire-alarm-backend", "status": "ok"}
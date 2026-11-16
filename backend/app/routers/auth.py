import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import verify_password, create_access_token, get_current_user
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---- 登录限流：按 username + client IP 计数，1 分钟内超过 5 次返回 429 ----
_RATE_LIMIT_LOGIN = 5
_RATE_LIMIT_WINDOW = 60  # 秒
_login_attempts: dict[str, deque] = defaultdict(deque)
_login_lock = Lock()


def _login_key(username: str, ip: str) -> str:
    return f"{ip}|{username}"


def _check_rate_limit(username: str, ip: str):
    key = _login_key(username, ip)
    now = time.monotonic()
    with _login_lock:
        dq = _login_attempts[key]
        while dq and now - dq[0] > _RATE_LIMIT_WINDOW:
            dq.popleft()
        if len(dq) >= _RATE_LIMIT_LOGIN:
            raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")
        dq.append(now)


def _clear_rate_limit(username: str, ip: str):
    """同一窗口内成功登录即重置失败计数，避免合法用户被锁。"""
    key = _login_key(username, ip)
    with _login_lock:
        _login_attempts.pop(key, None)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(body.username, ip)
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已被停用")
    _clear_rate_limit(body.username, ip)
    token = create_access_token({"sub": user.username, "role": user.role})
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
"""
自建认证 API — 邮箱 + 密码 + OTP 验证码

端点：
    POST /api/auth/send-otp     发送 4 位 OTP 验证码到邮箱（注册时使用）
    POST /api/auth/register     注册：校验 OTP + 设置密码 → 返回 JWT
    POST /api/auth/login        登录：邮箱 + 密码 → 返回 JWT
    GET  /api/auth/me           获取当前用户信息（需 Bearer Token）
    POST /api/auth/profile/avatar 更新用户头像 URL
"""

import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db import user_repo
from app.service.otp_service import generate_otp, verify_otp
from app.service.email_service import send_otp_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


# ── 密码工具 ──────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """PBKDF2-SHA256 加盐哈希，格式：salt:hash"""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}:{hashed.hex()}"


def _check_password(password: str, stored: str) -> bool:
    """验证密码是否与存储的哈希匹配"""
    try:
        salt, hash_hex = stored.split(":", 1)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
        return hashed.hex() == hash_hex
    except Exception:
        return False


# ── JWT 工具 ──────────────────────────────────────────────────────

def _create_jwt(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")


# ── Pydantic Schemas ──────────────────────────────────────────────

class SendOtpRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    otp: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserInfo(BaseModel):
    user_id: str
    email: str
    avatar_url: Optional[str] = None


class AvatarUpdateRequest(BaseModel):
    avatar_url: str


# ── 依赖注入 ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db)
) -> UserInfo:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")
    payload = decode_jwt(credentials.credentials)
    
    user_id = payload["sub"]
    db_user = await user_repo.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="查无此用户")
        
    return UserInfo(user_id=db_user.id, email=db_user.email, avatar_url=db_user.avatar_url)


# ── 路由 ──────────────────────────────────────────────────────────

@router.post("/send-otp", summary="发送 OTP 验证码（注册时使用）")
async def send_otp(req: SendOtpRequest) -> dict:
    """生成 4 位验证码并发送到邮箱，有效期 10 分钟"""
    import asyncio
    otp = generate_otp(req.email)
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, send_otp_email, req.email, otp)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    logger.info("OTP 已发送: email=%s", req.email)
    return {"message": "验证码已发送，请查收邮件"}


@router.post("/register", response_model=TokenResponse, summary="注册新账号")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    注册流程：校验 OTP → 创建账号（含密码哈希）→ 返回 JWT
    """
    email = req.email.lower()

    existing_user = await user_repo.get_user_by_email(db, email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已注册，请直接登录",
        )

    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="密码至少 6 位",
        )

    if not verify_otp(email, req.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期，请重新获取",
        )

    user_id = str(uuid.uuid4())
    hashed_pw = _hash_password(req.password)
    
    await user_repo.create_user(db, user_id, email, hashed_pw)
    logger.info("新用户注册: email=%s", email)

    token = _create_jwt(user_id, email)
    return TokenResponse(access_token=token, user_id=user_id, email=email)


@router.post("/login", response_model=TokenResponse, summary="邮箱密码登录")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    登录流程：查找账号 → 验证密码 → 返回 JWT
    """
    email = req.email.lower()
    db_user = await user_repo.get_user_by_email(db, email)

    if not db_user or not _check_password(req.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    logger.info("用户登录: email=%s", email)
    token = _create_jwt(db_user.id, email)
    return TokenResponse(access_token=token, user_id=db_user.id, email=email)


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
async def get_me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    return user


@router.post("/profile/avatar", summary="更新用户头像")
async def update_avatar(
    req: AvatarUpdateRequest, 
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    success = await user_repo.update_avatar(db, user.user_id, req.avatar_url)
    if not success:
        raise HTTPException(status_code=500, detail="头像更新失败")
    return {"message": "头像已更新", "avatar_url": req.avatar_url}

"""
数据仓库：用户认证及账户管理。
负责操作 Postgres users 表。
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """通过邮箱查找用户"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """通过 ID 查找用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def create_user(
    db: AsyncSession, user_id: str, email: str, password_hash: str
) -> User:
    """创建新用户"""
    user = User(
        id=user_id,
        email=email,
        password_hash=password_hash,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_avatar(db: AsyncSession, user_id: str, avatar_url: str) -> bool:
    """更新用户头像 URL"""
    user = await get_user_by_id(db, user_id)
    if user:
        user.avatar_url = avatar_url
        await db.commit()
        return True
    return False

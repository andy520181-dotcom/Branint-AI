#!/usr/bin/env python3
"""
数据库连接测试脚本。

用途：在配置 .env 的 DATABASE_URL 后，运行此脚本验证阿里云 RDS 连接是否正常。

运行方式：
    cd backend
    python scripts/test_db_connection.py
"""

import asyncio
import os
import sys
from pathlib import Path

# NOTE: 将 backend/ 加入 Python 路径，确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _build_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


async def test_connection() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("❌ 错误：.env 中未配置 DATABASE_URL")
        sys.exit(1)

    print(f"🔗 正在连接：{database_url.split('@')[-1]}")  # 脱敏：只显示 host 部分

    async_url = _build_async_url(database_url)
    engine = create_async_engine(async_url, connect_args={"timeout": 10})

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ 连接成功！")
            print(f"   PostgreSQL 版本：{version}")

        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT current_database(), current_user, inet_server_addr()")
            )
            row = result.fetchone()
            print(f"   当前数据库：{row[0]}")
            print(f"   当前用户：{row[1]}")
            print(f"   服务器地址：{row[2]}")

        print("\n🎉 数据库配置正确，可以启动后端！")

    except Exception as e:
        print(f"\n❌ 连接失败：{e}")
        print("\n排查建议：")
        print("  1. 检查 .env 中的 DATABASE_URL 用户名/密码是否正确")
        print("  2. 检查阿里云 RDS 白名单是否包含你的本机 IP")
        print("  3. 检查实例是否处于「运行中」状态")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())

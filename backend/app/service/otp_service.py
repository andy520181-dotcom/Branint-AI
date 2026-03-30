"""
OTP 服务 — 生成、存储、校验 4 位数字验证码

NOTE: MVP 阶段使用内存字典存储，服务重启后 OTP 会失效（可接受）
      生产环境迁移到 Redis（替换 _store 的读写逻辑即可）
"""

import random
import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# NOTE: 不要在这里引入数据库依赖，保持该模块纯内存逻辑，方便后续替换
_store: Dict[str, Tuple[str, float]] = {}  # email → (otp, expire_timestamp)

OTP_LENGTH = 4
OTP_EXPIRE_SECONDS = 600  # 10 分钟


def generate_otp(email: str) -> str:
    """
    为指定邮箱生成并缓存一个 4 位 OTP 验证码

    每次调用会覆盖旧的 OTP，防止重复使用旧码
    """
    otp = f"{random.randint(0, 9999):04d}"  # 补零确保始终 4 位
    expire_at = time.time() + OTP_EXPIRE_SECONDS
    _store[email.lower()] = (otp, expire_at)
    logger.info("OTP 已生成: email=%s", email)
    return otp


def verify_otp(email: str, otp: str) -> bool:
    """
    验证 OTP 是否正确且未过期

    验证成功后立即删除，防止重放攻击（一次性使用）

    Returns:
        True  — 验证通过
        False — 验证码错误、已过期、或不存在
    """
    key = email.lower()
    if key not in _store:
        logger.warning("OTP 校验失败(不存在): email=%s", email)
        return False

    stored_otp, expire_at = _store[key]

    if time.time() > expire_at:
        del _store[key]
        logger.warning("OTP 已过期: email=%s", email)
        return False

    if stored_otp != otp.strip():
        logger.warning("OTP 错误: email=%s", email)
        return False

    # 验证通过，删除防止复用
    del _store[key]
    logger.info("OTP 验证通过: email=%s", email)
    return True

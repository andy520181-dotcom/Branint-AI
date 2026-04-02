"""
Agent 规则文件加载器（类 CLAUDE.md 机制）

启动时自动读取 agents/ 目录下的 .md 文件，
将 _shared_rules.md（共享铁律）+ 各 Agent 专属规则合并为最终 System Prompt。

修改规则只需编辑 .md 文件，重启后端即可生效。
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# NOTE: agents/ 目录位于 backend 根目录下
AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents"

# 启动时缓存，避免每次请求都读文件
_cache: dict[str, str] = {}


def load_agent_prompt(agent_id: str) -> str:
    """
    加载指定 Agent 的完整 System Prompt。
    规则 = Agent 专属规则 + 共享铁律
    """
    if agent_id in _cache:
        return _cache[agent_id]

    # 加载共享铁律
    shared_path = AGENTS_DIR / "_shared_rules.md"
    shared_rules = ""
    if shared_path.is_file():
        shared_rules = shared_path.read_text(encoding="utf-8").strip()
        logger.info("加载共享铁律: %s", shared_path.name)

    # 加载 Agent 专属规则
    agent_path = AGENTS_DIR / f"{agent_id}.md"
    agent_rules = ""
    if agent_path.is_file():
        agent_rules = agent_path.read_text(encoding="utf-8").strip()
        logger.info("加载 Agent 规则: %s", agent_path.name)
    else:
        logger.warning("Agent 规则文件不存在: %s，将仅使用共享铁律", agent_path.name)

    # 合并：Agent 专属规则在前，共享铁律在后
    prompt = f"{agent_rules}\n\n---\n\n{shared_rules}" if agent_rules else shared_rules
    _cache[agent_id] = prompt
    return prompt


def reload_all() -> None:
    """清空缓存，下次调用时重新读取文件（用于热更新）"""
    _cache.clear()
    logger.info("Agent 规则缓存已清空，将在下次调用时重新加载")

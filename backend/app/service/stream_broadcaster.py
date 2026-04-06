"""
内存级 SSE 广播器：将会话生成任务与 HTTP 连接解耦。

核心设计：
  - 每个运行中的 session_id 对应一个 SessionBroadcaster 实例
  - Orchestrator 在后台悬浮进程中运行，将 SSE 事件推入 broadcaster
  - 前端的每一条 HTTP/SSE 连接都是 broadcaster 的"听众"
  - 当浏览器刷新时，旧的听众队列被销毁，新进来的听众立刻收到历史 replay
  - Orchestrator 进程完全不受 HTTP 连接断开的影响，继续运行直到完成

NOTE: 这是解决"刷新丢档并重新生成"问题的根本架构方案。
      原先 Orchestrator 挂靠在 HTTP 请求协程上，TCP 断则进程死。
      现在 Orchestrator 以 asyncio.create_task 独立挂靠在事件循环上，
      HTTP 连接只是"旁听频道"，浏览器重连只需秒级回放历史事件。
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# 全局字典：session_id -> SessionBroadcaster
# NOTE: 进程级单例，uvicorn reload 会清空（开发时可接受；生产可用 Redis Pub/Sub 替代）
_broadcasters: dict[str, "SessionBroadcaster"] = {}


def get_broadcaster(session_id: str) -> "SessionBroadcaster | None":
    """获取已存在的广播器（刷新重连场景）"""
    return _broadcasters.get(session_id)


def get_or_create_broadcaster(session_id: str) -> tuple["SessionBroadcaster", bool]:
    """
    获取或创建广播器。
    返回 (broadcaster, is_new)：is_new=True 表示首次创建，调用方需启动后台任务。
    """
    if session_id in _broadcasters:
        return _broadcasters[session_id], False
    bc = SessionBroadcaster(session_id)
    _broadcasters[session_id] = bc
    return bc, True


def remove_broadcaster(session_id: str) -> None:
    """会话完成或出错后清理广播器，释放内存"""
    _broadcasters.pop(session_id, None)
    logger.info("广播器已释放: %s", session_id)


class SessionBroadcaster:
    """
    单会话事件广播器。

    Orchestrator 调用 put() 推入 SSE 事件字符串；
    每个新的 SSE HTTP 连接调用 listen() 订阅，
    订阅时会立即回放此前的所有历史事件（history replay），
    之后接收实时推送直到广播完毕。
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        # 历史事件列表（保증新听众接入时能秒速补到进度）
        self._history: list[str] = []
        # 订阅队列列表（每个 HTTP 连接一个队列）
        self._queues: list[asyncio.Queue[str | None]] = []
        # 标记广播是否已经结束
        self._done = False
        self._done_event = asyncio.Event()

    def put(self, event: str) -> None:
        """
        Orchestrator 推入一条 SSE 事件。
        先存入 history，再分发给所有在线听众。
        """
        self._history.append(event)
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("广播队列溢出 [%s]，丢弃 chunk", self.session_id)

    def close(self) -> None:
        """
        Orchestrator 完成后调用，向所有听众推送结束信号 (None)。
        """
        self._done = True
        self._done_event.set()
        for q in list(self._queues):
            try:
                q.put_nowait(None)
            except Exception:
                pass
        logger.info("广播器关闭: %s（共 %d 条历史事件）", self.session_id, len(self._history))

    async def listen(self) -> AsyncGenerator[str, None]:
        """
        订阅该广播器的事件流。
        1. 先 yield 历史事件的"压缩版"（replay，供刷新重连使用）
           - 历史阶段跳过所有 agent_start 与 agent_chunk，用累计好的 agent_output 直接替代
           - 其他事件（routing_decided / agent_complete / agent_image 等）原样回放
           - 对于还没有 agent_output 的进行中 Agent（正在打字），补发单条合并 chunk
        2. 再从队列接收未来的实时事件（正常流式打字）
        3. 广播器关闭后自动退出

        设计目标：刷新重连时前端界面不闪白，内容秒速恢复到最新进度，
                  然后无缝接续剩余的实时 chunk 推送。
        """
        import json as _j

        # 在添加实时队列之前先 snapshot 历史（线程安全：Python 列表 copy 是原子的）
        history_snapshot = list(self._history)
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=2000)
        self._queues.append(queue)

        try:
            # Step 1: 智能历史回放（压缩 chunk 防闪白）
            # 先重建每个 agent 的累计输出
            accumulated: dict[str, str] = {}
            finalized: set[str] = set()  # 已经有 agent_output 事件的 agent_id
            replay_events: list[str] = []   # 其余事件按序记录

            for event in history_snapshot:
                if "event: agent_chunk" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _j.loads(line[6:])
                                aid = payload.get("id", "")
                                chunk = payload.get("chunk", "")
                                if aid and chunk:
                                    accumulated[aid] = accumulated.get(aid, "") + chunk
                            except Exception:
                                pass
                    # agent_chunk 不放入 replay，后续用 agent_output 替代
                elif "event: agent_start" in event:
                    # NOTE: 必须重放 agent_start，否则前端在 LLM 思考期（无 chunk 时）会一直卡在空白的 loading 态！
                    replay_events.append(event)
                elif "event: agent_output" in event:
                    # 有最终输出，用它替代累计 chunk（更权威）
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _j.loads(line[6:])
                                aid = payload.get("id", "")
                                content = payload.get("content", "")
                                if aid and content:
                                    accumulated[aid] = content
                                    finalized.add(aid)
                            except Exception:
                                pass
                    replay_events.append(event)
                else:
                    # routing_decided / agent_complete / agent_image / agent_video
                    # / session_complete / strategy_clarify / session_pause 等原样回放
                    replay_events.append(event)

            # 构建回放序列：先发 routing_decided，再插入各 agent 的压缩输出，再其余事件
            # 按顺序发送其他事件
            # 先把每个有数据的 agent 用 agent_output 替代 chunk
            agent_output_events: dict[str, str] = {}
            for aid, content in accumulated.items():
                agent_output_events[aid] = (
                    f"event: agent_start\ndata: {aid}\n\n"
                    f"event: agent_output\ndata: "
                    f"{_j.dumps({'id': aid, 'content': content}, ensure_ascii=False)}\n\n"
                )

            # 依序 yield 所有历史回放事件
            emitted_agents: set[str] = set()
            for event in replay_events:
                # 在 agent_output 事件之前插入对应 agent 的 agent_start（让前端知道有这个 agent）
                if "event: agent_output" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _j.loads(line[6:])
                                aid = payload.get("id", "")
                                if aid and aid not in emitted_agents:
                                    yield f"event: agent_start\ndata: {aid}\n\n"
                                    emitted_agents.add(aid)
                            except Exception:
                                pass
                yield event

            # 对于在历史里只有 chunk 没有 agent_output 的 agent（正在进行中），
            # 发送合并后的完整输出（这样前端立刻看到已生成内容的全貌）
            for aid, content in accumulated.items():
                if aid not in finalized and content:
                    if aid not in emitted_agents:
                        yield f"event: agent_start\ndata: {aid}\n\n"
                    yield (
                        f"event: agent_output\ndata: "
                        f"{_j.dumps({'id': aid, 'content': content}, ensure_ascii=False)}\n\n"
                    )

            # 如果广播已结束（刷新时会话已完成），直接退出
            if self._done:
                return

            # Step 2: 实时监听未来事件（正常流式打字）
            # 切换到实时模式前，先通知前端即将续传（当前 agent 重新激活）
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # 每 30s 发送心跳保活，防止 Nginx/CDN 超时断连
                    yield ": heartbeat\n\n"
                    continue

                if event is None:
                    # None 是结束信号
                    break
                yield event
        finally:
            # 清理队列（浏览器断开连接时由 StreamingResponse 触发）
            if queue in self._queues:
                self._queues.remove(queue)


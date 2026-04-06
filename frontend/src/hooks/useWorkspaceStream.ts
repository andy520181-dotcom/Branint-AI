'use client';

import { useEffect, useRef } from 'react';
import { AgentId } from '@/types';
import { useWorkspaceStore, ResearchProgressStep } from '@/store/workspaceStore';
import { API_BASE as API_URL } from '@/lib/api';

/**
 * SSE 流连接 Hook
 * 连接后端 /api/sessions/{id}/stream，监听各 Agent 事件并更新 Zustand 状态
 * 支持品牌顾问动态路由：routing_decided / consultant_plan / consultant_review
 * 支持 Wacksman 实时研究进度：agent_research_progress
 *
 * NOTE: 依赖数组仅包含 sessionId，所有 Zustand actions 通过 getState() 获取
 * 以避免 React Strict Mode 和多次 setState 导致的 SSE 重连风暴。
 */
export function useWorkspaceStream(sessionId: string | null) {
  const esRef = useRef<EventSource | null>(null);
  // NOTE: 连接守卫——记录当前已连接的 sessionId，防止对同一 session 重复建连
  const connectedIdRef = useRef<string | null>(null);
  // NOTE: 防抖定时器——避免 restored 状态快速切换时连续触发连接
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancel = () => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    connectedIdRef.current = null;
    // 将当前 running 的 Agent 立即标记为 completed，清空激活状态
    const store = useWorkspaceStore.getState();
    const { agents, currentAgentId } = store;
    if (currentAgentId && agents[currentAgentId]?.status === 'running') {
      store.setAgentStatus(currentAgentId, 'completed');
    }
    store.setCurrentAgent(null);
    // 触发 setComplete：同步更新顶部状态栏和报告按钮
    store.setComplete();
  };

  useEffect(() => {
    // 清理上一次的防抖定时器
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }

    if (!sessionId) {
      // sessionId 为空时断开已有连接
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      connectedIdRef.current = null;
      return;
    }

    // NOTE: 连接守卫——如果已经连接到同一个 session 且连接仍然存活，跳过
    if (connectedIdRef.current === sessionId && esRef.current && esRef.current.readyState !== EventSource.CLOSED) {
      return;
    }

    // NOTE: 200ms 防抖——避免 fetchSnapshot 的多次 setState 触发连续 effect
    debounceRef.current = setTimeout(() => {
      // 双重检查：防抖期间 sessionId 可能已改变
      if (connectedIdRef.current === sessionId && esRef.current && esRef.current.readyState !== EventSource.CLOSED) {
        return;
      }

      // 关闭旧连接
      if (esRef.current) {
        esRef.current.close();
      }

      const store = useWorkspaceStore.getState;

      const es = new EventSource(`${API_URL}/api/sessions/${sessionId}/stream`);
      esRef.current = es;
      connectedIdRef.current = sessionId;

      es.onopen = () => {
        store().setStreaming(true);
      };

      // Agent 开始执行（含顾问节点）
      es.addEventListener('agent_start', (e) => {
        const agentId = e.data as AgentId;
        store().setAgentStatus(agentId, 'running');
        store().setCurrentAgent(agentId);
      });

      // NOTE: 流式 token 逐 chunk 追加，实现实时思考过程显示
      es.addEventListener('agent_chunk', (e) => {
        try {
          const { id, chunk } = JSON.parse(e.data) as { id: AgentId; chunk: string };
          store().appendAgentOutput(id, chunk);
        } catch {
          // 忽略解析错误
        }
      });

      // 专业 Agent 完整输出（所有 chunk 推完后用于最终 Markdown 渲染校正）
      es.addEventListener('agent_output', (e) => {
        try {
          const { id, content } = JSON.parse(e.data) as { id: AgentId; content: string };
          store().setAgentOutput(id, content);
        } catch {
          // 忽略解析错误
        }
      });

      // 接收 Agent 附带生成的图片（如美术指导 Agent 的 Logo）
      es.addEventListener('agent_image', (e) => {
        try {
          const { id, type, data_url } = JSON.parse(e.data) as { id: AgentId; type: string; data_url: string };
          store().addAgentImage(id, type, data_url);
        } catch {
          // 忽略解析错误
        }
      });

      // 接收 Agent 附带生成的视频（如美术指导 Agent 的即梦概念片）
      es.addEventListener('agent_video', (e) => {
        try {
          const { id, type, data_url } = JSON.parse(e.data) as { id: AgentId; type: string; data_url: string };
          store().addAgentVideo(id, type, data_url);
        } catch {
          // 忽略解析错误
        }
      });

      // NOTE: Wacksman 研究循环进度事件——静默期实时反馈
      es.addEventListener('agent_research_progress', (e) => {
        try {
          const { id, progress } = JSON.parse(e.data) as { id: AgentId; progress: string };
          const parsed = JSON.parse(progress) as { step: string; detail: string };
          const progressStep: ResearchProgressStep = {
            step: parsed.step,
            detail: parsed.detail,
            ts: Date.now(),
            done: false,
          };
          store().appendResearchProgress(id, progressStep);
        } catch {
          // 忽略解析失败
        }
      });

      // 品牌顾问路由决策：收到后动态更新工作台显示的 Agent 列表
      es.addEventListener('routing_decided', (e) => {
        try {
          const keys = JSON.parse(e.data) as string[];
          // 首尾各加顾问节点，中间是决策出的专业 Agent
          const fullRoute: AgentId[] = [
            'consultant_plan',
            ...keys.filter((k): k is AgentId => ['market','strategy','content','visual'].includes(k)),
            'consultant_review',
          ];
          store().setSelectedAgents(fullRoute);
        } catch {
          // 解析失败保持全量显示
        }
      });

      // NOTE: consultant_plan 和 consultant_review 现在通过 agent_chunk + agent_output 统一处理
      // 保留旧事件监听作为 fallback，兼容可能的非流式情况
      es.addEventListener('consultant_plan', (e) => {
        store().setAgentOutput('consultant_plan', e.data.replace(/\\n/g, '\n'));
      });
      es.addEventListener('consultant_review', (e) => {
        store().setAgentOutput('consultant_review', e.data.replace(/\\n/g, '\n'));
      });

      // Agent / 顾问节点完成
      es.addEventListener('agent_complete', (e) => {
        const agentId = e.data as AgentId;
        store().setAgentStatus(agentId, 'completed');
      });

      // 全部完成，最终报告由顾问审核输出
      es.addEventListener('session_complete', (e) => {
        try {
          const { report } = JSON.parse(e.data) as { report: string };
          store().setFinalReport(report);
        } catch {
          // 结构解析失败时跳过
        }
        store().setComplete();
        es.close();
      });

      // NOTE: 监听状态回滚指令，触发 Zustand 物理切断
      es.addEventListener('session_revert', (e) => {
        try {
          const { target_round } = JSON.parse(e.data) as { target_round: number };
          // eslint-disable-next-line no-console
          console.log(`[Revert] Server triggered revert to round ${target_round}. Dropping subsequent UI state...`);
          // 延迟 3 秒执行切断，给用户保留阅读"撤销回复"的时间
          setTimeout(() => {
            useWorkspaceStore.getState().revertToRound(target_round);
          }, 3000);
        } catch {
          // ignore
        }
      });

      // NOTE: Trout 战略追问信号——展示追问气泡并挂起会话，等待用户回答
      es.addEventListener('strategy_clarify', (e) => {
        try {
          const { questions } = JSON.parse(e.data) as { id: string; questions: string };
          const { sessionId: sid, strategyClarify } = store();
          store().setStrategyClarify({
            isPaused: true,
            questions,
            answer: '',
            // 累计追问轮次（每次追问 +1）
            clarifyRound: (strategyClarify?.clarifyRound ?? 0) + 1,
            originalSessionId: sid,
          });
        } catch {
          // 忽略解析错误
        }
      });

      // NOTE: 收到中断信号，保留现有状态并关闭长连接，等待用户下一轮对话输入
      es.addEventListener('session_pause', (e) => {
        try {
          const { reason } = JSON.parse(e.data) as { reason: string };
          // eslint-disable-next-line no-console
          console.log('Session paused for user interaction:', reason);
        } catch {
          // ignore
        }
        useWorkspaceStore.setState({ isStreaming: false, currentAgentId: null });
        es.close();
      });

      es.addEventListener('error', (e) => {
        const raw = (e as MessageEvent).data;
        store().setError(
          raw != null && String(raw).trim() !== ''
            ? String(raw)
            : 'workspace.error.streamInterrupted',
        );
        store().setAgentStatus('consultant_plan', 'error');
        es.close();
      });

      es.onerror = () => {
        store().setError('workspace.error.connectionLost');
        es.close();
      };
    }, 200);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      connectedIdRef.current = null;
    };
  // NOTE: 仅依赖 sessionId。所有 Zustand actions 通过 useWorkspaceStore.getState() 获取，
  // 引用天然稳定，不需要加入依赖数组——这是消除 SSE 重连风暴的核心手段。
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return { cancel };
}

'use client';

import { useEffect, useRef } from 'react';
import { AgentId } from '@/types';
import { useWorkspaceStore } from '@/store/workspaceStore';
import { API_BASE as API_URL } from '@/lib/api';

/**
 * SSE 流连接 Hook
 * 连接后端 /api/sessions/{id}/stream，监听各 Agent 事件并更新 Zustand 状态
 * 支持品牌顾问动态路由：routing_decided / consultant_plan / consultant_review
 */
export function useWorkspaceStream(sessionId: string | null) {
  const {
    setAgentStatus,
    setAgentOutput,
    appendAgentOutput,
    addAgentImage,
    setCurrentAgent,
    setSelectedAgents,
    setFinalReport,
    setComplete,
    setError,
    setStreaming,
  } = useWorkspaceStore();
  void setStreaming; // setStreaming 仅在 cancel 内部通过 setComplete 间接调用

  const esRef = useRef<EventSource | null>(null);

  const cancel = () => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    // 将当前 running 的 Agent 立即标记为 completed，清空激活状态
    const { agents, currentAgentId } = useWorkspaceStore.getState();
    if (currentAgentId && agents[currentAgentId]?.status === 'running') {
      setAgentStatus(currentAgentId, 'completed');
    }
    setCurrentAgent(null);
    // 触发 setComplete：同步更新顶部状态栏和报告按钮
    setComplete();
  };

  useEffect(() => {
    if (!sessionId) return;

    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource(`${API_URL}/api/sessions/${sessionId}/stream`);
    esRef.current = es;

    // Agent 开始执行（含顾问节点）
    es.addEventListener('agent_start', (e) => {
      const agentId = e.data as AgentId;
      setAgentStatus(agentId, 'running');
      setCurrentAgent(agentId);
    });

    // NOTE: 流式 token 逐 chunk 追加，实现实时思考过程显示
    es.addEventListener('agent_chunk', (e) => {
      try {
        const { id, chunk } = JSON.parse(e.data) as { id: AgentId; chunk: string };
        appendAgentOutput(id, chunk);
      } catch {
        // 忽略解析错误
      }
    });

    // 专业 Agent 完整输出（所有 chunk 推完后用于最终 Markdown 渲染校正）
    es.addEventListener('agent_output', (e) => {
      try {
        const { id, content } = JSON.parse(e.data) as { id: AgentId; content: string };
        setAgentOutput(id, content);
      } catch {
        // 忽略解析错误
      }
    });

    // 接收 Agent 附带生成的图片 (如视觉 Agent 的 Logo)
    es.addEventListener('agent_image', (e) => {
      try {
        const { id, type, data_url } = JSON.parse(e.data) as { id: AgentId; type: string; data_url: string };
        addAgentImage(id, type, data_url);
      } catch {
        // 忽略解析错误
      }
    });

    // 接收 Agent 附带生成的视频 (如视觉 Agent 的即梦概念片)
    es.addEventListener('agent_video', (e) => {
      try {
        const { id, type, data_url } = JSON.parse(e.data) as { id: AgentId; type: string; data_url: string };
        useWorkspaceStore.getState().addAgentVideo(id, type, data_url);
      } catch {
        // 忽略解析错误
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
        setSelectedAgents(fullRoute);
      } catch {
        // 解析失败保持全量显示
      }
    });

    // NOTE: consultant_plan 和 consultant_review 现在通过 agent_chunk + agent_output 统一处理
    // 保留旧事件监听作为 fallback，兼容可能的非流式情况
    es.addEventListener('consultant_plan', (e) => {
      setAgentOutput('consultant_plan', e.data.replace(/\\n/g, '\n'));
    });
    es.addEventListener('consultant_review', (e) => {
      setAgentOutput('consultant_review', e.data.replace(/\\n/g, '\n'));
    });

    // Agent / 顾问节点完成
    es.addEventListener('agent_complete', (e) => {
      const agentId = e.data as AgentId;
      setAgentStatus(agentId, 'completed');
    });

    // 全部完成，最终报告由顾问审核输出
    es.addEventListener('session_complete', (e) => {
      try {
        const { report } = JSON.parse(e.data) as { report: string };
        setFinalReport(report);
      } catch {
        // 结构解析失败时跳过
      }
      setComplete();
      es.close();
    });

    es.addEventListener('error', (e) => {
      const raw = (e as MessageEvent).data;
      setError(
        raw != null && String(raw).trim() !== ''
          ? String(raw)
          : 'workspace.error.streamInterrupted',
      );
      setAgentStatus('consultant_plan', 'error');
      es.close();
    });

    es.onerror = () => {
      setError('workspace.error.connectionLost');
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [sessionId, setAgentStatus, setAgentOutput, appendAgentOutput, setCurrentAgent, setFinalReport, setComplete, setError, setStreaming]);

  return { cancel };
}

import type { AgentId, AgentStatus } from '@/types';

/** 单轮分析的快照，用于在同页面保留历史内容 */
export interface RoundSnapshot {
  sessionId: string;
  userPrompt: string;
  agents: Record<AgentId, { id: AgentId; status: AgentStatus; output: string }>;
  selectedAgents: AgentId[] | null;
}

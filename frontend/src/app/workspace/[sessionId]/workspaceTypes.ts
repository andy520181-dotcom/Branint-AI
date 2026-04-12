import type { AgentId, AgentStatus, AgentImage } from '@/types';

/** 单轮分析的快照，用于在同页面保留历史内容 */
export interface RoundSnapshot {
  sessionId: string;
  userPrompt: string;
  agents: Record<AgentId, { id: AgentId; status: AgentStatus; output: string }>;
  selectedAgents: AgentId[] | null;
  /** NOTE: 该轮生成的视觉资产快照，确保图片卡片永远显示在触发它的对话轮次位置 */
  agentImages?: AgentImage[];
}

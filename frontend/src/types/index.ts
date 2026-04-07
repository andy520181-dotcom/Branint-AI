export type AgentId =
  | 'consultant_plan'   // 品牌顾问 — 执行计划阶段
  | 'market'
  | 'strategy'
  | 'content'
  | 'visual'
  | 'consultant_review'; // 品牌顾问 — 质量审核阶段

export type AgentStatus = 'waiting' | 'running' | 'completed' | 'error';

export interface AgentConfig {
  id: AgentId;
  name: string;
  charName: string;
  role: string;
  description: string;
  /** 落地页 Agent 卡片展示的能力标签，用 · 分隔 */
  desc: string;
  /** 头像图片路径（相对 public/）*/
  avatar: string;
  color: string;
  colorDim: string;
  icon: string;
  index: number;
}

export interface AgentState {
  id: AgentId;
  status: AgentStatus;
  output: string;
}

export interface WorkspaceStore {
  sessionId: string;
  userPrompt: string;
  agents: Record<AgentId, AgentState>;
  currentAgentId: AgentId | null;
  finalReport: string;
  isComplete: boolean;
  isStreaming: boolean;
  error: string | null;
  initSession: (sessionId: string, userPrompt: string) => void;
  setAgentStatus: (id: AgentId, status: AgentStatus) => void;
  setAgentOutput: (id: AgentId, output: string) => void;
  setCurrentAgent: (id: AgentId | null) => void;
  setFinalReport: (report: string) => void;
  setComplete: () => void;
  setError: (err: string) => void;
  reset: () => void;
}

export interface HistoryItem {
  sessionId: string;
  title: string;
  createdAt: string;
  /** 打开该会话的路径，一般为 `/workspace/{sessionId}` */
  shareUrl: string;
  isPinned?: boolean;
}

/** Agent 静态配置见 `@/data/agentConfigs` */

/** 美术指导 Agent（visual）生成的品牌参考图 */
export interface AgentImage {
  agentId: AgentId;
  type: string;
  dataUrl: string;
}

/** 美术指导 Agent（visual）生成的品牌视频 */
export interface AgentVideo {
  agentId: AgentId;
  type: string;
  dataUrl: string;
}

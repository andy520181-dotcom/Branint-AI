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
}

// NOTE: 顺序与后端 SSE 事件流一致，顾问首尾各一张卡片
export const AGENT_CONFIGS: AgentConfig[] = [
  {
    id: 'consultant_plan',
    name: '品牌顾问 Agent',
    charName: 'Lara',
    role: 'Brand Consultant · 执行计划',
    description: '拆解品牌需求，制定多智能体协作执行计划',
    desc: '需求诊断·项目统筹·进度管理',
    avatar: '/agents/lara.png',
    color: 'var(--color-gold)',
    colorDim: 'var(--agent-consultant-dim)',
    icon: '🧑‍💼',
    index: 0,
  },
  {
    id: 'market',
    name: '市场研究 Agent',
    charName: 'Smith',
    role: 'Market Research Agent',
    description: '深度分析目标市场、竞品格局与消费者画像',
    desc: '数据分析·用户洞察·竞品对标·机会识别',
    avatar: '/agents/smith.png',
    color: 'var(--agent-market)',
    colorDim: 'var(--agent-market-dim)',
    icon: '🔍',
    index: 1,
  },
  {
    id: 'strategy',
    name: '品牌战略 Agent',
    charName: 'Bond',
    role: 'Brand Strategy Agent',
    description: '制定品牌定位、命名方向与核心差异化主张',
    desc: '顶层设计·品牌定位·品牌架构·品牌屋',
    avatar: '/agents/bond.png',
    color: 'var(--agent-strategy)',
    colorDim: 'var(--agent-strategy-dim)',
    icon: '🎯',
    index: 2,
  },
  {
    id: 'content',
    name: '内容策划 Agent',
    charName: 'Hunt',
    role: 'Content Strategy Agent',
    description: '规划品牌故事、Slogan 与全渠道内容矩阵',
    desc: '品牌故事·Slogan·内容策略·传播矩阵',
    avatar: '/agents/hunt.png',
    color: 'var(--agent-content)',
    colorDim: 'var(--agent-content-dim)',
    icon: '✍️',
    index: 3,
  },
  {
    id: 'visual',
    name: '视觉设计 Agent',
    charName: 'Salt',
    role: 'Visual Design Agent',
    description: '构建视觉规范、色板、字体与 Logo 方向',
    desc: 'VI系统·视觉规范·物料延展',
    avatar: '/agents/salt.png',
    color: 'var(--agent-visual)',
    colorDim: 'var(--agent-visual-dim)',
    icon: '🎨',
    index: 4,
  },
  {
    id: 'consultant_review',
    name: '品牌顾问 Agent',
    charName: 'Lara',
    role: 'Brand Consultant · 质量审核',
    description: '整合四大专业分析，审核并输出最终综合品牌策略报告',
    desc: '质量审核·综合报告',
    avatar: '/agents/lara.png',
    color: 'var(--color-gold)',
    colorDim: 'var(--agent-consultant-dim)',
    icon: '🧑‍💼',
    index: 5,
  },
];


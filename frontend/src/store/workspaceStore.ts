import { create } from 'zustand';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import { AgentId, AgentStatus, AgentImage, AgentVideo } from '@/types';

/** 实时研究进度步骤，由后端 Wacksman 进度事件驱动 */
export interface ResearchProgressStep {
  /** 工具名称，如 web_search_market_data */
  step: string;
  /** 人类可读第一行＋详情 */
  detail: string;
  /** 时间戳 */
  ts: number;
  /** 是否已完成（下一步到来时标记当前步已完成） */
  done: boolean;
}

interface AgentState {
  id: AgentId;
  status: AgentStatus;
  output: string;
  /** Wacksman 研究循环实时进度，仅对 market Agent 有效 */
  researchProgress: ResearchProgressStep[];
}

type AgentsMap = Record<AgentId, AgentState>;

const initialAgents = (): AgentsMap => {
  const map = {} as AgentsMap;
  for (const cfg of AGENT_CONFIGS) {
    map[cfg.id] = { id: cfg.id, status: 'waiting', output: '', researchProgress: [] };
  }
  return map;
};

// localStorage 持久化 key（跨标签页、跨浏览器会话）
const CACHE_PREFIX = 'ws_state_';
const MAX_CACHED_SESSIONS = 30;

const storageKey = (sessionId: string) => `${CACHE_PREFIX}${sessionId}`;

interface PersistedState {
  agents: AgentsMap;
  selectedAgents: AgentId[] | null;
  agentImages?: AgentImage[];
  agentVideos?: AgentVideo[];
  finalReport: string;
  isComplete: boolean;
  userPrompt: string;
}

/** 超出 MAX_CACHED_SESSIONS 时删除最旧的缓存 */
const pruneSessionCache = () => {
  if (typeof window === 'undefined') return;
  try {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(CACHE_PREFIX)) keys.push(k);
    }
    if (keys.length > MAX_CACHED_SESSIONS) {
      keys.slice(0, keys.length - MAX_CACHED_SESSIONS).forEach((k) => localStorage.removeItem(k));
    }
  } catch { /* ignore */ }
};

export const saveSession = (sessionId: string, state: PersistedState) => {
  if (typeof window === 'undefined' || !sessionId) return;
  try {
    localStorage.setItem(storageKey(sessionId), JSON.stringify(state));
    pruneSessionCache();
  } catch { /* ignore */ }
};

export const loadSession = (sessionId: string): PersistedState | null => {
  if (typeof window === 'undefined' || !sessionId) return null;
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    return raw ? (JSON.parse(raw) as PersistedState) : null;
  } catch { return null; }
};

interface WorkspaceState {
  sessionId: string;
  userPrompt: string;
  agents: AgentsMap;
  currentAgentId: AgentId | null;
  // NOTE: 由顾问路由决策后设定，null 表示决策前（显示全部占位）
  selectedAgents: AgentId[] | null;
  /** 美术指导 Agent（visual）生成的品牌参考图 */
  agentImages: AgentImage[];
  /** 美术指导 Agent（visual）生成的品牌视频 */
  agentVideos: AgentVideo[];
  finalReport: string;
  isComplete: boolean;
  isStreaming: boolean;
  error: string | null;
}

interface WorkspaceActions {
  initSession: (sessionId: string, userPrompt: string) => void;
  setAgentStatus: (id: AgentId, status: AgentStatus) => void;
  setAgentOutput: (id: AgentId, output: string) => void;
  /** NOTE: 流式推送时逐 chunk 追加，不覆盖已有内容 */
  appendAgentOutput: (id: AgentId, chunk: string) => void;
  /** 追加 Wacksman 研究进度步骤 */
  appendResearchProgress: (id: AgentId, step: ResearchProgressStep) => void;
  /** 添加 Agent 生成的图片 */
  addAgentImage: (agentId: AgentId, type: string, dataUrl: string) => void;
  /** 添加 Agent 生成的视频 */
  addAgentVideo: (agentId: AgentId, type: string, dataUrl: string) => void;
  setCurrentAgent: (id: AgentId | null) => void;
  setSelectedAgents: (agents: AgentId[]) => void;
  setFinalReport: (report: string) => void;
  setComplete: () => void;
  setStreaming: (v: boolean) => void;
  setError: (err: string) => void;
  reset: () => void;
}

const initialState: WorkspaceState = {
  sessionId: '',
  userPrompt: '',
  agents: initialAgents(),
  currentAgentId: null,
  selectedAgents: null,
  agentImages: [],
  agentVideos: [],
  finalReport: '',
  isComplete: false,
  isStreaming: false,
  error: null,
};

/** NOTE: 统一的持久化调用点，避免每个 action 重复手写完整的 PersistedState */
const persist = (s: WorkspaceState) =>
  saveSession(s.sessionId, {
    agents: s.agents,
    selectedAgents: s.selectedAgents,
    agentImages: s.agentImages,
    agentVideos: s.agentVideos,
    finalReport: s.finalReport,
    isComplete: s.isComplete,
    userPrompt: s.userPrompt,
  });

export const useWorkspaceStore = create<WorkspaceState & WorkspaceActions>((set) => ({
  ...initialState,

  initSession: (sessionId, userPrompt) =>
    set({ ...initialState, agents: initialAgents(), agentImages: [], agentVideos: [], sessionId, userPrompt, isStreaming: true }),

  setAgentStatus: (id, status) =>
    set((s) => ({
      agents: { ...s.agents, [id]: { ...s.agents[id], status } },
    })),

  setAgentOutput: (id, output) =>
    set((s) => {
      const agents = { ...s.agents, [id]: { ...s.agents[id], output } };
      persist({ ...s, agents });
      return { agents };
    }),

  appendAgentOutput: (id, chunk) =>
    set((s) => {
      const existing = s.agents[id]?.output ?? '';
      const agents = { ...s.agents, [id]: { ...s.agents[id], output: existing + chunk } };
      return { agents };
    }),

  appendResearchProgress: (id, step) =>
    set((s) => {
      const prev = s.agents[id]?.researchProgress ?? [];
      // NOTE: 将前一个步骤标记为 done（新步骤到来时)
      const updated = prev.map((p, i) =>
        i === prev.length - 1 ? { ...p, done: true } : p
      );
      const agents = {
        ...s.agents,
        [id]: { ...s.agents[id], researchProgress: [...updated, step] },
      };
      return { agents };
    }),
  addAgentImage: (agentId, type, dataUrl) =>
    set((s) => {
      const agentImages = [...s.agentImages, { agentId, type, dataUrl }];
      persist({ ...s, agentImages });
      return { agentImages };
    }),

  addAgentVideo: (agentId, type, dataUrl) =>
    set((s) => {
      const agentVideos = [...s.agentVideos, { agentId, type, dataUrl }];
      persist({ ...s, agentVideos });
      return { agentVideos };
    }),

  setCurrentAgent: (id) => set({ currentAgentId: id }),

  setSelectedAgents: (agents) => set((s) => {
    const selectedAgents = agents;
    persist({ ...s, selectedAgents });
    return { selectedAgents };
  }),

  setFinalReport: (report) => set((s) => {
    persist({ ...s, finalReport: report });
    return { finalReport: report };
  }),

  setComplete: () => set((s) => {
    persist({ ...s, isComplete: true });
    return { isComplete: true, isStreaming: false, currentAgentId: null };
  }),

  setStreaming: (v) => set({ isStreaming: v }),

  setError: (err) => set({ error: err, isStreaming: false }),

  reset: () => set({ ...initialState, agents: initialAgents() }),
}));

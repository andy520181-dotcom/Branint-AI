import { create } from 'zustand';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import { AgentId, AgentStatus, AgentImage, AgentVideo } from '@/types';
import type { RoundSnapshot } from '@/app/workspace/[sessionId]/workspaceTypes';

/** 实时研究进度步骤，由后端 Wacksman 进度事件驱动 */
export interface ResearchProgressStep {
  /** 工具名称，如 web_search_market_data */
  step: string;
  /** 步骤标题，对应 _ACTION_LABELS 中的人类可读描述 */
  label: string;
  /** 步骤具体细节，如搜索关键词、竞品名称（可为空） */
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
  assetRecommendations?: Record<AgentId, any[]>;
  finalReport: string;
  isComplete: boolean;
  userPrompt: string;
  previousRounds?: RoundSnapshot[];
  strategyClarify?: StrategyClarifyState | null;
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
  } catch (err: unknown) {
    // NOTE: localStorage 容量不足时先清理历史，再重试一次
    const isQuotaError = err instanceof DOMException &&
      (err.name === 'QuotaExceededError' || err.name === 'NS_ERROR_DOM_QUOTA_REACHED');
    if (isQuotaError) {
      try {
        // 强制清空 50% 的旧缓存，然后重试
        const keys: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k?.startsWith(CACHE_PREFIX)) keys.push(k);
        }
        keys.slice(0, Math.ceil(keys.length / 2)).forEach((k) => localStorage.removeItem(k));
        localStorage.setItem(storageKey(sessionId), JSON.stringify(state));
      } catch { /* 重试也失败则静默放弃，不崩溃 */ }
    }
  }
};

export const loadSession = (sessionId: string): PersistedState | null => {
  if (typeof window === 'undefined' || !sessionId) return null;
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    return raw ? (JSON.parse(raw) as PersistedState) : null;
  } catch { return null; }
};

/** Trout 品牌战略 Agent 自适应反问状态 */
export interface StrategyClarifyState {
  /** 是否处于等待用户回答的暂停状态 */
  isPaused: boolean;
  /** Trout 发出的追问文本 */
  questions: string;
  /** 用户的回答（提交前的草稿） */
  answer: string;
  /** 当前已进行的追问轮次（0=未追问，最多3轮） */
  clarifyRound: number;
  /** 上一次会话的 sessionId（用于继续提交时找回上下文） */
  originalSessionId: string;
}

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
  /** 动态下发的视觉动作按钮推荐清单 */
  assetRecommendations: Record<AgentId, any[]>;
  finalReport: string;
  isComplete: boolean;
  isStreaming: boolean;
  error: string | null;
  previousRounds: RoundSnapshot[];
  /** Trout 自适应反问状态，null 表示未触发 */
  strategyClarify: StrategyClarifyState | null;
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
  /** 设置视觉资产推荐列表 */
  setAssetRecommendations: (id: AgentId, recs: any[]) => void;
  setCurrentAgent: (id: AgentId | null) => void;
  setSelectedAgents: (agents: AgentId[]) => void;
  setFinalReport: (report: string) => void;
  setComplete: () => void;
  setStreaming: (v: boolean) => void;
  setError: (err: string) => void;
  setPreviousRounds: (rounds: RoundSnapshot[] | ((prev: RoundSnapshot[]) => RoundSnapshot[])) => void;
  /** 执行时光倒流特效，物理抹除 targetRound 之后的所有轮次以及正在生成的当前轮次 */
  revertToRound: (targetRound: number) => void;
  /** 设置/清除 Trout 反问状态 */
  setStrategyClarify: (state: StrategyClarifyState | null) => void;
  /** 更新反问回答草稿 */
  setStrategyClarifyAnswer: (answer: string) => void;
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
  assetRecommendations: {} as Record<AgentId, any[]>,
  finalReport: '',
  isComplete: false,
  isStreaming: false,
  error: null,
  previousRounds: [],
  strategyClarify: null,
};

const persist = (s: WorkspaceState) =>
  saveSession(s.sessionId, {
    agents: s.agents,
    selectedAgents: s.selectedAgents,
    agentImages: s.agentImages,
    agentVideos: s.agentVideos,
    assetRecommendations: s.assetRecommendations,
    finalReport: s.finalReport,
    isComplete: s.isComplete,
    userPrompt: s.userPrompt,
    previousRounds: s.previousRounds,
    strategyClarify: s.strategyClarify,
  });

/**
 * NOTE: 节流版 persist —— 用于 appendAgentOutput 的高频写入场景。
 * 每 2s 最多真正写一次 localStorage，避免每个 SSE chunk 都 JSON.stringify
 * 大状态对象导致主线程阻塞或 QuotaExceededError 崩溃。
 */
let _throttleTimer: ReturnType<typeof setTimeout> | null = null;
let _pendingState: WorkspaceState | null = null;

const throttledPersist = (s: WorkspaceState) => {
  _pendingState = s;
  if (_throttleTimer !== null) return;
  _throttleTimer = setTimeout(() => {
    if (_pendingState) persist(_pendingState);
    _pendingState = null;
    _throttleTimer = null;
  }, 2000);
};

export const useWorkspaceStore = create<WorkspaceState & WorkspaceActions>((set) => ({
  ...initialState,

  initSession: (sessionId, userPrompt) => {
    set((s) => {
      // 保留 previousRounds！否则多轮对话只要提交就会因 initSession 把历史记录重置为空！
      const finalState = { 
        ...initialState, 
        agents: initialAgents(), 
        agentImages: [], 
        agentVideos: [], 
        assetRecommendations: {} as Record<AgentId, any[]>,
        sessionId, 
        userPrompt, 
        isStreaming: true, 
        previousRounds: s.previousRounds || [] 
      };
      persist(finalState);
      return finalState;
    });
  },

  setAgentStatus: (id, status) =>
    set((s) => {
      const agents = { ...s.agents, [id]: { ...s.agents[id], status } };
      persist({ ...s, agents });
      return { agents };
    }),

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
      // NOTE: 流式追加不做 localStorage 写入，持久化职责已移交给后端实时落盘
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

  setAssetRecommendations: (id, recs) =>
    set((s) => {
      const assetRecommendations = { ...s.assetRecommendations, [id]: recs };
      persist({ ...s, assetRecommendations });
      return { assetRecommendations };
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
    // NOTE: 立刻强制冲刷节流器，确保节流期内未落盘的最终内容在 complete 时被完整写入
    if (_throttleTimer !== null) {
      clearTimeout(_throttleTimer);
      _throttleTimer = null;
      _pendingState = null;
    }
    const next = { ...s, isComplete: true, isStreaming: false as const, currentAgentId: null as null };
    persist(next);
    return { isComplete: true, isStreaming: false, currentAgentId: null };
  }),

  setStreaming: (v) => set({ isStreaming: v }),

  setError: (err) => set({ error: err, isStreaming: false }),

  setPreviousRounds: (rounds) => set((s) => {
    const previousRounds = typeof rounds === 'function' ? rounds(s.previousRounds) : rounds;
    persist({ ...s, previousRounds });
    return { previousRounds };
  }),

  revertToRound: (targetRound) => set((s) => {
    // targetRound 是一般人类认知（如第一轮），对应数组中的 slice(0, targetRound)
    // 这会保留 [0, targetRound - 1] 的历史快照
    const newPrevious = s.previousRounds.slice(0, targetRound);
    
    // 把当前会话直接重置清理，配合 Tailwind AnimatePresence 实现视觉上的突然折叠/消失特效
    const nextState = {
      ...s,
      previousRounds: newPrevious,
      userPrompt: '',
      agents: initialAgents(),
      selectedAgents: null,
      agentImages: [],
      agentVideos: [],
      finalReport: '',
      isComplete: true, // 设为 complete 以停止所有的 isLoading 动画，等待下一次对话
      isStreaming: false as const,
      currentAgentId: null as null,
      error: null
    };
    
    // 强制冲刷写入底层 LocalStorage，确保刷新页面也是回到这个干净状态
    if (_throttleTimer !== null) {
      clearTimeout(_throttleTimer);
      _throttleTimer = null;
      _pendingState = null;
    }
    persist(nextState);
    
    return {
      previousRounds: newPrevious,
      userPrompt: '',
      agents: nextState.agents,
      selectedAgents: null,
      agentImages: [],
      agentVideos: [],
      finalReport: '',
      isComplete: true,
      isStreaming: false,
      currentAgentId: null,
      error: null
    };
  }),

  setStrategyClarify: (state) => set({ strategyClarify: state }),

  setStrategyClarifyAnswer: (answer) =>
    set((s) => ({
      strategyClarify: s.strategyClarify ? { ...s.strategyClarify, answer } : null,
    })),

  reset: () => set({ ...initialState, agents: initialAgents() }),
}));

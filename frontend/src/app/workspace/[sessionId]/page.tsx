'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useWorkspaceStore, loadSession } from '@/store/workspaceStore';
import { useWorkspaceStream } from '@/hooks/useWorkspaceStream';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import type { AgentId, AgentStatus } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { useUserAvatar } from '@/hooks/useUserAvatar';
import { createSession, fetchReport } from '@/lib/api';
import styles from './page.module.css';
import type { RoundSnapshot } from './workspaceTypes';
import { useHistorySidebar } from './hooks/useHistorySidebar';
import { useOutlineDock } from './hooks/useOutlineDock';
import { WorkspaceHistorySidebar } from './components/WorkspaceHistorySidebar';
import { WorkspaceTopBar } from './components/WorkspaceTopBar';
import { WorkspaceHeroEmpty } from './components/WorkspaceHeroEmpty';
import { WorkspaceFeed } from './components/WorkspaceFeed';
import { WorkspaceBottomBar } from './components/WorkspaceBottomBar';
import { WorkspaceOutlineDock } from './components/WorkspaceOutlineDock';

export default function WorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const { user } = useAuth();
  const { t, resolvedLocale } = useLocale();

  const {
    agents, currentAgentId, selectedAgents,
    agentImages, agentVideos, finalReport,
    isComplete, isStreaming, error,
    initSession, userPrompt,
  } = useWorkspaceStore();

  const [restored, setRestored] = useState<boolean | null>(null);
  const [bottomPrompt, setBottomPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [heroFocused, setHeroFocused] = useState(false);

  const [previousRounds, setPreviousRounds] = useState<RoundSnapshot[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(sessionId);
  const currentRoundRef = useRef<HTMLDivElement>(null);
  const avatarDataUrl = useUserAvatar(user?.id);

  // ── 历史记录侧边栏（状态与操作已封装到 Hook）──────────────────────
  const {
    historyOpen, setHistoryOpen,
    historyGroups,
    historyMenuOpenId, setHistoryMenuOpenId,
    historyToast,
    handleHistoryRename,
    handleHistoryPin,
    handleHistoryShare,
    handleHistoryDelete,
  } = useHistorySidebar({ sessionId, t });

  // ── Outline 大纲 Dock（滚动跟踪与面板开关已封装到 Hook）────────────
  const previousRoundPrompts = useMemo(
    () => previousRounds.map((r) => r.userPrompt),
    [previousRounds],
  );

  const {
    outlineItems,
    activeOutlineIndex,
    outlinePanelOpen, setOutlinePanelOpen,
    outlineDockRef,
    jumpToRound,
  } = useOutlineDock({ previousRoundPrompts, userPrompt });

  // ── 输入框自适应高度 ───────────────────────────────────────────────
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 50)}px`;
  }, [bottomPrompt]);

  // ── SSE 流连接 ─────────────────────────────────────────────────────
  const { cancel } = useWorkspaceStream(restored === false ? activeSessionId : null);

  // ── 多轮对话提交 ───────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!bottomPrompt.trim() || !user || submitting) return;
    const promptText = bottomPrompt.trim();
    setSubmitting(true);
    try {
      // NOTE: 收集之前所有轮次的对话历史（用户输入 + Agent 输出），传给后端
      // 使品牌顾问在后续轮次能理解之前的分析上下文
      const history: { user_prompt: string; agent_outputs: Record<string, string> }[] = [];

      for (const r of previousRounds) {
        const outputs: Record<string, string> = {};
        for (const a of Object.values(r.agents)) {
          if (a.output) outputs[a.id] = a.output;
        }
        history.push({ user_prompt: r.userPrompt, agent_outputs: outputs });
      }

      const currentAgents = useWorkspaceStore.getState().agents;
      const currentOutputs: Record<string, string> = {};
      for (const a of Object.values(currentAgents)) {
        if (a.output) currentOutputs[a.id] = a.output;
      }
      if (userPrompt && Object.keys(currentOutputs).length > 0) {
        history.push({ user_prompt: userPrompt, agent_outputs: currentOutputs });
      }

      // 将当前轮次快照存入 previousRounds 用于 UI 展示
      if (userPrompt) {
        const snapshot: RoundSnapshot = {
          sessionId: activeSessionId,
          userPrompt,
          agents: { ...currentAgents },
          selectedAgents: useWorkspaceStore.getState().selectedAgents,
        };
        setPreviousRounds((prev) => [...prev, snapshot]);
      }

      const newSessionId = await createSession(user.id, promptText, history);
      setBottomPrompt('');
      initSession(newSessionId, promptText);
      setActiveSessionId(newSessionId);
      setRestored(false);
      window.history.pushState(null, '', `/workspace/${newSessionId}`);
      setTimeout(() => {
        currentRoundRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
      setSubmitting(false);
    } catch {
      setSubmitting(false);
    }
  };

  // ── 会话恢复（localStorage / sessionStorage / 后端拉取）────────────
  useEffect(() => {
    setRestored(null);

    const saved = loadSession(sessionId);
    if (saved) {
      useWorkspaceStore.setState({
        sessionId,
        userPrompt: saved.userPrompt,
        agents: saved.agents,
        selectedAgents: saved.selectedAgents,
        agentImages: saved.agentImages ?? [],
        agentVideos: saved.agentVideos ?? [],
        finalReport: saved.finalReport,
        isComplete: saved.isComplete,
        isStreaming: false,
        currentAgentId: null,
        error: null,
      });
      setRestored(true);
      return;
    }

    const blankKey = `workspace_blank_${sessionId}`;
    if (typeof window !== 'undefined' && sessionStorage.getItem(blankKey)) {
      useWorkspaceStore.getState().reset();
      useWorkspaceStore.setState({ sessionId });
      setRestored(true);
      setTimeout(() => {
        try { sessionStorage.removeItem(blankKey); } catch { /* ignore */ }
      }, 0);
      return;
    }

    const prompt = sessionStorage.getItem(`prompt_${sessionId}`) ?? '';
    if (prompt) {
      initSession(sessionId, prompt);
      setRestored(false);
      return;
    }

    fetchReport(sessionId)
      .then((data) => {
        const agentsMap = Object.fromEntries(
          AGENT_CONFIGS.map((cfg) => [cfg.id, { id: cfg.id as AgentId, status: 'waiting' as AgentStatus, output: '', researchProgress: [] }]),
        ) as Record<AgentId, { id: AgentId; status: AgentStatus; output: string; researchProgress: [] }>;
        useWorkspaceStore.setState({
          sessionId,
          userPrompt: '',
          agents: agentsMap,
          selectedAgents: null,
          finalReport: data.report ?? '',
          isComplete: true,
          isStreaming: false,
          currentAgentId: null,
          error: null,
        });
      })
      .catch(() => {
        useWorkspaceStore.setState({
          sessionId,
          isStreaming: false,
          isComplete: false,
          error: 'workspace.error.sessionExpired',
        });
      })
      .finally(() => setRestored(true));
  }, [sessionId, initSession]);

  // ── Agent 切换时的 handoff 气泡动画 ───────────────────────────────
  const prevAgentIdRef = useRef<AgentId | null>(null);
  const [handoffMsg, setHandoffMsg] = useState<{ agentId: AgentId; text: string } | null>(null);
  useEffect(() => {
    if (!currentAgentId) return;
    const prev = prevAgentIdRef.current;
    prevAgentIdRef.current = currentAgentId;
    if (prev && prev !== currentAgentId) {
      const currCfg = AGENT_CONFIGS.find((c) => c.id === currentAgentId);
      if (currCfg) {
        setHandoffMsg({
          agentId: prev,
          text: t('workspace.handoff').replace('{name}', t(`agent.${currCfg.id}.name`)),
        });
        const timer = setTimeout(() => setHandoffMsg(null), 2800);
        return () => clearTimeout(timer);
      }
    }
  }, [currentAgentId, t]);

  // ── 新对话 ─────────────────────────────────────────────────────────
  const handleNewConversation = useCallback(() => {
    cancel();
    const newId = crypto.randomUUID();
    sessionStorage.setItem(`workspace_blank_${newId}`, '1');
    setPreviousRounds([]);
    setBottomPrompt('');
    setActiveSessionId(newId);
    setOutlinePanelOpen(false);
    setHistoryOpen(false);
    setHandoffMsg(null);
    prevAgentIdRef.current = null;
    router.replace(`/workspace/${newId}`);
  }, [cancel, router, setHistoryOpen, setOutlinePanelOpen]);

  // ── 渲染逻辑 ───────────────────────────────────────────────────────
  const hasFeedContent = useMemo(() => {
    if (previousRounds.length > 0) return true;
    if (userPrompt?.trim()) return true;
    if (isStreaming) return true;
    if (finalReport?.trim()) return true;
    if (Object.values(agents).some((a) => a.status !== 'waiting')) return true;
    return false;
  }, [previousRounds.length, userPrompt, isStreaming, finalReport, agents]);

  const showHeroInput = restored !== null && !error && !hasFeedContent;

  const visibleConfigs = selectedAgents
    ? AGENT_CONFIGS.filter((c) => selectedAgents.includes(c.id))
    : AGENT_CONFIGS;

  return (
    <div className={styles.page}>
      <WorkspaceHistorySidebar
        historyOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        historyGroups={historyGroups}
        sessionId={sessionId}
        resolvedLocale={resolvedLocale}
        historyMenuOpenId={historyMenuOpenId}
        setHistoryMenuOpenId={setHistoryMenuOpenId}
        onNavigateSession={(sid) => router.replace(`/workspace/${sid}`)}
        onRename={handleHistoryRename}
        onPin={handleHistoryPin}
        onShare={handleHistoryShare}
        onDelete={handleHistoryDelete}
        t={t}
      />

      <WorkspaceTopBar
        historyOpen={historyOpen}
        onToggleHistory={() => setHistoryOpen(!historyOpen)}
        onNewConversation={handleNewConversation}
        isComplete={isComplete}
        error={error}
        showHeroInput={showHeroInput}
        t={t}
      />

      <main className={`${styles.main} ${showHeroInput ? styles.mainHeroShell : ''}`}>
        {showHeroInput ? (
          <WorkspaceHeroEmpty
            textareaRef={textareaRef}
            bottomPrompt={bottomPrompt}
            setBottomPrompt={setBottomPrompt}
            heroFocused={heroFocused}
            setHeroFocused={setHeroFocused}
            onSubmit={handleSubmit}
            submitting={submitting}
            user={user}
            t={t}
          />
        ) : (
          <>
            <WorkspaceFeed
              feedRef={currentRoundRef}
              previousRounds={previousRounds}
              userPrompt={userPrompt}
              avatarDataUrl={avatarDataUrl}
              isStreaming={isStreaming}
              currentAgentId={currentAgentId}
              agents={agents}
              visibleConfigs={visibleConfigs}
              agentImages={agentImages}
              agentVideos={agentVideos}
              handoffMsg={handoffMsg}
              error={error}
              t={t}
            />
            <WorkspaceBottomBar
              textareaRef={textareaRef}
              bottomPrompt={bottomPrompt}
              setBottomPrompt={setBottomPrompt}
              onSubmit={handleSubmit}
              isStreaming={isStreaming}
              submitting={submitting}
              onCancel={cancel}
              t={t}
            />
          </>
        )}
      </main>

      <WorkspaceOutlineDock
        outlineDockRef={outlineDockRef}
        outlineItems={outlineItems}
        activeOutlineIndex={activeOutlineIndex}
        outlinePanelOpen={outlinePanelOpen}
        onMouseEnter={() => setOutlinePanelOpen(true)}
        onJump={jumpToRound}
        t={t}
      />

      {historyToast ? (
        <div className={styles.historyToast} role="status">
          {historyToast}
        </div>
      ) : null}
    </div>
  );
}

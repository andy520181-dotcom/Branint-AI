'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useWorkspaceStore, loadSession } from '@/store/workspaceStore';
import { useWorkspaceStream } from '@/hooks/useWorkspaceStream';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import type { AgentId, AgentStatus, HistoryItem } from '@/types';
import { useAuth, useHistory } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { useUserAvatar } from '@/hooks/useUserAvatar';
import { createSession, fetchReport } from '@/lib/api';
import styles from './page.module.css';
import type { RoundSnapshot } from './workspaceTypes';
import { groupByDate } from './workspaceUtils';
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
  const { getHistory, updateHistoryTitle, removeHistoryItem, pinHistoryToTop } = useHistory();
  const { t, resolvedLocale } = useLocale();

  const { agents, currentAgentId, selectedAgents, agentImages, agentVideos, finalReport, isComplete, isStreaming, error, initSession, userPrompt } =
    useWorkspaceStore();

  const [restored, setRestored] = useState<boolean | null>(null);
  const [bottomPrompt, setBottomPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [heroFocused, setHeroFocused] = useState(false);

  const [previousRounds, setPreviousRounds] = useState<RoundSnapshot[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(sessionId);
  const currentRoundRef = useRef<HTMLDivElement>(null);
  const avatarDataUrl = useUserAvatar(user?.id);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyGroups, setHistoryGroups] = useState<{ label: string; items: HistoryItem[] }[]>([]);
  const [historyMenuOpenId, setHistoryMenuOpenId] = useState<string | null>(null);
  const [historyToast, setHistoryToast] = useState('');

  const refreshHistory = useCallback(() => {
    setHistoryGroups(groupByDate(getHistory(), t));
  }, [getHistory, t]);

  const showHistoryToast = useCallback((msg: string) => {
    setHistoryToast(msg);
    setTimeout(() => setHistoryToast(''), 2200);
  }, []);

  useEffect(() => {
    if (historyOpen) refreshHistory();
    else setHistoryMenuOpenId(null);
  }, [historyOpen, refreshHistory]);

  useEffect(() => {
    if (!historyMenuOpenId) return;
    const onDown = (e: MouseEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest('[data-history-menu-root]')) return;
      setHistoryMenuOpenId(null);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [historyMenuOpenId]);

  const handleHistoryRename = useCallback(
    (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      const next = window.prompt(t('workspace.history.renamePrompt'), item.title);
      if (next === null) return;
      const trimmed = next.trim();
      if (!trimmed) return;
      updateHistoryTitle(item.sessionId, trimmed);
      refreshHistory();
    },
    [t, updateHistoryTitle, refreshHistory],
  );

  const handleHistoryPin = useCallback(
    (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      pinHistoryToTop(item.sessionId);
      refreshHistory();
    },
    [pinHistoryToTop, refreshHistory],
  );

  const handleHistoryShare = useCallback(
    async (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      const url = `${window.location.origin}/workspace/${item.sessionId}`;
      try {
        await navigator.clipboard.writeText(url);
        showHistoryToast(t('workspace.history.shareCopied'));
      } catch {
        showHistoryToast(t('workspace.history.shareFailed'));
      }
    },
    [t, showHistoryToast],
  );

  const handleHistoryDelete = useCallback(
    (item: HistoryItem) => {
      if (!window.confirm(t('workspace.history.deleteConfirm'))) return;
      setHistoryMenuOpenId(null);
      removeHistoryItem(item.sessionId);
      refreshHistory();
      if (item.sessionId === sessionId) {
        const rest = getHistory();
        if (rest[0]) router.replace(`/workspace/${rest[0].sessionId}`);
        else router.replace('/');
      }
    },
    [t, removeHistoryItem, refreshHistory, getHistory, sessionId, router],
  );

  const outlineItems = useMemo(() => {
    const items: { id: string; prompt: string }[] = [];
    previousRounds.forEach((r, i) => {
      items.push({ id: `workspace-round-${i}`, prompt: r.userPrompt });
    });
    if (userPrompt?.trim()) {
      items.push({ id: 'workspace-round-active', prompt: userPrompt });
    }
    return items;
  }, [previousRounds, userPrompt]);

  const [activeOutlineIndex, setActiveOutlineIndex] = useState(0);

  const updateOutlineActive = useCallback(() => {
    if (outlineItems.length === 0) return;
    const line = Math.min(140, (typeof window !== 'undefined' ? window.innerHeight : 800) * 0.2);
    let active = 0;
    for (let i = outlineItems.length - 1; i >= 0; i--) {
      const el = document.getElementById(outlineItems[i].id);
      if (!el) continue;
      if (el.getBoundingClientRect().top <= line) {
        active = i;
        break;
      }
    }
    setActiveOutlineIndex((prev) => (prev === active ? prev : active));
  }, [outlineItems]);

  useEffect(() => {
    if (outlineItems.length === 0) return;
    updateOutlineActive();
    window.addEventListener('scroll', updateOutlineActive, { passive: true });
    window.addEventListener('resize', updateOutlineActive);
    return () => {
      window.removeEventListener('scroll', updateOutlineActive);
      window.removeEventListener('resize', updateOutlineActive);
    };
  }, [outlineItems, updateOutlineActive]);

  const jumpToRound = useCallback((id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const outlineDockRef = useRef<HTMLElement | null>(null);
  const [outlinePanelOpen, setOutlinePanelOpen] = useState(false);

  useEffect(() => {
    if (!outlinePanelOpen) return;
    const onDown = (e: MouseEvent) => {
      const dock = outlineDockRef.current;
      if (dock && !dock.contains(e.target as Node)) {
        setOutlinePanelOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [outlinePanelOpen]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 50)}px`;
  }, [bottomPrompt]);

  const { cancel } = useWorkspaceStream(restored === false ? activeSessionId : null);

  const handleSubmit = async () => {
    if (!bottomPrompt.trim() || !user || submitting) return;
    const promptText = bottomPrompt.trim();
    setSubmitting(true);
    try {
      // NOTE: 收集之前所有轮次的对话历史（用户输入 + Agent 输出），传给后端
      // 使品牌顾问在后续轮次能理解之前的分析上下文
      const history: { user_prompt: string; agent_outputs: Record<string, string> }[] = [];

      // 1. previousRounds 中的历史轮次
      for (const r of previousRounds) {
        const outputs: Record<string, string> = {};
        for (const a of Object.values(r.agents)) {
          if (a.output) outputs[a.id] = a.output;
        }
        history.push({ user_prompt: r.userPrompt, agent_outputs: outputs });
      }

      // 2. 当前轮次（如果有内容）
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

      const new_session_id = await createSession(user.id, promptText, history);
      setBottomPrompt('');

      initSession(new_session_id, promptText);
      setActiveSessionId(new_session_id);
      setRestored(false);

      window.history.pushState(null, '', `/workspace/${new_session_id}`);

      setTimeout(() => {
        currentRoundRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);

      setSubmitting(false);
    } catch {
      setSubmitting(false);
    }
  };

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
        try {
          sessionStorage.removeItem(blankKey);
        } catch {
          /* ignore */
        }
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
          AGENT_CONFIGS.map((cfg) => [cfg.id, { id: cfg.id as AgentId, status: 'waiting' as AgentStatus, output: '' }]),
        ) as Record<AgentId, { id: AgentId; status: AgentStatus; output: string }>;
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

  const handleNewConversation = useCallback(() => {
    cancel();
    const newId = crypto.randomUUID();
    sessionStorage.setItem(`workspace_blank_${newId}`, '1');
    setPreviousRounds([]);
    setBottomPrompt('');
    setActiveSessionId(newId);
    setActiveOutlineIndex(0);
    setHistoryOpen(false);
    setHistoryMenuOpenId(null);
    setOutlinePanelOpen(false);
    setHandoffMsg(null);
    prevAgentIdRef.current = null;
    router.replace(`/workspace/${newId}`);
  }, [cancel, router]);

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
        onToggleHistory={() => setHistoryOpen((v) => !v)}
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

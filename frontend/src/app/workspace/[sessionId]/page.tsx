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
import { createSession, continueSession, fetchSnapshot, uploadAsset } from '@/lib/api';
import styles from './page.module.css';
import type { RoundSnapshot } from './workspaceTypes';
import { buildFeedRouteFromMiddleKeys } from './workspaceUtils';
import { useHistorySidebar } from './hooks/useHistorySidebar';
import { useOutlineDock } from './hooks/useOutlineDock';
import { WorkspaceHistorySidebar } from './components/WorkspaceHistorySidebar';
import { WorkspaceTopBar } from './components/WorkspaceTopBar';
import { WorkspaceHeroEmpty } from './components/WorkspaceHeroEmpty';
import { WorkspaceFeed } from './components/WorkspaceFeed';
import { WorkspaceBottomBar } from './components/WorkspaceBottomBar';
import { WorkspaceOutlineDock } from './components/WorkspaceOutlineDock';
import { WorkspaceSkeleton } from './components/WorkspaceSkeleton';

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
    previousRounds, setPreviousRounds,
    strategyClarify, setStrategyClarify,
  } = useWorkspaceStore();

  const [restored, setRestored] = useState<boolean | null>(null);
  const [bottomPrompt, setBottomPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [heroFocused, setHeroFocused] = useState(false);
  // 附件状态：存储待上传的本地文件列表
  const [attachments, setAttachments] = useState<Array<{ file: File; previewUrl: string }>>([]);
  // NOTE: feedToast 供 Agent 卡片操作按钮（复制、分享、下载）展示轻量通知，
  // 替代原来阻塞主线程的 alert()，复用全局 historyToast 的样式
  const [feedToast, setFeedToast] = useState('');
  const showFeedToast = useCallback((msg: string) => {
    setFeedToast(msg);
    setTimeout(() => setFeedToast(''), 2200);
  }, []);

  const currentRoundRef = useRef<HTMLDivElement>(null);
  const avatarDataUrl = useUserAvatar(user?.id);

  // ── 历史记录侧边栏（状态与操作已封装到 Hook）──────────────────────
  const {
    historyOpen, setHistoryOpen,
    historyGroups,
    historyLoading,
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
  const { cancel } = useWorkspaceStream(restored === false ? sessionId : null);

  // ── 统一提交入口 ────────────────────────────────────────────────────

  /**
   * 将当前正在进行的半轮对话快照（包含未完全结束的 agents 状态）存入历史记录
   * 用于页面跳转或刷新时的容错兜底
   */
  const commitCurrentRoundToHistory = useCallback((currentAgents: Record<string, AgentState>) => {
    if (userPrompt) {
      const currentSelectedAgents = useWorkspaceStore.getState().selectedAgents;
      const snapshot: RoundSnapshot = {
        sessionId: sessionId,
        userPrompt,
        agents: { ...currentAgents },
        selectedAgents: currentSelectedAgents,
      };
      setPreviousRounds((prev) => {
        const nextRounds = [...prev, snapshot];
        // 同步写入 store 供其他组件读取
        useWorkspaceStore.setState({ previousRounds: nextRounds });
        return nextRounds;
      });
    }
  }, [sessionId, userPrompt, setPreviousRounds]);

  /**
   * 构建多轮对话历史负载。
   * 收集 previousRounds + 当前轮的 agent 输出，供后端理解上下文。
   */
  const buildHistory = useCallback(() => {
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
    return { history, currentAgents };
  }, [previousRounds, userPrompt]);

  const handleSubmit = async (overridePrompt?: string) => {
    const inputText = (overridePrompt ?? bottomPrompt).trim();
    if (!inputText || !user || submitting) return;
    setSubmitting(true);

    // NOTE: 如果 Trout 正在等待追问回答，把用户输入作为答案而非新 prompt
    if (strategyClarify?.isPaused) {
      try {
        const clarifyRound = strategyClarify.clarifyRound;
        // 收集对话历史（追问分支）
        const { history, currentAgents } = buildHistory();

        // C. 将当前半成品轮次合并入本地快照
        commitCurrentRoundToHistory(currentAgents);

        setStrategyClarify(null);
        setBottomPrompt('');

        // NOTE: 追问回复不创建新会话，复用同一个 sessionId
        // URL 保持不变，侧边栏历史记录依旧是同一条
        initSession(sessionId, inputText);
        setRestored(true); // 挂起 SSE，等待后端续写

        setTimeout(() => {
          currentRoundRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);

        // 后台调用 PATCH /continue，不创建新历史记录
        try {
          await continueSession(
            sessionId,
            inputText,
            history,
            [],
            inputText,    // Trout 专用的真实答案
            clarifyRound,
          );
        } catch (err) {
          console.error('Failed to continue session on clarification reply:', err);
        } finally {
          setRestored(false);
          setSubmitting(false);
        }
      } catch (err) {
        console.error(err);
        setSubmitting(false);
      }
      return;
    }


    // ── 普通多轮对话提交 ────
    const promptText = inputText;
    setSubmitting(true);
    try {
      // NOTE: 收集对话历史（普通分支）复用 buildHistory()
      const { history, currentAgents } = buildHistory();

      // 2. 将当前轮次存入 previousRounds 用于 UI 固定展示
      commitCurrentRoundToHistory(currentAgents);

      // 先上传附件，拿到服务器上的 URL 列表
      const uploadedUrls: string[] = [];
      if (attachments.length > 0) {
        for (const item of attachments) {
          try {
            const { url } = await uploadAsset(item.file);
            uploadedUrls.push(url);
          } catch (err) {
            // NOTE: 单个文件上传失败跳过不中断，可后续加 toast 通知
            console.error('附件上传失败:', err);
          }
        }
        // 释放预览 URL 内存，并清空列表
        attachments.forEach((it) => URL.revokeObjectURL(it.previewUrl));
        setAttachments([]);
      }

      // 检测是否属于完全空白的新建会话（首次提交）
      const isFirstTurn = previousRounds.length === 0 && !userPrompt;

      // NOTE: 多轮对话不创建新 session，复用 sessionId
      // URL 保持不变，用户在侧边栏只会看到一条历史记录
      setBottomPrompt('');
      initSession(sessionId, promptText);
      setRestored(true); // 挂起 SSE 连接，等待后端续写完成

      setTimeout(() => {
        currentRoundRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);

      try {
        if (isFirstTurn) {
          // 真正的首轮对话，必须全量创建数据库记录
          await createSession(user.id, promptText, sessionId, promptText.slice(0, 40), undefined, uploadedUrls);
        } else {
          // 附加历史记录的多轮追问，调用 PATCH
          await continueSession(sessionId, promptText, history, uploadedUrls);
        }
      } catch (err) {
        console.error('Failed to continue session on multi-turn reply:', err);
      } finally {
        // 无论成功失败，开放 SSE 长连接请求阀门
        setRestored(false);
        setSubmitting(false);
      }
    } catch (err) {
      console.error(err);
      setSubmitting(false);
    }
  };

  // ── 会话恢复（优先拉取后端 snapshot，localStorage 仅作第二保障）────────────
  useEffect(() => {
    setRestored(null);

    // NOTE: 立即将 Store 重置为干净初始状态，防止上一个 session 的旧数据
    // 污染新 session 的 hasFeedContent 计算，导致历史会话点击后内容留白。
    // reset() 后立即设置新 sessionId，保证后续 setState patch 能找到正确归属。
    useWorkspaceStore.getState().reset();
    useWorkspaceStore.setState({ sessionId });

    // 第一优先：检查是否是新建空白会话（sessionStorage 标记）
    const blankKey = `workspace_blank_${sessionId}`;
    if (typeof window !== 'undefined' && sessionStorage.getItem(blankKey)) {
      setRestored(true);
      setTimeout(() => {
        try { sessionStorage.removeItem(blankKey); } catch { /* ignore */ }
        textareaRef.current?.focus();
      }, 0);
      return;
    }

    // 核心恢复：从后端拉取 snapshot（刷新、换设备、分享链接均有效）
    // NOTE: 必须先调 snapshot，才能判断这个 sessionId 是否已有后端数据。
    // 原来的「第二优先：sessionStorage prompt」会在刷新时误触发 initSession 重连 SSE，
    // 导致数据重跑或丢失，因此降级为 snapshot 失败时的最后兜底。
    fetchSnapshot(sessionId)
      .then((snap) => {
        const cached = loadSession(sessionId);
        const hasAnyOutput = Object.values(snap.agent_outputs ?? {}).some((v) => (v as string)?.trim());
        const promptFromLanding = typeof window !== 'undefined'
          ? sessionStorage.getItem(`prompt_${sessionId}`)
          : null;

        /*
         * 仅当落地页刚写入的 sessionStorage.prompt 存在时才 initSession。
         * 绝不能用 snap.user_prompt 兜底触发 initSession，否则刷新时会在「尚未落盘」阶段
         * 误判为全新会话并清空 Store、重复跑一遍生成。
         */
        if (snap.status === 'pending' && !hasAnyOutput && promptFromLanding) {
          initSession(sessionId, promptFromLanding);
          try {
            sessionStorage.removeItem(`prompt_${sessionId}`);
          } catch {
            /* ignore */
          }
          setRestored(false);
          return;
        }

        const routeFromSnap = buildFeedRouteFromMiddleKeys(snap.selected_agents);
        const selectedAgentsResolved = routeFromSnap ?? cached?.selectedAgents ?? null;

        const agentsMap = Object.fromEntries(
          AGENT_CONFIGS.map((cfg) => [
            cfg.id,
            {
              id: cfg.id as AgentId,
              status: (snap.agent_statuses?.[cfg.id] ?? 'waiting') as AgentStatus,
              output: snap.agent_outputs?.[cfg.id] ?? '',
              researchProgress: [] as [],
            },
          ]),
        ) as Record<AgentId, { id: AgentId; status: AgentStatus; output: string; researchProgress: [] }>;

        // ── 判断会话活跃度 ─────────────────────────────────────────────────
        // hasFullOutput: 是否已有完成的 agent 输出（用于识别"进程崩溃导致状态卡住"的 running 会话）
        const hasFullOutput = hasAnyOutput && Object.values(snap.agent_statuses ?? {}).some(
          (s) => s === 'completed'
        );

        // 真正的活跃会话：running 且没有任何 completed agent（说明仍在进行中）
        // 或者 pending 且已有部分输出（正在运行但节流期内）
        const liveSession =
          (snap.status === 'running' && !hasFullOutput) ||
          (snap.status === 'pending' && hasAnyOutput && !hasFullOutput);

        // treatAsCompleted：明确完成 OR 状态卡住的 running（有完整输出视为完成）
        // NOTE: 这是修复"历史会话点击触发重新生成"的核心判断。
        // 数据库 running 状态可能因进程崩溃未被置为 completed，
        // 若有完整 agent 输出，前端保守地视为已完成，不触发 SSE/Orchestrator。
        const treatAsCompleted =
          snap.status === 'completed' ||
          snap.status === 'error' ||
          (snap.status === 'running' && hasFullOutput);

        useWorkspaceStore.setState({
          sessionId,
          userPrompt: snap.user_prompt ?? '',
          agents: agentsMap,
          selectedAgents: selectedAgentsResolved,
          agentImages: snap.agent_media?.agentImages ?? [],
          agentVideos: snap.agent_media?.agentVideos ?? [],
          finalReport: snap.report ?? '',
          isComplete: treatAsCompleted,
          isStreaming: liveSession,
          currentAgentId: null,
          error: null,
        });

        if (cached?.strategyClarify) {
          useWorkspaceStore.setState({ strategyClarify: cached.strategyClarify });
        }

        // NOTE: 从服务端备份重建历史轮次（当换电脑、清缓存或强制刷新时起效）
        const historyFromBackend: RoundSnapshot[] = (snap.conversation_history || []).map(
          (h: any, i: number) => {
            const histAgents: Record<string, any> = {};
            for (const [aId, aOut] of Object.entries(h.agent_outputs ?? {})) {
              if (aOut) {
                histAgents[aId] = {
                  id: aId,
                  status: 'completed',
                  output: String(aOut),
                  researchProgress: [],
                };
              }
            }
            return {
              sessionId: `${sessionId}-hist-${i}`,
              userPrompt: h.user_prompt ?? '',
              agents: histAgents,
              selectedAgents: null,
            };
          }
        );

        setPreviousRounds(historyFromBackend);

        if (treatAsCompleted) {
          // 已完成（包含崩溃卡住的 running）：直接还原展示，绝不触发 SSE
          if (snap.status === 'error' && !hasAnyOutput) {
            useWorkspaceStore.setState({ isStreaming: false, error: null });
            // 延迟 600ms 等 UI 渲染完毕再弹出 Toast，避免骨架屏切换期间闪烁
            setTimeout(() => {
              showFeedToast(t('workspace.error.lastRoundFailed'));
            }, 600);
          }
          setRestored(true);
        } else if (liveSession) {
          // 真正进行中的会话：连接 SSE 续传
          setRestored(false);
        } else {
          // pending 全新会话且无输出：等待 initSession 调用，暂不触发 SSE
          setRestored(true);
        }
      })
      .catch(async () => {
        // snapshot 接口失败（404 等），回退到 sessionStorage prompt（真正的首次访问）
        const prompt = sessionStorage.getItem(`prompt_${sessionId}`) ?? '';
        if (prompt) {
          // 提前填充本地 Store，让屏幕立刻显示“用户气泡”而非白屏
          initSession(sessionId, prompt);
          
          const userId = sessionStorage.getItem(`user_${sessionId}`);
          if (userId) {
            try {
              // 【核心异步创建】：阻塞等待写库完成后，再允许 SSE 连接
              await createSession(userId, prompt, sessionId, prompt.slice(0, 40));
            } catch (createErr) {
              console.error('Failed to create session on landing redirect:', createErr);
            }
          }

          // 核心：打开 SSE 连接闸门
          setRestored(false);
          return;
        }
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
            previousRounds: saved.previousRounds ?? [],
          });
          if (saved.strategyClarify) {
            useWorkspaceStore.setState({ strategyClarify: saved.strategyClarify });
          }
        } else {
          // 如果后端快照 404 且本地也没有暂存（比如刷新全新建的页面，或者访问了过期的分享链接），
          // 不要抛出致命错误阻断 UI，而是平滑降级为一个新的空白对话页，让用户可以直接打字。
          useWorkspaceStore.setState({
            sessionId,
            isStreaming: false,
            isComplete: false,
            error: null,
          });
        }
        setRestored(true);
      });
  }, [sessionId, initSession, setPreviousRounds]);

  // ── Agent 切换时的 handoff 气泡动画 ───────────────────────────────
  const prevAgentIdRef = useRef<AgentId | null>(null);
  const [handoffMsg, setHandoffMsg] = useState<{ agentId: AgentId; text: string } | null>(null);
  useEffect(() => {
    if (!currentAgentId) return;
    const prev = prevAgentIdRef.current;
    prevAgentIdRef.current = currentAgentId;
    if (prev && prev !== currentAgentId) {
      const prevCfg = AGENT_CONFIGS.find((c) => c.id === prev);
      const currCfg = AGENT_CONFIGS.find((c) => c.id === currentAgentId);
      // NOTE: 只有当不是同一个角色（例如品牌顾问传给市场研究）时，才显示交接提示文案
      if (currCfg && (!prevCfg || prevCfg.charName !== currCfg.charName)) {
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
    setBottomPrompt('');
    setOutlinePanelOpen(false);
    setHistoryOpen(false);
    setHandoffMsg(null);
    prevAgentIdRef.current = null;
    // NOTE: router.replace 会更新 useParams().sessionId，
    // 无需额外维护 activeSessionId 状态
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

  const isLoading = restored === null;
  const showHeroInput = !isLoading && !error && !hasFeedContent;

  const visibleConfigs = selectedAgents
    ? AGENT_CONFIGS.filter((c) => selectedAgents.includes(c.id))
    : AGENT_CONFIGS;

  return (
    <div className={styles.page}>
      <WorkspaceHistorySidebar
        historyOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        historyGroups={historyGroups}
        historyLoading={historyLoading}
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
        isLoading={isLoading}
        t={t}
      />

      <main className={`${styles.main} ${showHeroInput ? styles.mainHeroShell : ''}`}>
        {isLoading ? (
          /* 加载过渡态：骨架屏平滑过渡 */
          <WorkspaceSkeleton />
        ) : showHeroInput ? (
          <WorkspaceHeroEmpty
            textareaRef={textareaRef}
            bottomPrompt={bottomPrompt}
            setBottomPrompt={setBottomPrompt}
            heroFocused={heroFocused}
            setHeroFocused={setHeroFocused}
            onSubmit={() => handleSubmit()}
            submitting={submitting}
            user={user}
            attachments={attachments}
            onAttachmentsChange={setAttachments}
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
              sessionId={sessionId}
              agentImages={agentImages}
              agentVideos={agentVideos}
              handoffMsg={handoffMsg}
              error={error}
              isClarifying={!!strategyClarify?.isPaused}
              onToast={showFeedToast}
              t={t}
            />
            <WorkspaceBottomBar
              textareaRef={textareaRef}
              bottomPrompt={bottomPrompt}
              setBottomPrompt={setBottomPrompt}
              onSubmit={() => handleSubmit()}
              isStreaming={isStreaming}
              submitting={submitting}
              onCancel={cancel}
              attachments={attachments}
              onAttachmentsChange={setAttachments}
              isClarifying={!!strategyClarify?.isPaused}
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

      {/* Agent 卡片操作（复制/分享/下载）触发的 Toast，复用 historyToast 样式 */}
      {feedToast ? (
        <div className={styles.historyToast} role="status">
          {feedToast}
        </div>
      ) : null}
    </div>
  );
}

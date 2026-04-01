'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useWorkspaceStore, loadSession } from '@/store/workspaceStore';
import { useWorkspaceStream } from '@/hooks/useWorkspaceStream';
import { AGENT_CONFIGS, AgentId } from '@/types';
import type { HistoryItem, AgentStatus } from '@/types';
import { useAuth, useHistory } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { useUserAvatar } from '@/hooks/useUserAvatar';
import { createSession, fetchReport } from '@/lib/api';
import { translateWorkspaceError } from '@/i18n/messages';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import landingStyles from '../../page.module.css';
import styles from './page.module.css';

/** 单轮分析的快照，用于在同页面保留历史内容 */
interface RoundSnapshot {
  sessionId: string;
  userPrompt: string;
  agents: Record<AgentId, { id: AgentId; status: AgentStatus; output: string }>;
  selectedAgents: AgentId[] | null;
}

/** 将历史列表按日期分组 */
function groupByDate(
  items: HistoryItem[],
  t: (key: string) => string,
): { label: string; items: HistoryItem[] }[] {
  const now = new Date();
  const todayStr = now.toDateString();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

  const today: HistoryItem[] = [];
  const week: HistoryItem[] = [];
  const month: HistoryItem[] = [];
  const older: HistoryItem[] = [];

  for (const item of items) {
    const d = new Date(item.createdAt);
    if (d.toDateString() === todayStr) today.push(item);
    else if (d >= weekAgo) week.push(item);
    else if (d >= monthAgo) month.push(item);
    else older.push(item);
  }

  return [
    { label: t('history.group.today'), items: today },
    { label: t('history.group.week'), items: week },
    { label: t('history.group.month'), items: month },
    { label: t('history.group.older'), items: older },
  ].filter((g) => g.items.length > 0);
}

/** 单行截断，用于导航列表与缩略划条 */
function truncatePromptOneLine(s: string, max = 44): string {
  const t = s.replace(/\s+/g, ' ').trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function WorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const { user } = useAuth();
  const { getHistory, updateHistoryTitle, removeHistoryItem, pinHistoryToTop } = useHistory();
  const { t, resolvedLocale } = useLocale();

  const { agents, currentAgentId, selectedAgents, finalReport, isComplete, isStreaming, error, initSession, userPrompt } =
    useWorkspaceStore();

  // null = 尚未确定（useEffect 运行前），避免切换 session 时短暂触发 SSE
  const [restored, setRestored] = useState<boolean | null>(null);
  const [bottomPrompt, setBottomPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [heroFocused, setHeroFocused] = useState(false);
  void finalReport;

  // NOTE: 历史轮次 — 同一页面连续追加分析，不跳转 URL
  const [previousRounds, setPreviousRounds] = useState<RoundSnapshot[]>([]);
  // 实际连接 SSE 的 sessionId，提交新分析后直接更新（不依赖 URL 变化）
  const [activeSessionId, setActiveSessionId] = useState<string>(sessionId);
  const currentRoundRef = useRef<HTMLDivElement>(null);
  // 用户头像（本地缓存的 data URL）
  const avatarDataUrl = useUserAvatar(user?.id);

  // 历史侧边栏
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

  /** 本轮对话内用户发言锚点列表（图1 短划 + 图2 展开列表） */
  const outlineItems = useMemo(() => {
    const items: { id: string; prompt: string }[] = [];
    for (const r of previousRounds) {
      items.push({ id: `workspace-round-${r.sessionId}`, prompt: r.userPrompt });
    }
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

  /**
   * 右侧对话导航：鼠标进入展开；收起条件为「点击发生在该导航之外」
   * （即点击主内容、顶栏、底栏等任意不在 nav 内的区域），不包含点击白底列表或短划条本身。
   */
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

  // 自动调整高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 50)}px`;
  }, [bottomPrompt]);

  // restored=null 时尚未确定，传 null 避免提前连接
  // restored=true 时已恢复缓存，不需要重连
  // restored=false 时是新会话，正常连接
  const { cancel } = useWorkspaceStream(restored === false ? activeSessionId : null);

  // NOTE: 不再跳转新 URL，而是在同一页面追加新轮次，保留历史内容供回看
  const handleSubmit = async () => {
    if (!bottomPrompt.trim() || !user) return;
    setSubmitting(true);
    try {
      // ① 快照当前轮次内容，追加到历史
      if (userPrompt) {
        const snapshot: RoundSnapshot = {
          sessionId: activeSessionId,
          userPrompt,
          agents: { ...useWorkspaceStore.getState().agents },
          selectedAgents: useWorkspaceStore.getState().selectedAgents,
        };
        setPreviousRounds(prev => [...prev, snapshot]);
      }

      // ② 创建新 session
      const new_session_id = await createSession(user.id, bottomPrompt.trim());
      setBottomPrompt('');

      // ③ 直接初始化新会话，不 router.push
      initSession(new_session_id, bottomPrompt.trim());
      setActiveSessionId(new_session_id);
      setRestored(false);

      // 更新地址栏（不触发 Next.js 路由重渲染）
      window.history.pushState(null, '', `/workspace/${new_session_id}`);

      // 滚动到新生成区域顶部
      setTimeout(() => {
        currentRoundRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);

      setSubmitting(false);
    } catch {
      setSubmitting(false);
    }
  };

  /** 获取用户头像首字母（无头像时的 fallback） */
  const userInitial = useCallback(() => {
    if (!user) return 'U';
    const name = (user as { name?: string; email?: string }).name
      ?? (user as { email?: string }).email
      ?? 'U';
    return name.charAt(0).toUpperCase();
  }, [user]);

  // 初始化：优先从 localStorage 恢复缓存，否则发起新会话
  useEffect(() => {
    setRestored(null); // 切换 sessionId 时先重置，阻断 SSE

    const saved = loadSession(sessionId);
    if (saved) {
      // ① 本地有完整缓存，直接恢复，不触发 SSE
      useWorkspaceStore.setState({
        sessionId,
        userPrompt: saved.userPrompt,
        agents: saved.agents,
        selectedAgents: saved.selectedAgents,
        finalReport: saved.finalReport,
        isComplete: saved.isComplete,
        isStreaming: false,
        currentAgentId: null,
        error: null,
      });
      setRestored(true);
      return;
    }

    /* 「新建对话」占位：须排在 fetch 之前；标记不可在 effect 内同步 remove，否则 React Strict Mode
       会连续跑两次 effect，第二次已读不到标记而误走 fetchReport → 会话过期 */
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
      // ② 同一浏览器 Tab 刚创建的新会话，有 prompt 凭证 → 正常连接 SSE 生成
      initSession(sessionId, prompt);
      setRestored(false);
      return;
    }

    // ③ 历史会话，本地无缓存（可能是旧数据或跨设备）
    //    先尝试从后端拉取已完成的报告，避免误触发重新生成
    fetchReport(sessionId)
      .then((data) => {
        const agentsMap = Object.fromEntries(
          AGENT_CONFIGS.map((cfg) => [cfg.id, { id: cfg.id as AgentId, status: 'waiting' as AgentStatus, output: '' }])
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
        // 后端也没有 → 显示过期提示，不启动 SSE
        useWorkspaceStore.setState({
          sessionId,
          isStreaming: false,
          isComplete: false,
          error: 'workspace.error.sessionExpired',
        });
      })
      .finally(() => setRestored(true)); // 无论如何阻断 SSE
  }, [sessionId, initSession]);

  // 监听 Agent 切换，触发传递气泡
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

  /** 无历史、无当前轮内容时：与首页一致的居中标题 + 输入（新建对话 / 空白会话） */
  const showHeroInput = restored !== null && !error && !hasFeedContent;

  const visibleConfigs = selectedAgents
    ? AGENT_CONFIGS.filter((c) => selectedAgents.includes(c.id))
    : AGENT_CONFIGS;

  return (
    <div className={styles.page}>

      {/* 历史侧边栏遮罩 */}
      {historyOpen && (
        <div className={styles.historyOverlay} onClick={() => setHistoryOpen(false)} />
      )}

      {/* 历史侧边栏 */}
      <aside className={`${styles.historySidebar} ${historyOpen ? styles.historySidebarOpen : ''}`}>
        <div className={styles.historyHeader}>
          <span className={styles.historyTitle}>{t('workspace.historyTitle')}</span>
          <button className={styles.historyCloseBtn} onClick={() => setHistoryOpen(false)} title={t('workspace.close')}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className={styles.historyBody}>
          {historyGroups.length === 0 ? (
            <p className={styles.historyEmpty}>{t('workspace.historyEmpty')}</p>
          ) : (
            historyGroups.map((group) => (
              <div key={group.label} className={styles.historyGroup}>
                <p className={styles.historyGroupLabel}>{group.label}</p>
                {group.items.map((item) => (
                  <div
                    key={item.sessionId}
                    className={`${styles.historyItemRow} ${item.sessionId === sessionId ? styles.historyItemRowActive : ''}`}
                  >
                    <button
                      type="button"
                      className={styles.historyItemMain}
                      onClick={() => {
                        setHistoryMenuOpenId(null);
                        setHistoryOpen(false);
                        if (item.sessionId !== sessionId) {
                          router.replace(`/workspace/${item.sessionId}`);
                        }
                      }}
                    >
                      <span className={styles.historyItemTitle}>{item.title}</span>
                      <span className={styles.historyItemTime}>
                        {new Date(item.createdAt).toLocaleDateString(
                          resolvedLocale === 'en' ? 'en-US' : 'zh-CN',
                          { month: 'numeric', day: 'numeric' },
                        )}
                      </span>
                    </button>
                    <div className={styles.historyMenuRoot} data-history-menu-root>
                      <button
                        type="button"
                        className={`${styles.historyItemMore} ${historyMenuOpenId === item.sessionId ? styles.historyItemMoreOpen : ''}`}
                        aria-expanded={historyMenuOpenId === item.sessionId}
                        aria-haspopup="menu"
                        title={t('workspace.history.more')}
                        onClick={(e) => {
                          e.stopPropagation();
                          setHistoryMenuOpenId((id) => (id === item.sessionId ? null : item.sessionId));
                        }}
                      >
                        <span className={styles.historyItemMoreDots} aria-hidden>⋯</span>
                      </button>
                      {historyMenuOpenId === item.sessionId && (
                        <ul className={styles.historyDropdown} role="menu">
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={styles.historyDropdownItem}
                              onClick={() => handleHistoryRename(item)}
                            >
                              <svg className={styles.historyDropdownIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
                              </svg>
                              {t('workspace.history.rename')}
                            </button>
                          </li>
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={styles.historyDropdownItem}
                              onClick={() => handleHistoryPin(item)}
                            >
                              <svg className={styles.historyDropdownIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                <g transform="rotate(-45 12 12)">
                                  <path d="M12 17v5" />
                                  <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
                                </g>
                              </svg>
                              {t('workspace.history.pin')}
                            </button>
                          </li>
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={styles.historyDropdownItem}
                              onClick={() => void handleHistoryShare(item)}
                            >
                              <svg className={styles.historyDropdownIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                                <circle cx="18" cy="5" r="3" />
                                <circle cx="6" cy="12" r="3" />
                                <circle cx="18" cy="19" r="3" />
                                <path d="M8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98" />
                              </svg>
                              {t('workspace.history.share')}
                            </button>
                          </li>
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={`${styles.historyDropdownItem} ${styles.historyDropdownItemDanger}`}
                              onClick={() => handleHistoryDelete(item)}
                            >
                              <svg className={styles.historyDropdownIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M10 11v6M14 11v6" />
                              </svg>
                              {t('workspace.history.delete')}
                            </button>
                          </li>
                        </ul>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* 顶部导航栏：历史入口在 Logo 右侧 */}
      <header className={styles.topBar}>
        <div className={styles.topBarBrand}>
          <Link href="/" className="site-nav-logo">
            <span>⚡</span>
            <span>Brandclaw AI</span>
          </Link>
          <button
            type="button"
            className={`${styles.topBarHistoryBtn} ${styles.historyToggleBtn} ${historyOpen ? styles.historyToggleBtnActive : ''}`}
            onClick={() => setHistoryOpen((v) => !v)}
            title={t('workspace.historyToggle')}
            aria-expanded={historyOpen}
            aria-label={t('workspace.historyToggle')}
          >
            <svg width="13" height="11" viewBox="0 0 16 14" fill="none" aria-hidden>
              <rect x="0" y="0" width="16" height="2" rx="1" fill="currentColor"/>
              <rect x="0" y="6" width="11" height="2" rx="1" fill="currentColor"/>
              <rect x="0" y="12" width="7" height="2" rx="1" fill="currentColor"/>
            </svg>
          </button>
          <button
            type="button"
            className={`${styles.topBarHistoryBtn} ${styles.historyToggleBtn}`}
            onClick={handleNewConversation}
            title={t('workspace.newChat')}
            aria-label={t('workspace.newChat')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v8M8 12h8" />
            </svg>
          </button>
        </div>
        <div className={styles.statusBadge}>
          {isComplete ? (
            <><span className={styles.dotDone} /> {t('workspace.status.done')}</>
          ) : error ? (
            <><span className={styles.dotRed} /> {t('workspace.status.error')}</>
          ) : showHeroInput ? (
            <><span className={styles.dotIdle} /> {t('workspace.status.idle')}</>
          ) : (
            <><span className={styles.dotPulse} /> {t('workspace.status.running')}</>
          )}
        </div>

      </header>

      {/* 主内容：空白态居中 Hero（同首页）；有内容时 Feed + 底栏 */}
      <main className={`${styles.main} ${showHeroInput ? styles.mainHeroShell : ''}`}>
        {showHeroInput ? (
          <div className={landingStyles.hero}>
            <h1 className={landingStyles.headline}>
              {t('hero.line1')}<br />
              <span className={landingStyles.headlineGold}>{t('hero.line2')}</span>
            </h1>
            <div className={landingStyles.inputWrapper}>
              <div className={landingStyles.textareaWrap}>
                {!bottomPrompt && !heroFocused && (
                  <div
                    className={landingStyles.ledOverlay}
                    onClick={() => textareaRef.current?.focus()}
                  >
                    <span className={landingStyles.ledText}>{t('workspace.bottom.placeholder')}</span>
                  </div>
                )}
                <textarea
                  ref={textareaRef}
                  className={landingStyles.textarea}
                  placeholder={heroFocused ? t('workspace.bottom.placeholder') : ''}
                  value={bottomPrompt}
                  onChange={(e) => setBottomPrompt(e.target.value)}
                  onFocus={() => setHeroFocused(true)}
                  onBlur={() => setHeroFocused(false)}
                  rows={1}
                  maxLength={20000}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSubmit();
                    }
                  }}
                />
              </div>
              <div className={landingStyles.inputFooter}>
                <button
                  type="button"
                  className={`icon-btn-circle ${landingStyles.submitBtn}`}
                  onClick={() => void handleSubmit()}
                  disabled={!bottomPrompt.trim() || submitting || !user}
                  title={t('workspace.send.title')}
                >
                  {submitting ? (
                    <span className={landingStyles.spinner} />
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path d="M10 15V5M10 5L5 10M10 5L15 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
        <>
        <div className={styles.feed}>

          {/* ── 历史轮次：直接展开，每轮顶部显示用户气泡 ── */}
          {previousRounds.map((round, roundIndex) => {
            const roundConfigs = round.selectedAgents
              ? AGENT_CONFIGS.filter(c => round.selectedAgents!.includes(c.id))
              : AGENT_CONFIGS;
            const visibleRoundAgents = roundConfigs.filter(cfg => {
              const s = round.agents[cfg.id as AgentId];
              return s && s.status !== 'waiting';
            });

            return (
              <div key={round.sessionId} className={styles.roundSection}>
                {/* 轮次标记线（无折叠，纯视觉分隔） */}
                {roundIndex > 0 && <div className={styles.roundSeparator}><div className={styles.roundDividerLine} /></div>}

                {/* 用户输入气泡 — 右侧对齐；锚点用于右侧导航 */}
                <div id={`workspace-round-${round.sessionId}`} className={styles.userRoundAnchor}>
                  <div className={styles.userMsgRow}>
                    <div className={styles.userBubble}>{round.userPrompt}</div>
                    <div className={styles.userAvatarWrap}>
                      {avatarDataUrl
                        ? <img src={avatarDataUrl} alt="avatar" className={styles.userAvatarImg} />
                        : <svg className={styles.userAvatarFallback} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                      }
                    </div>
                  </div>
                </div>

                {/* Agent 卡片 */}
                <div className={styles.roundContent}>
                  {visibleRoundAgents.map((cfg, i) => {
                    const state = round.agents[cfg.id as AgentId];
                    const output = state?.output ?? '';
                    const isDone = state?.status === 'completed';
                    const hasNext = i < visibleRoundAgents.length - 1;
                    return (
                      <div key={cfg.id}>
                        <div className={styles.feedItem}>
                          <div className={styles.feedLeft}>
                            <div className={styles.feedAvatar} style={{ '--agent-color': cfg.color } as React.CSSProperties}>
                              <img src={cfg.avatar} alt={cfg.charName} />
                              {isDone && (
                                <span className={styles.feedDoneCheck}>
                                  <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                                    <path d="M1 3L3 5L7 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                                  </svg>
                                </span>
                              )}
                            </div>
                            <div className={styles.feedAgentInfo}>
                              <span className={styles.feedAgentName}>{t(`agent.${cfg.id}.name`)}</span>
                              <span className={styles.feedAgentChar}>{cfg.charName}</span>
                            </div>
                            {hasNext && <div className={`${styles.feedLeftLine} ${styles.connectorDone}`} />}
                          </div>
                          <div className={styles.feedBubbleWrap}>
                            <div className={styles.feedBubble} style={{ '--agent-color': cfg.color } as React.CSSProperties}>
                              <div className={`${styles.cardOutput} markdown-body`}>
                                {output
                                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
                                  : <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>—</span>
                                }
                              </div>
                            </div>
                          </div>
                        </div>
                        {hasNext && (
                          <div className={styles.feedConnector}>
                            <div className={styles.connectorTrack}>
                              <div className={`${styles.connectorLine} ${styles.connectorDone}`} />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* 当前轮次内容 + ref 用于自动滚动 */}
          <div ref={currentRoundRef}>

          {/* 当前轮次用户气泡（有 userPrompt 时显示）*/}
          {userPrompt && (
            <div id="workspace-round-active" className={styles.userRoundAnchor}>
              <div className={styles.userMsgRow}>
                <div className={styles.userBubble}>{userPrompt}</div>
                <div className={styles.userAvatarWrap}>
                  {avatarDataUrl
                    ? <img src={avatarDataUrl} alt="avatar" className={styles.userAvatarImg} />
                    : <svg className={styles.userAvatarFallback} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  }
                </div>
              </div>
            </div>
          )}

          {/* 空状态 / 连接中 */}
          {isStreaming && !currentAgentId && (
            <div className={styles.loadingState}>
              <div className={styles.globalSpinner} />
              <p>{t('workspace.connecting')}</p>
            </div>
          )}


          {visibleConfigs.map((cfg, i) => {
            const state = agents[cfg.id as AgentId];
            const output = state?.output ?? '';
            const status = state?.status ?? 'waiting';
            const isRunning = status === 'running';
            const isDone = status === 'completed';
            const isCurrent = cfg.id === currentAgentId;
            const hasNext = i < visibleConfigs.length - 1;
            const nextCfg = visibleConfigs[i + 1];
            const isTransferring = isDone && nextCfg?.id === currentAgentId;

            if (status === 'waiting') return null;

            const nextState = nextCfg ? agents[nextCfg.id as AgentId] : null;
            const nextVisible = nextState && nextState.status !== 'waiting';

            const hasConnector = hasNext && nextVisible;
            const lineClass = [
              styles.feedLeftLine,
              isTransferring ? styles.connectorActive : '',
              isDone && !isTransferring ? styles.connectorDone : '',
            ].join(' ');

            const connector = hasConnector ? (
              <div className={styles.feedConnector}>
                {/* 桥接两个 feedItem 之间小间距的短线 */}
                <div className={styles.connectorTrack}>
                  <div className={`${styles.connectorLine} ${isTransferring ? styles.connectorActive : ''} ${isDone && !isTransferring ? styles.connectorDone : ''}`} />
                </div>
                {handoffMsg?.agentId === cfg.id && (
                  <div className={styles.handoffBubble}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M6 1v7M6 8l-3-3M6 8l3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {handoffMsg.text}
                  </div>
                )}
              </div>
            ) : null;

            return (
              <div key={cfg.id}>
              <div className={styles.feedItem}>
                {/* 左侧：头像 + 名称 + 向下延伸的连接竖线 */}
                <div className={styles.feedLeft}>
                  <div
                    className={`${styles.feedAvatar} ${isCurrent ? styles.feedAvatarActive : ''}`}
                    style={{ '--agent-color': cfg.color } as React.CSSProperties}
                  >
                    <img src={cfg.avatar} alt={cfg.charName} />
                    {isCurrent && <span className={styles.feedSpinner} />}
                    {isDone && (
                      <span className={styles.feedDoneCheck}>
                        <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                          <path d="M1 3L3 5L7 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </span>
                    )}
                  </div>
                  <div className={styles.feedAgentInfo}>
                    <span className={styles.feedAgentName}>{t(`agent.${cfg.id}.name`)}</span>
                    <span className={styles.feedAgentChar}>{cfg.charName}</span>
                  </div>
                  {/* 随气泡高度拉伸的竖线，连接到下方 feedConnector */}
                  {hasConnector && (
                    <div className={lineClass}>
                      {isTransferring && <span className={styles.connectorParticle} />}
                    </div>
                  )}
                </div>

                {/* 右侧：气泡 */}
                <div className={styles.feedBubbleWrap}>
                  {(isRunning || isDone) && (
                    <div className={styles.feedBubbleStatus}>
                      {isRunning && (
                        <div className={styles.feedRunning}>
                          <span className={styles.runningDot} style={{ background: cfg.color }} />
                          {t('workspace.analyzing')}
                        </div>
                      )}
                      {isDone && (
                        <div className={styles.feedDone} style={{ color: cfg.color }}>{t('workspace.done')}</div>
                      )}
                    </div>
                  )}
                  <div
                    className={`${styles.feedBubble} ${isRunning ? styles.feedBubbleActive : ''}`}
                    style={{ '--agent-color': cfg.color } as React.CSSProperties}
                  >
                    <div className={`${styles.cardOutput} markdown-body`}>
                      {output ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
                      ) : (
                        <div className={styles.thinking}>
                          <span className={styles.thinkingDot} />
                          <span className={styles.thinkingDot} />
                          <span className={styles.thinkingDot} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              {connector}
              </div>
            );
          })}

          {/* 错误提示 */}
          {error && (
            <div className={styles.errorCard}>
              <p>⚠️ {translateWorkspaceError(error, t)}</p>
              <a href="/" className="btn-ghost">{t('workspace.retry')}</a>
            </div>
          )}
          </div>{/* /currentRoundRef */}
        </div>

        {/* 底部输入框 */}
        <div className={styles.bottomBar}>
          <div className={styles.bottomInner}>
          <div className={styles.bottomSpacer} />
          <div className={styles.bottomInputWrap}>
            <textarea
              ref={textareaRef}
              className={styles.bottomTextarea}
              placeholder={t('workspace.bottom.placeholder')}
              value={bottomPrompt}
              onChange={(e) => setBottomPrompt(e.target.value)}
              rows={1}
              maxLength={20000}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
              }}
            />
            <div className={styles.bottomActions}>
              {isStreaming && (
                <button className={styles.cancelBtn} onClick={cancel} title={t('workspace.cancel.title')}>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="3" y="3" width="8" height="8" rx="1.5" fill="currentColor"/>
                  </svg>
                  {t('workspace.cancel')}
                </button>
              )}
              <button
                className={`icon-btn-circle ${styles.bottomSendBtn} ${isStreaming || submitting ? styles.bottomSendBtnActive : ''}`}
                onClick={handleSubmit}
                disabled={!bottomPrompt.trim() || submitting}
                title={t('workspace.send.title')}
              >
                {submitting ? (
                  <span className={styles.bottomSpinner} />
                ) : isStreaming ? (
                  <span className={styles.streamingDots}><span /><span /><span /></span>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M8 12V4M8 4L4 8M8 4L12 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </button>
            </div>
          </div>
          </div>
        </div>
        </>
        )}
      </main>

      {/* 右侧短划 + 展开白底列表；鼠标进入展开；点击导航以外区域收起 */}
      {outlineItems.length > 0 && (
        <nav
          ref={outlineDockRef}
          className={styles.outlineDock}
          aria-label={t('workspace.outlineNav')}
          onMouseEnter={() => setOutlinePanelOpen(true)}
        >
          <div className={styles.outlineMinimap}>
            {outlineItems.map((item, i) => (
              <button
                key={item.id}
                type="button"
                className={styles.outlineDash}
                data-active={activeOutlineIndex === i ? 'true' : undefined}
                onClick={() => jumpToRound(item.id)}
                title={item.prompt}
                aria-label={`${t('workspace.outlineJump')}: ${truncatePromptOneLine(item.prompt, 120)}`}
              />
            ))}
          </div>
          <div
            className={`${styles.outlinePanelScroll} ${outlinePanelOpen ? styles.outlinePanelScrollOpen : ''}`}
          >
            {outlineItems.map((item, i) => (
              <button
                key={item.id}
                type="button"
                className={styles.outlineRow}
                data-active={activeOutlineIndex === i ? 'true' : undefined}
                onClick={() => jumpToRound(item.id)}
                title={item.prompt}
                aria-current={activeOutlineIndex === i ? 'location' : undefined}
              >
                <span className={styles.outlineRowText}>{truncatePromptOneLine(item.prompt, 44)}</span>
                <span className={styles.outlineRowMark} data-active={activeOutlineIndex === i ? 'true' : undefined} aria-hidden />
              </button>
            ))}
          </div>
        </nav>
      )}

      {historyToast ? <div className={styles.historyToast} role="status">{historyToast}</div> : null}
    </div>
  );
}

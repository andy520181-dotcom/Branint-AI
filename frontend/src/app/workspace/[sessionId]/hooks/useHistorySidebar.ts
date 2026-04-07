'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import type { HistoryItem } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { fetchSessions, updateSessionMeta, deleteSession } from '@/lib/api';
import { groupByDate } from '../workspaceUtils';

type TFn = (key: string) => string;

export interface UseHistorySidebarOptions {
  sessionId: string;
  t: TFn;
}

export interface UseHistorySidebarReturn {
  historyOpen: boolean;
  setHistoryOpen: (v: boolean) => void;
  historyGroups: { label: string; items: HistoryItem[] }[];
  /** 是否正在拉取历史列表（未完成前不显示"暂无记录"） */
  historyLoading: boolean;
  historyMenuOpenId: string | null;
  setHistoryMenuOpenId: (id: string | null) => void;
  historyToast: string;
  handleHistoryRename: (item: HistoryItem) => void;
  handleHistoryPin: (item: HistoryItem) => void;
  handleHistoryShare: (item: HistoryItem) => Promise<void>;
  handleHistoryDelete: (item: HistoryItem) => void;
}

/**
 * 封装历史记录侧边栏的所有状态与操作
 * 包括：open/close、菜单弹出、toast、rename/pin/share/delete
 *
 * NOTE: 修复了两个竞态条件：
 * 1. 加载期间闪现"暂无会话记录"→ 新增 historyLoading 状态
 * 2. 首次打开时 user?.id 尚未就绪，refreshHistory 直接 return
 *    → 新增 useEffect 监听 user?.id，侧边栏已开时自动重试
 */
export function useHistorySidebar({ sessionId, t }: UseHistorySidebarOptions): UseHistorySidebarReturn {
  const router = useRouter();
  const { user } = useAuth();

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyGroups, setHistoryGroups] = useState<{ label: string; items: HistoryItem[] }[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMenuOpenId, setHistoryMenuOpenId] = useState<string | null>(null);
  const [historyToast, setHistoryToast] = useState('');

  // 记录是否已经完成过初始加载（无论是非阻塞预取还是阻塞拉取）
  const initialLoadDone = useRef(false);

  // NOTE: 用 ref 追踪 historyOpen，便于在 user?.id 变化的 effect 中读取最新值，
  //       避免闭包捕获旧值导致条件判断错误
  const historyOpenRef = useRef(historyOpen);
  useEffect(() => {
    historyOpenRef.current = historyOpen;
  }, [historyOpen]);

  // ── 核心策略：「预取」而非「懒加载」────────────────────────────────
  //
  // DeepSeek / ChatGPT 等产品侧边栏「秒现」的秘密：
  // 不等用户点击再拉数据，而是在组件 mount 时就后台静默预取。
  // 用户点击侧边栏时，数据已经在内存里 → 直接渲染，零延迟感知。
  //
  // 侧边栏开启时仍会发一次静默刷新以保持最新，但不阻塞渲染

  const refreshHistory = useCallback(async () => {
    if (!user?.id) return;
    
    // 如果还没完成过第一次加载，打开侧边栏时显示骨架屏
    const shouldShowSkeleton = !initialLoadDone.current;
    if (shouldShowSkeleton) {
      setHistoryLoading(true);
    }

    try {
      const dbSessions = await fetchSessions(user.id);
      // 将后端数据映射为 HistoryItem
      const mappedItems: HistoryItem[] = dbSessions.map((s) => ({
        sessionId: s.session_id,
        title: s.title,
        createdAt: s.created_at,
        isPinned: s.is_pinned,
        shareUrl: `/workspace/${s.session_id}`,
      }));
      setHistoryGroups(groupByDate(mappedItems, t));
      initialLoadDone.current = true;
    } catch (err) {
      console.error('Failed to refresh history:', err);
    } finally {
      if (shouldShowSkeleton) {
        setHistoryLoading(false);
      }
    }
  }, [user?.id, t]);

  /** 页面 mount 且 user 就绪后立即后台预取（不计入 loading 状态） */
  const prefetchHistory = useCallback(async () => {
    // 如果已经拉取过了不需要再预取
    if (!user?.id || initialLoadDone.current) return;
    try {
      const dbSessions = await fetchSessions(user.id);
      const mappedItems: HistoryItem[] = dbSessions.map((s) => ({
        sessionId: s.session_id,
        title: s.title,
        createdAt: s.created_at,
        isPinned: s.is_pinned,
        shareUrl: `/workspace/${s.session_id}`,
      }));
      setHistoryGroups(groupByDate(mappedItems, t));
      initialLoadDone.current = true;
    } catch (err) {
      console.error('Failed to prefetch history:', err);
    }
  }, [user?.id, t]);

  const showHistoryToast = useCallback((msg: string) => {
    setHistoryToast(msg);
    setTimeout(() => setHistoryToast(''), 2200);
  }, []);

  // 预取：user?.id 就绪后立即后台拉取，无论侧边栏是否打开
  useEffect(() => {
    if (user?.id) {
      prefetchHistory();
    }
  }, [user?.id, prefetchHistory]);

  // 侧边栏开关时的 effect：
  // - 打开：触发静默刷新（复用 refreshHistory，此时数据大概率已在内存）
  // - 关闭：收起菜单
  useEffect(() => {
    if (historyOpen) refreshHistory();
    else setHistoryMenuOpenId(null);
  }, [historyOpen, refreshHistory]);

  // NOTE: user?.id 就绪时若侧边栏已打开，补发一次刷新（竞态保底）
  useEffect(() => {
    if (user?.id && historyOpenRef.current) {
      refreshHistory();
    }
  }, [user?.id, refreshHistory]);

  // 点击空白区域收起右键菜单
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
    async (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      const next = window.prompt(t('workspace.history.renamePrompt'), item.title);
      if (next === null) return;
      const trimmed = next.trim();
      if (!trimmed) return;
      
      try {
        await updateSessionMeta(item.sessionId, { title: trimmed });
        await refreshHistory();
      } catch (err) {
        showHistoryToast(t('workspace.history.renameFailed') || 'Rename failed');
      }
    },
    [t, refreshHistory, showHistoryToast],
  );

  const handleHistoryPin = useCallback(
    async (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      try {
        // Toggle the pin status
        await updateSessionMeta(item.sessionId, { is_pinned: !item.isPinned });
        await refreshHistory();
      } catch (err) {
        showHistoryToast('Failed to change pin status');
      }
    },
    [refreshHistory, showHistoryToast],
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
    async (item: HistoryItem) => {
      if (!window.confirm(t('workspace.history.deleteConfirm'))) return;
      setHistoryMenuOpenId(null);
      try {
        await deleteSession(item.sessionId);
        await refreshHistory();
        
        if (item.sessionId === sessionId) {
          // 如果删除了当前会话，拉取最新剩余记录跳到第一个
          if (user?.id) {
             const rest = await fetchSessions(user.id);
             if (rest.length > 0) router.replace(`/workspace/${rest[0].session_id}`);
             else router.replace('/');
          }
        }
      } catch (err) {
        showHistoryToast('Failed to delete session');
      }
    },
    [t, refreshHistory, sessionId, router, user?.id, showHistoryToast],
  );

  return {
    historyOpen,
    setHistoryOpen,
    historyGroups,
    historyLoading,
    historyMenuOpenId,
    setHistoryMenuOpenId,
    historyToast,
    handleHistoryRename,
    handleHistoryPin,
    handleHistoryShare,
    handleHistoryDelete,
  };
}

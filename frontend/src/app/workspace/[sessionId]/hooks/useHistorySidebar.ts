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
 */
export function useHistorySidebar({ sessionId, t }: UseHistorySidebarOptions): UseHistorySidebarReturn {
  const router = useRouter();
  const { user } = useAuth();

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyGroups, setHistoryGroups] = useState<{ label: string; items: HistoryItem[] }[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMenuOpenId, setHistoryMenuOpenId] = useState<string | null>(null);
  const [historyToast, setHistoryToast] = useState('');

  // NOTE: 用 ref 追踪是否已有缓存数据，避免将 historyGroups.length 列入 useCallback 依赖
  const hasCacheRef = useRef(false);
  // NOTE: 共享同一个 in-flight 请求 Promise，避免重复发起网络请求
  const fetchingPromiseRef = useRef<Promise<void> | null>(null);

  // 初始化：mount 后立即从 localStorage 读取上次缓存，让侧边栏「秒显」
  useEffect(() => {
    if (typeof window === 'undefined' || !user?.id) return;
    const cached = localStorage.getItem(`history_cache_${user.id}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as { label: string; items: HistoryItem[] }[];
        setHistoryGroups(parsed);
        hasCacheRef.current = true;
      } catch (e) {
        console.error('Failed to parse history cache', e);
      }
    }
    // 读完缓存后立即后台更新，不显示骨架屏
    fetchingPromiseRef.current = null;
  }, [user?.id]);

  const refreshHistory = useCallback(async (force = false) => {
    if (!user?.id) return;

    // NOTE: force=true（rename/delete 后需要最新数据）时清除旧 Promise，强制重新请求
    if (force) {
      fetchingPromiseRef.current = null;
    }

    // 如果已有请求在进行中，直接复用该 Promise，避免重复调用
    if (fetchingPromiseRef.current) return fetchingPromiseRef.current;

    const fetchTask = (async () => {
      try {
        // NOTE: 无缓存时才显示骨架屏，有缓存时在后台静默更新
        if (!hasCacheRef.current) setHistoryLoading(true);

        const dbSessions = await fetchSessions(user.id!);
        const mappedItems: HistoryItem[] = dbSessions.map((s) => ({
          sessionId: s.session_id,
          title: s.title,
          createdAt: s.created_at,
          isPinned: s.is_pinned,
          shareUrl: `/workspace/${s.session_id}`,
        }));

        const grouped = groupByDate(mappedItems, t);
        setHistoryGroups(grouped);
        hasCacheRef.current = true;
        // 更新本地缓存，供下次打开时秒显
        localStorage.setItem(`history_cache_${user.id}`, JSON.stringify(grouped));
      } catch (err) {
        console.error('Failed to refresh history:', err);
      } finally {
        setHistoryLoading(false);
        fetchingPromiseRef.current = null;
      }
    })();

    fetchingPromiseRef.current = fetchTask;
    return fetchTask;
  }, [user?.id, t]);

  const showHistoryToast = useCallback((msg: string) => {
    setHistoryToast(msg);
    setTimeout(() => setHistoryToast(''), 2200);
  }, []);

  // 侧边栏开启时自动刷新
  useEffect(() => {
    if (historyOpen) {
      refreshHistory();
    } else {
      setHistoryMenuOpenId(null);
    }
  }, [historyOpen, refreshHistory]);

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
        await refreshHistory(true);
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
        await updateSessionMeta(item.sessionId, { is_pinned: !item.isPinned });
        await refreshHistory(true);
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
        await refreshHistory(true);
        
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

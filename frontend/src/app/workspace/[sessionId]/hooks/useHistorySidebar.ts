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

  // NOTE: 用 ref 追踪 historyOpen，便于在 user?.id 变化的 effect 中读取最新值，
  //       避免闭包捕获旧值导致条件判断错误
  const historyOpenRef = useRef(historyOpen);
  useEffect(() => {
    historyOpenRef.current = historyOpen;
  }, [historyOpen]);

  const refreshHistory = useCallback(async () => {
    if (!user?.id) return;
    setHistoryLoading(true);
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
    } catch (err) {
      console.error('Failed to refresh history:', err);
    } finally {
      setHistoryLoading(false);
    }
  }, [user?.id, t]);

  const showHistoryToast = useCallback((msg: string) => {
    setHistoryToast(msg);
    setTimeout(() => setHistoryToast(''), 2200);
  }, []);

  // 侧边栏开关时的主 effect
  useEffect(() => {
    if (historyOpen) refreshHistory();
    else setHistoryMenuOpenId(null);
  }, [historyOpen, refreshHistory]);

  // NOTE: 修复竞态 Bug2：
  // 当用户在 user?.id 尚未就绪时就打开了侧边栏，refreshHistory 会因为 !user?.id 直接 return。
  // 此 effect 监听 user?.id 变化，一旦 id 到位且侧边栏处于打开状态，立即补发请求。
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

'use client';

import { useAuthContext } from '@/contexts/AuthContext';

/**
 * 统一从 AuthContext 获取当前用户头像 URL。
 * 头像更新后 AuthContext 监听 woloong-profile-updated 事件并重新拉取 /api/auth/me，
 * user.avatar_url 变化后此 Hook 自动返回最新值，触发订阅组件重渲染。
 */
export function useUserAvatar(userId: string | undefined | null): string | null {
  const { user } = useAuthContext();
  if (!userId || !user || userId !== user.id) return null;
  return user.avatar_url ?? null;
}


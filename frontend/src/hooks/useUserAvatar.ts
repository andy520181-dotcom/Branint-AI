'use client';

import { useAuthContext } from '@/contexts/AuthContext';
import { useEffect, useState } from 'react';

/** 统一从 AuthContext 中获取用户真身头像（已迁移至 OSS URL），抛弃老旧的 localStorage 持久化 */
export function useUserAvatar(userId: string | undefined | null) {
  const { user } = useAuthContext();
  
  // NOTE: 这里做一层解耦防御，如果是查询当前用户，直接走 Context 流式反应，
  // 若是查询其余用户头像（例如未来的社交功能），可在此处扩展独立 API 调用
  const [dataUrl, setDataUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!userId || !user) {
      setDataUrl(null);
      return;
    }
    
    // 查询自己
    if (userId === user.id) {
      setDataUrl(user.avatar_url || null);
    }
    
    // 全局通知事件监听（强制从 Context 内联刷新）
    const updateHandler = () => {
      // 通过 AuthContext 强更
    };
    window.addEventListener('woloong-profile-updated', updateHandler);
    return () => window.removeEventListener('woloong-profile-updated', updateHandler);
  }, [userId, user]);

  return dataUrl;
}

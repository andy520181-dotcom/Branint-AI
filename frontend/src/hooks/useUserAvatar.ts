'use client';

import { useEffect, useState } from 'react';
import { getAvatarStorageKey, getStoredAvatarDataUrl, PROFILE_UPDATE_EVENT } from '@/lib/userProfile';

/** 本地缓存的头像 data URL，随 PROFILE_UPDATE_EVENT 与其它组件同步 */
export function useUserAvatar(userId: string | undefined | null) {
  // NOTE: 惰性初始化同步读取 localStorage，避免首帧 null → 下一帧 dataUrl 的闪跳
  const [dataUrl, setDataUrl] = useState<string | null>(
    () => (userId ? getStoredAvatarDataUrl(userId) : null),
  );

  useEffect(() => {
    if (!userId) {
      setDataUrl(null);
      return;
    }
    const sync = () => setDataUrl(getStoredAvatarDataUrl(userId));
    sync();
    window.addEventListener(PROFILE_UPDATE_EVENT, sync);
    const onStorage = (e: StorageEvent) => {
      if (e.key === getAvatarStorageKey(userId)) sync();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(PROFILE_UPDATE_EVENT, sync);
      window.removeEventListener('storage', onStorage);
    };
  }, [userId]);

  return dataUrl;
}

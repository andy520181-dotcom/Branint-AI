'use client';

import { useEffect, useState } from 'react';
import { getAvatarStorageKey, getStoredAvatarDataUrl, PROFILE_UPDATE_EVENT } from '@/lib/userProfile';

/** 本地缓存的头像 data URL，随 PROFILE_UPDATE_EVENT 与其它组件同步 */
export function useUserAvatar(userId: string | undefined | null) {
  const [dataUrl, setDataUrl] = useState<string | null>(null);

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

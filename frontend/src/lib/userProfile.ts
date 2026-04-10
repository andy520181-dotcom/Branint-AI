/** 本地持久化用户展示名（按用户 id，与后端账号解耦） */
const key = (userId: string) => `woloong_display_name_${userId}`;
const avatarKey = (userId: string) => `woloong_avatar_${userId}`;

export function getAvatarStorageKey(userId: string): string {
  return avatarKey(userId);
}

/** 同标签页内头像等资料更新后广播，供 UserMenu 等刷新 */
export const PROFILE_UPDATE_EVENT = 'woloong-profile-updated';

export function dispatchProfileUpdated(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(PROFILE_UPDATE_EVENT));
}

export function getStoredAvatarDataUrl(userId: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const v = localStorage.getItem(avatarKey(userId));
    return v && v.startsWith('data:image/') ? v : null;
  } catch {
    return null;
  }
}

export function setStoredAvatarDataUrl(userId: string, dataUrl: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (dataUrl == null || dataUrl === '') {
      localStorage.removeItem(avatarKey(userId));
    } else {
      localStorage.setItem(avatarKey(userId), dataUrl);
    }
    dispatchProfileUpdated();
  } catch {
    /* quota */
  }
}

export function getStoredDisplayName(userId: string): string {
  if (typeof window === 'undefined') return '';
  try {
    return localStorage.getItem(key(userId)) ?? '';
  } catch {
    return '';
  }
}

export function setStoredDisplayName(userId: string, value: string): void {
  if (typeof window === 'undefined') return;
  try {
    const v = value.trim();
    if (v === '') localStorage.removeItem(key(userId));
    else localStorage.setItem(key(userId), v);
    dispatchProfileUpdated();
  } catch { /* ignore quota */ }
}

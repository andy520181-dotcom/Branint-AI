'use client';

// 统一从全局 AuthContext 取值，避免各页面重复读 localStorage
export { useAuthContext as useAuth } from '@/contexts/AuthContext';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('woloong_token');
}

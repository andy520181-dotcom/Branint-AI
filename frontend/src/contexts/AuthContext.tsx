'use client';

import { createContext, useContext, useState, useEffect, useLayoutEffect, useCallback, ReactNode } from 'react';
import { API_BASE as API_URL } from '@/lib/api';
const TOKEN_KEY = 'woloong_token';
const USER_KEY  = 'woloong_user';

interface UserInfo { id: string; email: string; }

interface AuthContextValue {
  user: UserInfo | null;
  loading: boolean;
  sendOtp: (email: string) => Promise<void>;
  register: (email: string, otp: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveUser(userInfo: UserInfo, token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(userInfo));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 首屏在浏览器绘制前从 localStorage 恢复登录态，减少顶栏「登录↔头像」闪一下
  // NOTE: MVP 阶段 token 失效时仍可能显示头像，需用户重新登录
  useLayoutEffect(() => {
    setUser(loadUser());
    setLoading(false);
  }, []);

  // 多 Tab 同步
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === USER_KEY)
        setUser(e.newValue ? JSON.parse(e.newValue) : null);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const sendOtp = useCallback(async (email: string) => {
    const res = await fetch(`${API_URL}/api/auth/send-otp`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? '发送失败'); }
  }, []);

  const register = useCallback(async (email: string, otp: string, password: string) => {
    const res = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp, password }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? '注册失败'); }
    const data = await res.json();
    const info: UserInfo = { id: data.user_id, email: data.email };
    saveUser(info, data.access_token);
    setUser(info);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? '邮箱或密码错误'); }
    const data = await res.json();
    const info: UserInfo = { id: data.user_id, email: data.email };
    saveUser(info, data.access_token);
    setUser(info);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, sendOtp, register, login, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}

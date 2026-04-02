'use client';

import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import UserMenu from '@/components/UserMenu';

type SiteNavAuthProps = {
  onLoginClick: () => void;
  /** 例如首页用于 E2E 的 #nav-login-btn */
  loginButtonId?: string;
};

/**
 * 顶栏右侧：登录态恢复前显示骨架，避免整页刷新时先出现「登录」再变成头像。
 * AuthProvider 在 useLayoutEffect 中同步读取 localStorage，loading 仅覆盖首帧。
 */
export function SiteNavAuth({ onLoginClick, loginButtonId }: SiteNavAuthProps) {
  const { user, loading } = useAuth();
  const { t } = useLocale();

  if (loading) {
    return (
      <span
        className="site-nav-auth-skeleton"
        aria-busy="true"
        aria-label={t('nav.authLoading')}
      />
    );
  }

  if (user) {
    return <UserMenu userId={user.id} email={user.email} />;
  }

  return (
    <button
      type="button"
      className="btn-ghost"
      onClick={onLoginClick}
      id={loginButtonId}
    >
      {t('nav.login')}
    </button>
  );
}

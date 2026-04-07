'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import {
  type ThemePreference,
  applyThemePreference,
  getStoredThemePreference,
} from '@/lib/theme';
import type { LocalePreference } from '@/lib/locale';
import { useLocale } from '@/hooks/useLocale';
import { useAuth } from '@/hooks/useAuth';
import { maskEmail } from '@/lib/maskContact';
import { getStoredDisplayName, setStoredAvatarDataUrl, setStoredDisplayName } from '@/lib/userProfile';
import { processAvatarFile } from '@/lib/avatarImage';
import { useUserAvatar } from '@/hooks/useUserAvatar';
import { API_BASE } from '@/lib/api';
import AvatarPlaceholderIcon from '@/components/AvatarPlaceholderIcon';
import styles from './SettingsModal.module.css';

type Section = 'theme' | 'language' | 'account' | 'legal';

interface SettingsModalProps {
  onClose: () => void;
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
  const { preference, setPreference, t } = useLocale();
  const { user } = useAuth();
  const avatarUrl = useUserAvatar(user?.id);
  const [mounted, setMounted] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const avatarFileRef = useRef<HTMLInputElement>(null);
  const [section, setSection] = useState<Section>('account');
  const [themePref, setThemePref] = useState<ThemePreference>('light');

  useEffect(() => {
    setMounted(true);
    setThemePref(getStoredThemePreference());
  }, []);

  useEffect(() => {
    if (!user) {
      setDisplayName('');
      return;
    }
    setDisplayName(getStoredDisplayName(user.id));
  }, [user]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const setTheme = (pref: ThemePreference) => {
    setThemePref(pref);
    applyThemePreference(pref);
  };

  const setLang = (pref: LocalePreference) => {
    setPreference(pref);
  };

  const onAvatarFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f || !user) return;
    try {
      // 1. 直传文件到 OSS 代理资产库
      const formData = new FormData();
      formData.append('file', f);
      const token = localStorage.getItem('woloong_token');

      const uploadRes = await fetch(`${API_BASE}/api/assets/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!uploadRes.ok) throw new Error('UPLOAD_FAILED');
      const uploadData = await uploadRes.json();
      const ossUrl = uploadData.url;

      // 2. 将 OSS 网址保存到用户账户关联表中
      const updateRes = await fetch(`${API_BASE}/api/auth/profile/avatar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ avatar_url: ossUrl })
      });

      if (!updateRes.ok) throw new Error('UPDATE_FAILED');

      // 3. 强制触发重渲染事件，让所有组件捕获到最新头像
      window.dispatchEvent(new Event('woloong-profile-updated'));
      setAvatarError(null);
    } catch (err) {
      const code = err instanceof Error ? err.message : '';
      if (code === 'TOO_LARGE') setAvatarError(t('settings.account.avatarTooLarge'));
      else if (code === 'INVALID_TYPE') setAvatarError(t('settings.account.avatarInvalidType'));
      else setAvatarError(t('settings.account.avatarFailed'));
    }
  };

  const removeAvatar = async () => {
    if (!user) return;
    try {
      const token = localStorage.getItem('woloong_token');
      await fetch(`${API_BASE}/api/auth/profile/avatar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ avatar_url: '' })
      });
      window.dispatchEvent(new Event('woloong-profile-updated'));
      setAvatarError(null);
    } catch {
      // ignore
    }
  };

  const modal = (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 id="settings-modal-title" className={styles.title}>
            {t('settings.title')}
          </h2>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label={t('settings.close')}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M1 1L15 15M15 1L1 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        <div className={styles.body}>
          <nav className={styles.sidebar} aria-label={t('settings.navAria')}>
            <NavButton
              active={section === 'account'}
              onClick={() => setSection('account')}
              icon={
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              }
              label={t('settings.nav.account')}
            />
            <NavButton
              active={section === 'theme'}
              onClick={() => setSection('theme')}
              icon={
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              }
              label={t('settings.nav.theme')}
            />
            <NavButton
              active={section === 'language'}
              onClick={() => setSection('language')}
              icon={
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M2 12h20" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
              }
              label={t('settings.nav.language')}
            />
            <NavButton
              active={section === 'legal'}
              onClick={() => setSection('legal')}
              icon={
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              }
              label={t('settings.nav.legal')}
            />
          </nav>

          <div className={styles.content}>
            {section === 'theme' && (
              <div className={styles.themeRow}>
                <button
                  type="button"
                  className={`${styles.themeCard} ${themePref === 'light' ? styles.themeCardActive : ''}`}
                  onClick={() => setTheme('light')}
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
                  </svg>
                  {t('settings.theme.light')}
                </button>
                <button
                  type="button"
                  className={`${styles.themeCard} ${themePref === 'dark' ? styles.themeCardActive : ''}`}
                  onClick={() => setTheme('dark')}
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                  </svg>
                  {t('settings.theme.dark')}
                </button>
                <button
                  type="button"
                  className={`${styles.themeCard} ${themePref === 'system' ? styles.themeCardActive : ''}`}
                  onClick={() => setTheme('system')}
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                    <rect x="2" y="3" width="20" height="14" rx="2" />
                    <path d="M8 21h8M12 17v4" />
                  </svg>
                  {t('settings.theme.system')}
                </button>
              </div>
            )}

            {section === 'language' && (
              <div className={styles.langRow} role="group" aria-label={t('settings.nav.language')}>
                {(
                  [
                    { value: 'system' as const, msgKey: 'settings.lang.system' },
                    { value: 'zh-CN' as const, msgKey: 'settings.lang.zh' },
                    { value: 'en' as const, msgKey: 'settings.lang.en' },
                  ] as const
                ).map(({ value, msgKey }) => (
                  <button
                    key={value}
                    type="button"
                    className={`${styles.langPill} ${preference === value ? styles.langPillActive : ''}`}
                    onClick={() => setLang(value)}
                  >
                    {preference === value && (
                      <svg className={styles.langPillCheck} width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
                        <path d="M2.5 7L5.5 10L11.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                    {t(msgKey)}
                  </button>
                ))}
              </div>
            )}

            {section === 'account' && (
              <div className={styles.accountPanel}>
                {!user ? (
                  <p className={styles.placeholder}>{t('settings.account.needLogin')}</p>
                ) : (
                  <>
                    {avatarError && <p className={styles.footnoteError}>{avatarError}</p>}
                    <div className={styles.accountRow}>
                      <span className={styles.accountLabel}>{t('settings.account.avatar')}</span>
                      <div className={styles.accountRowRight}>
                        <input
                          ref={avatarFileRef}
                          type="file"
                          accept="image/jpeg,image/png,image/webp,image/gif"
                          className={styles.avatarFileInput}
                          onChange={onAvatarFile}
                        />
                        <button
                          type="button"
                          className={styles.avatarHit}
                          onClick={() => avatarFileRef.current?.click()}
                          aria-label={t('settings.account.avatarClickHint')}
                        >
                          {avatarUrl ? (
                            <img src={avatarUrl} alt="" className={styles.avatarHitImg} />
                          ) : (
                            <AvatarPlaceholderIcon className={styles.avatarHitSvg} />
                          )}
                        </button>
                        {avatarUrl && (
                          <button type="button" className={styles.avatarRemoveLink} onClick={removeAvatar}>
                            {t('settings.account.removeAvatar')}
                          </button>
                        )}
                      </div>
                    </div>
                    <div className={styles.accountRow}>
                      <label className={styles.accountLabel} htmlFor="settings-display-name">
                        {t('settings.account.username')}
                      </label>
                      <input
                        id="settings-display-name"
                        type="text"
                        className={styles.accountInput}
                        value={displayName}
                        placeholder={t('settings.account.notSet')}
                        maxLength={64}
                        autoComplete="off"
                        onChange={(e) => setDisplayName(e.target.value)}
                        onBlur={() => setStoredDisplayName(user.id, displayName)}
                      />
                    </div>
                    <div className={styles.accountRow}>
                      <span className={styles.accountLabel}>{t('settings.account.email')}</span>
                      <span className={styles.accountValue}>{maskEmail(user.email)}</span>
                    </div>
                  </>
                )}
              </div>
            )}
            {section === 'legal' && (
              <p className={styles.legalNote}>{t('settings.legal.placeholder')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (!mounted || typeof document === 'undefined') return null;
  return createPortal(modal, document.body);
}

function NavButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      className={`${styles.navItem} ${active ? styles.navItemActive : ''}`}
      onClick={onClick}
    >
      <span className={styles.navIcon}>{icon}</span>
      {label}
    </button>
  );
}

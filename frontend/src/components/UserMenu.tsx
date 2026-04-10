'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import SettingsModal from '@/components/settings/SettingsModal';
import AvatarPlaceholderIcon from '@/components/AvatarPlaceholderIcon';
import { useUserAvatar } from '@/hooks/useUserAvatar';
import { maskEmail } from '@/lib/maskContact';
import { getStoredDisplayName } from '@/lib/userProfile';
import styles from './UserMenu.module.css';

interface UserMenuProps {
  userId: string;
  email: string;
}

export default function UserMenu({ userId, email }: UserMenuProps) {
  const { signOut } = useAuth();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const avatarUrl = useUserAvatar(userId);

  useEffect(() => {
    setDisplayName(getStoredDisplayName(userId));
    const handleProfileUpdate = () => {
      setDisplayName(getStoredDisplayName(userId));
    };
    window.addEventListener('woloong-profile-updated', handleProfileUpdate);
    return () => window.removeEventListener('woloong-profile-updated', handleProfileUpdate);
  }, [userId]);

  return (
    <div className={styles.wrap} ref={ref}>
      <button
        type="button"
        className={styles.avatar}
        onClick={() => setOpen((v) => !v)}
        aria-label={t('userMenu.aria')}
      >
        {avatarUrl ? (
          <img src={avatarUrl} alt="" className={styles.avatarImg} />
        ) : (
          <span className={styles.avatarPlaceholder}>
            <AvatarPlaceholderIcon className={styles.avatarPlaceholderSvg} />
          </span>
        )}
      </button>

      {open && (
        <div className={styles.dropdown}>
          <div className={styles.emailRow}>
            <span className={styles.avatarSm}>
              {avatarUrl ? (
                <img src={avatarUrl} alt="" className={styles.avatarImgSm} />
              ) : (
                <span className={styles.avatarPlaceholderSm}>
                  <AvatarPlaceholderIcon className={styles.avatarPlaceholderSvgSm} />
                </span>
              )}
            </span>
            <div className={styles.userInfoCol}>
              <span className={styles.usernameText}>{displayName || t('settings.account.notSet')}</span>
              <span className={styles.emailText}>{maskEmail(email)}</span>
            </div>
          </div>

          <div className={styles.divider} />

          <button
            type="button"
            className={styles.menuItem}
            onClick={() => {
              setOpen(false);
              setSettingsOpen(true);
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
            {t('userMenu.settings')}
          </button>

          <Link
            href="/about"
            className={styles.menuItem}
            onClick={() => setOpen(false)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
            {t('userMenu.about')}
          </Link>

          <div className={styles.divider} />

          <button
            className={`${styles.menuItem} ${styles.menuItemDanger}`}
            onClick={() => { signOut(); setOpen(false); }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
            {t('userMenu.logout')}
          </button>
        </div>
      )}

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

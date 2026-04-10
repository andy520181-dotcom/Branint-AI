'use client';

import { SiteNavLogo } from '@/components/SiteNavLogo';
import styles from './WorkspaceTopBar.module.css';

type TFn = (key: string) => string;

export interface WorkspaceTopBarProps {
  historyOpen: boolean;
  onToggleHistory: () => void;
  onNewConversation: () => void;
  isComplete: boolean;
  error: string | null;
  showHeroInput: boolean;
  isLoading?: boolean;
  t: TFn;
}

export function WorkspaceTopBar({
  historyOpen,
  onToggleHistory,
  onNewConversation,
  isComplete,
  error,
  showHeroInput,
  isLoading,
  t,
}: WorkspaceTopBarProps) {
  return (
    <header className={styles.topBar}>
      <div className={styles.topBarBrand}>
        <SiteNavLogo />
        <button
          type="button"
          className={`${styles.topBarHistoryBtn} ${styles.historyToggleBtn} ${historyOpen ? styles.historyToggleBtnActive : ''}`}
          onClick={onToggleHistory}
          title={t('workspace.historyToggle')}
          aria-expanded={historyOpen}
          aria-label={t('workspace.historyToggle')}
        >
          <svg width="13" height="11" viewBox="0 0 16 14" fill="none" aria-hidden>
            <rect x="0" y="0" width="16" height="2" rx="1" fill="currentColor" />
            <rect x="0" y="6" width="11" height="2" rx="1" fill="currentColor" />
            <rect x="0" y="12" width="7" height="2" rx="1" fill="currentColor" />
          </svg>
        </button>
        <button
          type="button"
          className={`${styles.topBarHistoryBtn} ${styles.historyToggleBtn}`}
          onClick={onNewConversation}
          title={t('workspace.newChat')}
          aria-label={t('workspace.newChat')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v8M8 12h8" />
          </svg>
        </button>
      </div>
      <div className={styles.statusBadge}>
        {isLoading ? null : isComplete ? (
          <>
            <span className={styles.dotDone} /> {t('workspace.status.done')}
          </>
        ) : error ? (
          <>
            <span className={styles.dotRed} /> {t('workspace.status.error')}
          </>
        ) : showHeroInput ? (
          <>
            <span className={styles.dotIdle} /> {t('workspace.status.idle')}
          </>
        ) : (
          <>
            <span className={styles.dotPulse} /> {t('workspace.status.running')}
          </>
        )}
      </div>
    </header>
  );
}

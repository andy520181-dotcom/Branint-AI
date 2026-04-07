'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { SiteNavAuth } from '@/components/SiteNavAuth';
import AuthModal from '@/components/auth/AuthModal';
import { HistoryItem } from '@/types';
import { fetchSessions } from '@/lib/api';
import styles from './page.module.css';

export default function HistoryPage() {
  const { t, resolvedLocale } = useLocale();
  const { user } = useAuth();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    if (!user?.id) {
      setItems([]);
      return;
    }
    fetchSessions(user.id)
      .then(dbSessions => {
        setItems(dbSessions.map(s => ({
          sessionId: s.session_id,
          title: s.title,
          createdAt: s.created_at,
          isPinned: s.is_pinned,
          shareUrl: `/workspace/${s.session_id}`
        })));
      })
      .catch(console.error);
  }, [user?.id]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const tag = resolvedLocale === 'en' ? 'en-US' : 'zh-CN';
    return d.toLocaleDateString(tag, { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className={styles.page}>
      {/* 导航栏 */}
      <nav className={`site-nav ${styles.navBordered}`}>
        <div className="site-nav-left">
          <SiteNavLogo />
          <div className="site-nav-links">
            <a href="/#features" className="site-nav-link">{t('nav.features')}</a>
            <a href="/#pricing" className="site-nav-link">{t('nav.pricing')}</a>
          </div>
        </div>
        <div className="site-nav-right">
          <SiteNavAuth onLoginClick={() => setShowAuth(true)} />
        </div>
      </nav>

      <main className={`${styles.main} ${items.length === 0 ? styles.mainEmpty : ''}`}>
        {items.length === 0 ? (
          <div className={styles.emptyState}>
            <h1 className={styles.srOnly}>{t('history.title')}</h1>
            <p className={styles.emptyHint}>{t('history.empty')}</p>
            <span className={styles.emptyArrow} aria-hidden>
              →
            </span>
            <Link href="/" className={`btn-primary ${styles.startBtn}`}>
              {t('history.cta')}
            </Link>
          </div>
        ) : (
          <>
            <header className={styles.header}>
              <h1 className={styles.title}>{t('history.title')}</h1>
            </header>
            <div className={styles.list}>
              {items.map((item, index) => (
                <Link
                  key={`${item.sessionId}-${item.createdAt}-${index}`}
                  href={`/workspace/${item.sessionId}`}
                  className={styles.card}
                >
                  <div className={styles.cardIcon} aria-hidden>
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                      <line x1="10" y1="9" x2="8" y2="9" />
                    </svg>
                  </div>
                  <div className={styles.cardBody}>
                    <p className={styles.cardTitle}>{item.title}</p>
                    <p className={styles.cardDate}>{formatDate(item.createdAt)}</p>
                  </div>
                  <svg className={styles.cardArrow} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 18l6-6-6-6"/>
                  </svg>
                </Link>
              ))}
            </div>
          </>
        )}
      </main>

      {showAuth && (
        <AuthModal onClose={() => setShowAuth(false)} onSuccess={() => setShowAuth(false)} />
      )}
    </div>
  );
}

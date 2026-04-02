'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useHistory } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { SiteNavAuth } from '@/components/SiteNavAuth';
import AuthModal from '@/components/auth/AuthModal';
import { HistoryItem } from '@/types';
import styles from './page.module.css';

export default function HistoryPage() {
  const { t, resolvedLocale } = useLocale();
  const { getHistory } = useHistory();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    setItems(getHistory());
  }, [getHistory]);

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

      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>{t('history.title')}</h1>
          <p className={styles.subtitle}>{t('history.subtitle')}</p>
        </div>

        {items.length === 0 ? (
          <div className={styles.empty}>
            <span className={styles.emptyIcon}>📋</span>
            <p className={styles.emptyText}>{t('history.empty')}</p>
            <Link href="/" className={`btn-primary ${styles.startBtn}`}>
              {t('history.cta')}
            </Link>
          </div>
        ) : (
          <div className={styles.list}>
            {items.map((item, index) => (
              <Link
                key={`${item.sessionId}-${item.createdAt}-${index}`}
                href={`/workspace/${item.sessionId}`}
                className={styles.card}
              >
                <div className={styles.cardIcon}>📄</div>
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
        )}
      </main>

      {showAuth && (
        <AuthModal onClose={() => setShowAuth(false)} onSuccess={() => setShowAuth(false)} />
      )}
    </div>
  );
}

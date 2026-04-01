'use client';

import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import UserMenu from '@/components/UserMenu';
import AuthModal from '@/components/auth/AuthModal';
import { useState } from 'react';
import styles from '../history/page.module.css';

export default function AboutPage() {
  const { user } = useAuth();
  const { t } = useLocale();
  const [showAuth, setShowAuth] = useState(false);

  return (
    <div className={styles.page}>
      <nav className={`site-nav ${styles.navBordered}`}>
        <div className="site-nav-left">
          <Link href="/" className="site-nav-logo">
            <span>⚡</span>
            <span>Brandclaw AI</span>
          </Link>
          <div className="site-nav-links">
            <a href="/#features" className="site-nav-link">{t('nav.features')}</a>
            <a href="/#pricing" className="site-nav-link">{t('nav.pricing')}</a>
          </div>
        </div>
        <div className="site-nav-right">
          {user
            ? <UserMenu userId={user.id} email={user.email} />
            : <button className="btn-ghost" onClick={() => setShowAuth(true)}>{t('nav.login')}</button>}
        </div>
      </nav>

      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>{t('about.title')}</h1>
          <p className={styles.subtitle}>{t('about.subtitle')}</p>
        </div>
      </main>

      {showAuth && (
        <AuthModal onClose={() => setShowAuth(false)} onSuccess={() => setShowAuth(false)} />
      )}
    </div>
  );
}

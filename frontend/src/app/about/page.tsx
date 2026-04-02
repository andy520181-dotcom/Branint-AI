'use client';

import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useLocale } from '@/hooks/useLocale';
import { SiteNavAuth } from '@/components/SiteNavAuth';
import AuthModal from '@/components/auth/AuthModal';
import { useState } from 'react';
import styles from '../history/page.module.css';

export default function AboutPage() {
  const { t } = useLocale();
  const [showAuth, setShowAuth] = useState(false);

  return (
    <div className={styles.page}>
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

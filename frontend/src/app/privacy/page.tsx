'use client';

import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useLocale } from '@/hooks/useLocale';
import styles from '../legal/document.module.css';

export default function PrivacyPage() {
  const { t } = useLocale();

  return (
    <div className={styles.page}>
      <nav className={`site-nav ${styles.navBordered}`}>
        <div className="site-nav-left">
          <SiteNavLogo />
        </div>
      </nav>

      <main className={styles.main}>
        <Link href="/" className={styles.back}>
          ← {t('legal.backHome')}
        </Link>
        <h1 className={styles.title}>{t('legal.privacyTitle')}</h1>
        <p className={styles.body}>{t('legal.privacyBody')}</p>
      </main>
    </div>
  );
}

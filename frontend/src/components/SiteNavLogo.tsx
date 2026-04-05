'use client';

import Image from 'next/image';
import Link from 'next/link';

export function SiteNavLogo() {
  return (
    <Link href="/" className="site-nav-logo">
      <Image
        src="/logo.png"
        alt="Branin AI"
        width={80}
        height={80}
        className="site-nav-logo-img"
        priority
      />
      <span>Branin AI</span>
    </Link>
  );
}

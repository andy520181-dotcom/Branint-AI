'use client';

import Image from 'next/image';
import Link from 'next/link';

export function SiteNavLogo() {
  return (
    <Link href="/" className="site-nav-logo">
      <Image
        src="/logo.png"
        alt="Brandclaw AI"
        width={80}
        height={80}
        className="site-nav-logo-img"
        priority
      />
      <span>Brandclaw AI</span>
    </Link>
  );
}

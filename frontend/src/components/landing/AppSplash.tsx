'use client';

import Image from 'next/image';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import styles from './AppSplash.module.css';

const SPLASH_MS = 1800;
const FADE_MS = 450;
const SESSION_KEY = 'bc_splash_seen';

/**
 * 同一次页面加载内，首轮启动动画已开始过后为 true。
 * 用于在 React Strict Mode 第二次挂载时不再叠一层全屏启动页。
 */
let splashCycleStarted = false;

export interface AppSplashProps {
  /** 动画结束后调用（组件内会先写入 sessionStorage） */
  onComplete: () => void;
}

/** 首页启动全屏层：仅品牌图标 */
export function AppSplash({ onComplete }: AppSplashProps) {
  const dupRef = useRef<boolean | null>(null);
  if (dupRef.current === null) {
    dupRef.current = splashCycleStarted;
  }
  const isStrictRemount = dupRef.current;

  const [exiting, setExiting] = useState(false);
  const doneRef = useRef(false);

  useLayoutEffect(() => {
    if (isStrictRemount) {
      onComplete();
      return;
    }
    splashCycleStarted = true;
  }, [isStrictRemount, onComplete]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    if (isStrictRemount) return;
    const t = window.setTimeout(() => setExiting(true), SPLASH_MS);
    return () => window.clearTimeout(t);
  }, [isStrictRemount]);

  useEffect(() => {
    if (isStrictRemount) return;
    if (!exiting) return;
    const t = window.setTimeout(() => {
      if (doneRef.current) return;
      doneRef.current = true;
      try {
        sessionStorage.setItem(SESSION_KEY, '1');
      } catch {
        /* ignore */
      }
      onComplete();
    }, FADE_MS);
    return () => window.clearTimeout(t);
  }, [exiting, isStrictRemount, onComplete]);

  if (isStrictRemount) {
    return null;
  }

  return (
    <div className={styles.root} data-component="splash" data-exiting={exiting} aria-hidden="true">
      <div className={styles.logoWrap}>
        <Image
          src="/logo.png"
          alt=""
          width={128}
          height={128}
          className={styles.logo}
          priority
        />
      </div>
    </div>
  );
}

export function shouldSkipSplash(): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(SESSION_KEY) === '1';
}

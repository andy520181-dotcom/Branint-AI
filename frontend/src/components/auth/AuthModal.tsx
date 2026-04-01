'use client';

import Link from 'next/link';
import { useState } from 'react';
import styles from './AuthModal.module.css';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';

interface AuthModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

type Mode = 'login' | 'register';

export default function AuthModal({ onClose, onSuccess }: AuthModalProps) {
  const { login, register, sendOtp } = useAuth();
  const { t } = useLocale();

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [resendCd, setResendCd] = useState(0);
  const [error, setError] = useState('');

  const switchMode = (m: Mode) => {
    setMode(m);
    setError('');
    setOtp('');
    setOtpSent(false);
    setResendCd(0);
  };

  const startCountdown = () => {
    setResendCd(60);
    const timer = setInterval(() => {
      setResendCd((prev) => {
        if (prev <= 1) { clearInterval(timer); return 0; }
        return prev - 1;
      });
    }, 1000);
  };

  const handleSendOtp = async () => {
    if (!email || !email.includes('@')) {
      setError(t('auth.err.emailFirst'));
      return;
    }
    setError('');
    setOtpSent(true);
    startCountdown();
    // 后台静默发送，不阻塞 UI
    sendOtp(email).catch((err) => {
      const msg = err instanceof Error ? err.message : t('auth.err.sendFailed');
      setError(msg.includes('rate limit') ? t('auth.err.rateLimit') : msg);
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !email.includes('@')) { setError(t('auth.err.emailInvalid')); return; }
    if (!password || password.length < 6) { setError(t('auth.err.passwordShort')); return; }

    if (mode === 'register') {
      if (!otp.trim()) { setError(t('auth.err.otpRequired')); return; }
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, otp.trim(), password);
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.err.generic'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>

        <button className={styles.closeBtn} onClick={onClose} aria-label={t('auth.close')}>✕</button>

        <h2 className={styles.title}>{t('auth.welcome')}</h2>

        <form className={styles.form} onSubmit={handleSubmit}>

          {/* 邮箱 */}
          <div className={styles.inputRow}>
            <span className={styles.inputLabel}>{t('auth.email')}</span>
            <input
              type="email"
              className={styles.inputField}
              placeholder={t('auth.placeholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              autoComplete="email"
            />
          </div>

          {/* 验证码（仅注册） */}
          {mode === 'register' && (
            <div className={styles.inputRow}>
              <span className={styles.inputLabel}>{t('auth.otp')}</span>
              <input
                type="text"
                className={styles.inputField}
                placeholder={t('auth.placeholder')}
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                maxLength={4}
                autoComplete="one-time-code"
              />
              <button
                type="button"
                className={styles.otpBtn}
                onClick={handleSendOtp}
                disabled={resendCd > 0}
              >
                {resendCd > 0 ? `${resendCd}s` : otpSent ? t('auth.resendOtp') : t('auth.sendOtp')}
              </button>
            </div>
          )}

          {/* 密码 */}
          <div className={styles.inputRow}>
            <span className={styles.inputLabel}>{t('auth.password')}</span>
            <input
              type={showPassword ? 'text' : 'password'}
              className={styles.inputField}
              placeholder={t('auth.placeholder')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
            <button
              type="button"
              className={styles.eyeBtn}
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
            >
              {showPassword ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button
            type="submit"
            className={styles.submitBtn}
            disabled={loading}
          >
            {loading ? t('auth.loading') : mode === 'login' ? t('auth.login') : t('auth.register')}
          </button>
        </form>

        <div className={styles.toggle}>
          {mode === 'login' ? (
            <>{t('auth.noAccount')}<button type="button" onClick={() => switchMode('register')}>{t('auth.signUp')}</button></>
          ) : (
            <>{t('auth.hasAccount')}<button type="button" onClick={() => switchMode('login')}>{t('auth.signIn')}</button></>
          )}
        </div>

        <p className={styles.legal}>
          {t('auth.legal.lead')}
          <Link href="/terms" target="_blank" rel="noopener noreferrer" className={styles.legalLink}>
            {t('auth.legal.terms')}
          </Link>
          {t('auth.legal.and')}
          <Link href="/privacy" target="_blank" rel="noopener noreferrer" className={styles.legalLink}>
            {t('auth.legal.privacy')}
          </Link>
        </p>
      </div>
    </div>
  );
}

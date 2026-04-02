'use client';

import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useRouter } from 'next/navigation';
import AuthModal from '@/components/auth/AuthModal';
import { SiteNavAuth } from '@/components/SiteNavAuth';
import { useAuth } from '@/hooks/useAuth';
import { useHistory } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { createSession } from '@/lib/api';
import { USER_PROMPT_MAX_CHARS } from '@/lib/promptLimits';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import heroStyles from '@/components/landing/landingHero.module.css';
import { AppSplash, shouldSkipSplash } from '@/components/landing/AppSplash';
import styles from './page.module.css';

/** 落地页展示的 5 个 Agent（按 index 升序，排除 consultant_review） */
const LANDING_AGENTS = AGENT_CONFIGS
  .filter((a) => a.id !== 'consultant_review')
  .sort((a, b) => a.index - b.index);

const EXAMPLE_PROMPTS = [
  '给一个宠物营养品创业项目包装一个品牌名字并设计一个logo',
  '给一个面向 25-35 岁都市女性的轻奢咖啡做一个品牌定位分析',
  '为一家专注 Z 世代的国潮服饰品牌制定一套品牌战略',
  '为一个独立女性的高端护肤品牌制定一套新媒体内容运营策略',
];

const EXAMPLE_PROMPTS_EN = [
  'Build a light-luxury coffee brand for urban women aged 25–35',
  'I have a pet nutrition startup and need full brand positioning',
  'Define strategy for a Gen-Z streetwear brand with Chinese cultural flair',
  'Build a premium skincare brand for independent women focused on ingredient science',
];

export default function LandingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { addHistory, getHistory } = useHistory();
  const { t, resolvedLocale } = useLocale();
  const examplePrompts = resolvedLocale === 'en' ? EXAMPLE_PROMPTS_EN : EXAMPLE_PROMPTS;
  const [prompt, setPrompt] = useState('');
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 内容变化时自动调整高度，最小保持初始高度 50px
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 50)}px`;
  }, [prompt]);
  const [showAuth, setShowAuth] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [pendingSubmit, setPendingSubmit] = useState(false);
  const [toast, setToast] = useState('');
  /** 启动页：首帧与 SSR 一致为 false，避免 hydration 不匹配；再在 layoutEffect 里同步 sessionStorage */
  const [splashDone, setSplashDone] = useState(false);
  /** 与 SSR 首屏一致为 /history，挂载后再读 localStorage，避免 Nav Link hydration mismatch */
  const [workspaceHref, setWorkspaceHref] = useState('/history');

  useLayoutEffect(() => {
    if (shouldSkipSplash()) setSplashDone(true);
  }, []);

  useEffect(() => {
    const recent = getHistory()[0];
    setWorkspaceHref(recent ? `/workspace/${recent.sessionId}` : '/history');
  }, [getHistory]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2000);
  };
  // LED 轮播
  const [ledIndex, setLedIndex] = useState(0);
  const [ledVisible, setLedVisible] = useState(true);

  useEffect(() => {
    if (focused || prompt) return;
    const id = setInterval(() => {
      // 先淡出，再切换，再淡入
      setLedVisible(false);          // 旧文字向上滑出
      setTimeout(() => {
        setLedIndex((i) => (i + 1) % examplePrompts.length);
        setLedVisible(true);         // 新文字从下方滑入
      }, 520);
    }, 5000);
    return () => clearInterval(id);
  }, [focused, prompt, examplePrompts.length]);

  /** 登录成功后若有待提交意图，在 user 更新的新 render 中自动提交 */
  useEffect(() => {
    if (user && pendingSubmit) {
      setPendingSubmit(false);
      void doSubmit(user, prompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  /** 实际调用后端创建会话的逻辑（user 由调用方传入，避免闭包陈旧值） */
  const doSubmit = async (
    currentUser: { id: string; email: string },
    currentPrompt: string,
  ) => {
    if (!currentPrompt.trim() || currentPrompt.trim().length < 10) {
      setError(t('error.minChars'));
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const session_id = await createSession(currentUser.id, currentPrompt.trim());
      addHistory({
        sessionId: session_id,
        title: currentPrompt.trim().slice(0, 40),
        createdAt: new Date().toISOString(),
        shareUrl: `/workspace/${session_id}`,
      });
      // NOTE: 工作台页面通过 sessionStorage 判断是新会话还是历史会话
      // 如果缺少这一步，工作台会误走 fetchReport 分支，显示"分析完成"空页面
      sessionStorage.setItem(`prompt_${session_id}`, currentPrompt.trim());
      router.push(`/workspace/${session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('error.network'));
      setSubmitting(false);
    }
  };

  /** 提交品牌需求，创建会话后跳转工作台 */
  const handleSubmit = async () => {
    if (!user) {
      setPendingSubmit(true);
      setShowAuth(true);
      return;
    }
    if (!prompt.trim()) {
      showToast(t('toast.emptyPrompt'));
      return;
    }
    await doSubmit(user, prompt);
  };

  return (
    <div className={styles.page}>
      {!splashDone && (
        <AppSplash onComplete={() => setSplashDone(true)} />
      )}
      {/* 导航栏 */}
      <nav className="site-nav">
        <div className="site-nav-left">
          <SiteNavLogo />
          <div className="site-nav-links">
            <a href="#features" className="site-nav-link">{t('nav.features')}</a>
            <a href="#pricing" className="site-nav-link">{t('nav.pricing')}</a>
            <Link href={workspaceHref} className="site-nav-link">
              {t('nav.workspace')}
            </Link>
          </div>
        </div>
        <div className="site-nav-right">
          <SiteNavAuth onLoginClick={() => setShowAuth(true)} loginButtonId="nav-login-btn" />
        </div>
      </nav>

      {/* Hero 区域 */}
      <main className={heroStyles.hero}>
        {/* 装饰光晕 */}
        <div className={heroStyles.glowOrb1} />
        <div className={heroStyles.glowOrb2} />

        {/* 主标题 */}
        <h1 className={heroStyles.headline}>
          <span className={heroStyles.headlinePrimary}>{t('hero.line1')}</span>
          <span className={heroStyles.headlineSub}>{t('hero.line2')}</span>
        </h1>


        {/* 输入框 */}
        <div className={heroStyles.inputWrapper}>
          <div className={heroStyles.textareaWrap}>
            {/* LED 示例轮播 — 绝对定位覆盖，不影响 textarea 高度 */}
            {!prompt && !focused && (
              <div
                className={heroStyles.ledOverlay}
                onClick={() => { setPrompt(examplePrompts[ledIndex]); }}
              >
                <span
                  key={ledIndex}
                  className={`${heroStyles.ledText} ${ledVisible ? heroStyles.ledIn : heroStyles.ledOut}`}
                >
                  {examplePrompts[ledIndex]}
                </span>
              </div>
            )}
          <textarea
            ref={textareaRef}
            id="brand-prompt-input"
            className={heroStyles.textarea}
            placeholder={focused ? t('input.placeholder') : ''}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            maxLength={USER_PROMPT_MAX_CHARS}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
            }}
          />
          </div>
          <div className={heroStyles.inputFooter}>
            <button
              id="start-analysis-btn"
              type="button"
              className={`icon-btn-circle ${heroStyles.submitBtn}`}
              onClick={handleSubmit}
              disabled={!prompt.trim() || submitting}
              title={t('input.submitTitle')}
            >
              {submitting ? (
                <span className={heroStyles.spinner} />
              ) : (
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M10 15V5M10 5L5 10M10 5L15 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
          {error && <p className={heroStyles.error}>{error}</p>}
        </div>

        {/* Agent 展示 */}
        <section id="features" className={styles.agentsSection} aria-label={t('nav.features')}>
        <div className={styles.agentsRow}>
          {LANDING_AGENTS.map((a) => (
            <div key={a.id} className={styles.agentPill} style={{ '--agent-color': a.color } as React.CSSProperties}>
              {/* 上方：头像 + 名称 */}
              <div className={styles.agentPillBody}>
                <div className={styles.agentPillAvatar} data-component="agent-avatar">
                  <img src={a.avatar} alt={a.charName} width={34} height={34} fetchPriority="high" decoding="sync" />
                </div>
                <div className={styles.agentPillHeader}>
                  <span className={styles.agentPillName}>{t(`agent.${a.id}.name`)}</span>
                  <span className={styles.agentPillCharName}>{a.charName}</span>
                </div>
              </div>
              {/* 下方：描述文字，· 分隔，每段不断行 */}
              <p className={styles.agentPillTags}>
                {t(`agent.${a.id}.desc`)
                  .split('·')
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .map((tag, j) => (
                  <span key={j} style={{ whiteSpace: 'nowrap' }}>{j > 0 ? '·' : ''}{tag}</span>
                ))}
              </p>
            </div>
          ))}
        </div>
        </section>
        {/* 定价锚点占位（无文案），供导航 #pricing 滚动定位 */}
        <div id="pricing" aria-hidden="true" className={styles.pricingAnchor} />
      </main>

      {/* Auth 弹窗 */}
      {showAuth && (
        <AuthModal
          onClose={() => { setShowAuth(false); setPendingSubmit(false); }}
          onSuccess={() => setShowAuth(false)}
        />
      )}

      {/* Toast 提示 */}
      {toast && <div className={styles.toast}>{toast}</div>}
    </div>
  );
}

'use client';

import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { SiteNavLogo } from '@/components/SiteNavLogo';
import { useRouter } from 'next/navigation';
import AuthModal from '@/components/auth/AuthModal';
import { SiteNavAuth } from '@/components/SiteNavAuth';
import { useAuth } from '@/hooks/useAuth';
import { useLocale } from '@/hooks/useLocale';
import { createSession, uploadAsset, fetchSessions } from '@/lib/api';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import heroStyles from '@/components/landing/landingHero.module.css';
import { SharedHeroInput } from '@/components/landing/SharedHeroInput';
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
  const { t, resolvedLocale } = useLocale();
  const examplePrompts = resolvedLocale === 'en' ? EXAMPLE_PROMPTS_EN : EXAMPLE_PROMPTS;
  const [prompt, setPrompt] = useState('');
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // 附件列表状态
  const [attachments, setAttachments] = useState<Array<{ file: File; previewUrl: string }>>([]); 

  // 内容变化时自动调整高度，最小保持初始高度 50px
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight, 50)}px`;
  }, [prompt]);
  const [showAuth, setShowAuth] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pendingSubmit, setPendingSubmit] = useState(false);
  const [toast, setToast] = useState('');
  /** 启动页：首帧与 SSR 一致为 false，避免 hydration 不匹配；再在 layoutEffect 里同步 sessionStorage */
  const [splashDone, setSplashDone] = useState(false);
  const [hasHistory, setHasHistory] = useState<boolean | null>(null);

  useLayoutEffect(() => {
    if (shouldSkipSplash()) setSplashDone(true);
  }, []);

  useEffect(() => {
    if (user?.id) {
       fetchSessions(user.id).then(res => {
         setHasHistory(res.length > 0);
       }).catch(err => {
         console.error(err);
         setHasHistory(false);
       });
    } else {
       setHasHistory(null);
    }
  }, [user?.id]);

  const showToast = (msg: string, durationMs = 2800) => {
    setToast(msg);
    setTimeout(() => setToast(''), durationMs);
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

  /**
   * 实际提交："先跳转，后创建" 模式
   * 前端生成 UUID 后立即跳转到 workspace 页面，
   * createSession 调用推迟到 workspace 页面中执行，消除等待后端响应的卡顿。
   */
  const doSubmit = useCallback(async (
    currentUser: { id: string; email: string },
    currentPrompt: string,
  ) => {
    if (!currentPrompt.trim()) return;
    setSubmitting(true);
    try {
      // NOTE: 附件需要预上传（workspace 页面不处理文件对象），
      // 但不阻塞跳转——并行上传并将 URL 写入 sessionStorage
      const uploadPromises = attachments.map(async (item) => {
        try {
          const { url } = await uploadAsset(item.file);
          return url;
        } catch { return null; }
      });

      // 生成本地 UUID，立即跳转 (带随机回退)
      const sessionId = typeof crypto !== 'undefined' && crypto.randomUUID 
        ? crypto.randomUUID() 
        : Math.random().toString(36).substring(2, 15);
      const trimmedPrompt = currentPrompt.trim();

      // 将会话数据写入 sessionStorage，workspace 页面读取后创建后端会话
      sessionStorage.setItem(`prompt_${sessionId}`, trimmedPrompt);
      sessionStorage.setItem(`user_${sessionId}`, currentUser.id);

      // NOTE: 立即跳转！用户感受到即时切换，无需等待 createSession 响应
      router.push(`/workspace/${sessionId}`);

      // 后台等待附件上传完成，写入 sessionStorage 供 workspace 使用
      const uploadedUrls = (await Promise.all(uploadPromises)).filter(Boolean) as string[];
      if (uploadedUrls.length > 0) {
        sessionStorage.setItem(`attachments_${sessionId}`, JSON.stringify(uploadedUrls));
      }
      attachments.forEach((it) => URL.revokeObjectURL(it.previewUrl));
      setAttachments([]);
    } catch (err) {
      showToast(err instanceof Error ? err.message : t('error.network'), 3200);
      setSubmitting(false);
    }
  }, [attachments, router, t]);

  /** 提交品牌需求，创建会话后跳转工作台 */
  const handleSubmit = async () => {
    if (!user) {
      setPendingSubmit(true);
      setShowAuth(true);
      return;
    }
    if (!prompt.trim()) return;
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
            <a 
              href="#"
              className="site-nav-link"
              onClick={(e) => {
                e.preventDefault();
                if (!user) {
                  setShowAuth(true);
                  return;
                }

                // 无论是新老用户，直接跳转到独立工作台的空壳
                // 左侧记录栏会在工作台内部异步拉取历史记录
                const newId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
                sessionStorage.setItem(`workspace_blank_${newId}`, '1');
                router.push(`/workspace/${newId}`);
              }}
            >
              {t('nav.workspace')}
            </a>
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


        {/* 输入框 — 使用共享组件，LED轮播通过 ledNode 传入 */}
        <SharedHeroInput
          textareaRef={textareaRef}
          value={prompt}
          onChange={setPrompt}
          focused={focused}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onSubmit={handleSubmit}
          submitting={submitting}
          attachments={attachments}
          onAttachmentsChange={setAttachments}
          placeholder={t('input.placeholder')}
          ledNode={
            <span
              key={ledIndex}
              className={`${heroStyles.ledText} ${ledVisible ? heroStyles.ledIn : heroStyles.ledOut}`}
              onClick={() => setPrompt(examplePrompts[ledIndex])}
            >
              {examplePrompts[ledIndex]}
            </span>
          }
          t={t}
        />

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

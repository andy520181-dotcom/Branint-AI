'use client';

import type { RefObject } from 'react';
import heroStyles from '@/components/landing/landingHero.module.css';

type TFn = (key: string) => string;

export interface WorkspaceHeroEmptyProps {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  bottomPrompt: string;
  setBottomPrompt: (v: string) => void;
  heroFocused: boolean;
  setHeroFocused: (v: boolean) => void;
  onSubmit: () => void | Promise<void>;
  submitting: boolean;
  user: { id: string } | null;
  t: TFn;
}

export function WorkspaceHeroEmpty({
  textareaRef,
  bottomPrompt,
  setBottomPrompt,
  heroFocused,
  setHeroFocused,
  onSubmit,
  submitting,
  user,
  t,
}: WorkspaceHeroEmptyProps) {
  return (
    <div className={heroStyles.hero}>
      <h1 className={heroStyles.headline}>
        <span className={heroStyles.headlinePrimary}>{t('hero.line1')}</span>
        <span className={heroStyles.headlineSub}>{t('hero.line2')}</span>
      </h1>
      <div className={heroStyles.inputWrapper}>
        <div className={heroStyles.textareaWrap}>
          {!bottomPrompt && !heroFocused && (
            <div className={heroStyles.ledOverlay} onClick={() => textareaRef.current?.focus()}>
              <span className={heroStyles.ledText}>{t('workspace.bottom.placeholder')}</span>
            </div>
          )}
          <textarea
            ref={textareaRef}
            className={heroStyles.textarea}
            placeholder={heroFocused ? t('workspace.bottom.placeholder') : ''}
            value={bottomPrompt}
            onChange={(e) => setBottomPrompt(e.target.value)}
            onFocus={() => setHeroFocused(true)}
            onBlur={() => setHeroFocused(false)}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void onSubmit();
              }
            }}
          />
        </div>
        <div className={heroStyles.inputFooter}>
          <button
            type="button"
            className={`icon-btn-circle ${heroStyles.submitBtn}`}
            onClick={() => void onSubmit()}
            disabled={!bottomPrompt.trim() || submitting || !user}
            title={t('workspace.send.title')}
          >
            {submitting ? (
              <span className={heroStyles.spinner} />
            ) : (
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M10 15V5M10 5L5 10M10 5L15 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

'use client';

import type { RefObject } from 'react';
import heroStyles from '@/components/landing/landingHero.module.css';
import { SharedHeroInput, type AttachmentItem } from '@/components/landing/SharedHeroInput';

// 重新导出供 page.tsx 使用，统一导入来源
export type { AttachmentItem };

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
  attachments: AttachmentItem[];
  onAttachmentsChange: (items: AttachmentItem[]) => void;
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
  attachments,
  onAttachmentsChange,
  t,
}: WorkspaceHeroEmptyProps) {
  return (
    <div className={heroStyles.hero}>
      <h1 className={heroStyles.headline}>
        <span className={heroStyles.headlinePrimary}>{t('hero.line1')}</span>
        <span className={heroStyles.headlineSub}>{t('hero.line2')}</span>
      </h1>
      {/* NOTE: 工作台空白态直接使用共享输入框组件，无 LED 轮播（ledNode 不传） */}
      <SharedHeroInput
        textareaRef={textareaRef}
        value={bottomPrompt}
        onChange={setBottomPrompt}
        focused={heroFocused}
        onFocus={() => setHeroFocused(true)}
        onBlur={() => setHeroFocused(false)}
        onSubmit={onSubmit}
        submitting={submitting}
        disabled={!user}
        attachments={attachments}
        onAttachmentsChange={onAttachmentsChange}
        t={t}
      />
    </div>
  );
}

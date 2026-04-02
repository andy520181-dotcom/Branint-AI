'use client';

import type { RefObject } from 'react';
import { USER_PROMPT_MAX_CHARS } from '@/lib/promptLimits';
import styles from './WorkspaceBottomBar.module.css';

type TFn = (key: string) => string;

export interface WorkspaceBottomBarProps {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  bottomPrompt: string;
  setBottomPrompt: (v: string) => void;
  onSubmit: () => void | Promise<void>;
  isStreaming: boolean;
  submitting: boolean;
  onCancel: () => void;
  t: TFn;
}

export function WorkspaceBottomBar({
  textareaRef,
  bottomPrompt,
  setBottomPrompt,
  onSubmit,
  isStreaming,
  submitting,
  onCancel,
  t,
}: WorkspaceBottomBarProps) {
  return (
    <div className={styles.bottomBar}>
      <div className={styles.bottomInner}>
        <div className={styles.bottomSpacer} />
        <div className={styles.bottomInputWrap}>
          <textarea
            ref={textareaRef}
            className={styles.bottomTextarea}
            placeholder={t('workspace.bottom.placeholder')}
            value={bottomPrompt}
            onChange={(e) => setBottomPrompt(e.target.value)}
            rows={1}
            maxLength={USER_PROMPT_MAX_CHARS}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void onSubmit();
              }
            }}
          />
          <div className={styles.bottomActions}>
            {isStreaming && (
              <button type="button" className={styles.cancelBtn} onClick={onCancel} title={t('workspace.cancel.title')}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="3" y="3" width="8" height="8" rx="1.5" fill="currentColor" />
                </svg>
                {t('workspace.cancel')}
              </button>
            )}
            <button
              type="button"
              className={`icon-btn-circle ${styles.bottomSendBtn} ${isStreaming || submitting ? styles.bottomSendBtnActive : ''}`}
              onClick={() => void onSubmit()}
              disabled={!bottomPrompt.trim() || submitting}
              title={t('workspace.send.title')}
            >
              {submitting ? (
                <span className={styles.bottomSpinner} />
              ) : isStreaming ? (
                <span className={styles.streamingDots}>
                  <span />
                  <span />
                  <span />
                </span>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 12V4M8 4L4 8M8 4L12 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

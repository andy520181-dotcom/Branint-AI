'use client';

import { useRef, type RefObject } from 'react';
import heroStyles from '@/components/landing/landingHero.module.css';
import styles from './WorkspaceHeroEmpty.module.css';

type TFn = (key: string) => string;

/** 附件预览信息（与 WorkspaceBottomBar 保持一致） */
export interface AttachmentItem {
  file: File;
  previewUrl: string;
}

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAttachClick = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const newItems: AttachmentItem[] = files.map((f) => ({
      file: f,
      previewUrl: URL.createObjectURL(f),
    }));
    onAttachmentsChange([...attachments, ...newItems]);
    e.target.value = '';
  };

  const handleRemove = (index: number) => {
    URL.revokeObjectURL(attachments[index].previewUrl);
    onAttachmentsChange(attachments.filter((_, i) => i !== index));
  };

  const isImage = (file: File) => file.type.startsWith('image/');

  return (
    <div className={heroStyles.hero}>
      <h1 className={heroStyles.headline}>
        <span className={heroStyles.headlinePrimary}>{t('hero.line1')}</span>
        <span className={heroStyles.headlineSub}>{t('hero.line2')}</span>
      </h1>
      <div className={heroStyles.inputWrapper}>
        {/* ── 附件预览条 ─────────────────────────────── */}
        {attachments.length > 0 && (
          <div className={styles.attachmentsRow}>
            {attachments.map((item, idx) => (
              <div key={idx} className={styles.attachmentChip}>
                {isImage(item.file) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.previewUrl}
                    alt={item.file.name}
                    className={styles.attachmentThumb}
                  />
                ) : (
                  <div className={styles.attachmentFileIcon}>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <rect x="2" y="1" width="9" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                      <path d="M8 1v4h4" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                      <path d="M4 8.5h6M4 10.5h4" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
                    </svg>
                  </div>
                )}
                <span className={styles.attachmentName}>{item.file.name}</span>
                <button
                  type="button"
                  className={styles.attachmentRemove}
                  onClick={() => handleRemove(idx)}
                  title="移除附件"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── 文字输入区 ─────────────────────────────── */}
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

        {/* ── 底部操作栏 ─────────────────────────────── */}
        <div className={heroStyles.inputFooter}>
          {/* 回形针上传按钮 */}
          <button
            type="button"
            className={styles.attachBtn}
            onClick={handleAttachClick}
            title="上传图片或文件"
            disabled={submitting || !user}
          >
            <svg width="18" height="18" viewBox="0 0 17 17" fill="none">
              <path
                d="M14.5 8.5L8 15a4.243 4.243 0 01-6-6L9.5 1.5a2.828 2.828 0 014 4L6 13a1.414 1.414 0 01-2-2l6.5-6.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {/* 隐藏的原生 file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf,.doc,.docx,.txt"
            multiple
            className={styles.hiddenFileInput}
            onChange={handleFileChange}
          />

          {/* 发送按钮 */}
          <button
            type="button"
            className={`icon-btn-circle ${heroStyles.submitBtn}`}
            onClick={() => void onSubmit()}
            disabled={(!bottomPrompt.trim() && attachments.length === 0) || submitting || !user}
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

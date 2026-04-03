'use client';

import { useRef, type RefObject } from 'react';
import styles from './WorkspaceBottomBar.module.css';

type TFn = (key: string) => string;

/** 附件预览信息 */
export interface AttachmentItem {
  file: File;
  previewUrl: string;  // 本地 URL.createObjectURL 生成的预览地址
}

export interface WorkspaceBottomBarProps {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  bottomPrompt: string;
  setBottomPrompt: (v: string) => void;
  onSubmit: () => void | Promise<void>;
  isStreaming: boolean;
  submitting: boolean;
  onCancel: () => void;
  attachments: AttachmentItem[];
  onAttachmentsChange: (items: AttachmentItem[]) => void;
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
  attachments,
  onAttachmentsChange,
  t,
}: WorkspaceBottomBarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** 点击回形针按钮触发文件选择器 */
  const handleAttachClick = () => fileInputRef.current?.click();

  /** 用户选择文件后加入附件列表 */
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const newItems: AttachmentItem[] = files.map((f) => ({
      file: f,
      previewUrl: URL.createObjectURL(f),
    }));
    onAttachmentsChange([...attachments, ...newItems]);
    // NOTE: 清空 input value，允许重复选择同一文件
    e.target.value = '';
  };

  /** 移除单个附件，并释放 objectURL 内存 */
  const handleRemove = (index: number) => {
    URL.revokeObjectURL(attachments[index].previewUrl);
    onAttachmentsChange(attachments.filter((_, i) => i !== index));
  };

  const isImage = (file: File) => file.type.startsWith('image/');

  return (
    <div className={styles.bottomBar}>
      <div className={styles.bottomInner}>
        <div className={styles.bottomSpacer} />
        <div className={styles.bottomInputWrap}>
          {/* ── 附件预览区 ─────────────────────────────────── */}
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

          {/* ── 文字输入区 ─────────────────────────────────── */}
          <textarea
            ref={textareaRef}
            className={styles.bottomTextarea}
            placeholder={t('workspace.bottom.placeholder')}
            value={bottomPrompt}
            onChange={(e) => setBottomPrompt(e.target.value)}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void onSubmit();
              }
            }}
          />

          {/* ── 操作按钮区 ─────────────────────────────────── */}
          <div className={styles.bottomActions}>
            {isStreaming && (
              <button type="button" className={styles.cancelBtn} onClick={onCancel} title={t('workspace.cancel.title')}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="3" y="3" width="8" height="8" rx="1.5" fill="currentColor" />
                </svg>
                {t('workspace.cancel')}
              </button>
            )}

            {/* 上传附件按钮：回形针图标，紧靠发送按钮左侧 */}
            <button
              type="button"
              className={styles.attachBtn}
              onClick={handleAttachClick}
              title="上传图片或文件"
              disabled={submitting}
            >
              <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
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

            <button
              type="button"
              className={`icon-btn-circle ${styles.bottomSendBtn} ${isStreaming || submitting ? styles.bottomSendBtnActive : ''}`}
              onClick={() => void onSubmit()}
              disabled={(!bottomPrompt.trim() && attachments.length === 0) || submitting}
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

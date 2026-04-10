'use client';

/**
 * SharedHeroInput — 共享的 Hero 大输入框组件
 * 同时被 落地页 (app/page.tsx) 和 工作台空白态 (WorkspaceHeroEmpty.tsx) 引用。
 * 只负责 UI 呈现：附件预览 + LED 占位 + 回形针 + 发送按钮 + 智能体胶囊；业务逻辑保留在父级。
 */

import { useRef, type RefObject } from 'react';
import heroStyles from '@/components/landing/landingHero.module.css';
import styles from './SharedHeroInput.module.css';
import { AGENT_CONFIGS } from '@/data/agentConfigs';

type TFn = (key: string) => string;

/** NOTE: 输入框内展示的 5 个智能体胶囊（排除 consultant_review） */
const CAPSULE_AGENTS = AGENT_CONFIGS
  .filter((a) => a.id !== 'consultant_review')
  .sort((a, b) => a.index - b.index);

/** 胶囊所需的中英文映射 */
const CAPSULE_LABELS: Record<string, { zh: string; en: string }> = {
  consultant_plan: { zh: '品牌顾问', en: 'Agent' },
  market:          { zh: '市场研究', en: 'Agent' },
  strategy:        { zh: '品牌战略', en: 'Agent' },
  content:         { zh: '内容策划', en: 'Agent' },
  visual:          { zh: '美术指导', en: 'Agent' },
};

export interface AttachmentItem {
  file: File;
  previewUrl: string;
}

export interface SharedHeroInputProps {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  /** 当前输入框文字内容 */
  value: string;
  onChange: (v: string) => void;
  /** 点击输入框聚焦时的动画控制（可选，落地页 LED 轮播需要） */
  focused?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
  /** 发送按钮点击 */
  onSubmit: () => void | Promise<void>;
  submitting: boolean;
  disabled?: boolean;
  /** 附件列表 */
  attachments: AttachmentItem[];
  onAttachmentsChange: (items: AttachmentItem[]) => void;
  /** 占位内容（LED 轮播覆盖层），不传时显示普通 placeholder */
  ledNode?: React.ReactNode;
  placeholder?: string;
  t: TFn;
}

export function SharedHeroInput({
  textareaRef,
  value,
  onChange,
  focused,
  onFocus,
  onBlur,
  onSubmit,
  submitting,
  disabled = false,
  attachments,
  onAttachmentsChange,
  ledNode,
  placeholder,
  t,
}: SharedHeroInputProps) {
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

  const canSubmit = (value.trim().length > 0 || attachments.length > 0) && !submitting && !disabled;

  return (
    <div className={heroStyles.inputWrapper}>
      {/* ── 附件预览条（无分割线）────────────────────────── */}
      {attachments.length > 0 && (
        <div className={styles.attachmentsRow}>
          {attachments.map((item, idx) => (
            <div key={idx} className={styles.attachmentChip}>
              {item.file.type.startsWith('image/') ? (
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

      {/* ── 文字输入区（支持 LED 浮层） ─────────────────────── */}
      <div className={heroStyles.textareaWrap}>
        {/* LED 轮播占位层（落地页传入，工作台不传则显示默认 placeholder） */}
        {ledNode && !value && !focused && (
          <div className={heroStyles.ledOverlay} onClick={() => textareaRef.current?.focus()}>
            {ledNode}
          </div>
        )}
        <textarea
          ref={textareaRef}
          id="brand-prompt-input"
          className={heroStyles.textarea}
          placeholder={(!ledNode || focused) ? (placeholder ?? t('workspace.bottom.placeholder')) : ''}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void onSubmit();
            }
          }}
        />
      </div>

      {/* ── 底部操作栏：智能体胶囊 + 回形针 + 发送 ─────────────── */}
      <div className={heroStyles.inputFooter}>
        {/* 5 个智能体胶囊 */}
        <div className={styles.capsuleRow}>
          {CAPSULE_AGENTS.map((agent) => {
            const label = CAPSULE_LABELS[agent.id];
            return (
              <button
                key={agent.id}
                type="button"
                className={styles.capsule}
                title={label?.zh ?? agent.name}
              >
                <span className={styles.capsuleZh}>{label?.zh ?? agent.name}</span>
                <span className={styles.capsuleEn}>{label?.en ?? agent.charName}</span>
              </button>
            );
          })}
        </div>

        {/* 右侧操作区 */}
        <div className={styles.footerActions}>
          {/* 回形针上传按钮 */}
          <button
            type="button"
            className={styles.attachBtn}
            onClick={handleAttachClick}
            title="上传图片或文件"
            disabled={submitting || disabled}
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
            id="start-analysis-btn"
            type="button"
            className={`icon-btn-circle ${heroStyles.submitBtn}`}
            onClick={() => void onSubmit()}
            disabled={!canSubmit}
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

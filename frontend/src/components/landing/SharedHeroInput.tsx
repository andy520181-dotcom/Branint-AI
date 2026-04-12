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

/** 胶囊所需的中英文映射 + @提及名 */
const CAPSULE_LABELS: Record<string, { zh: string; en: string; mention: string }> = {
  consultant_plan: { zh: '品牌顾问', en: 'Agent', mention: 'Ogilvy' },
  market:          { zh: '市场研究', en: 'Agent', mention: 'Wacksman' },
  strategy:        { zh: '品牌战略', en: 'Agent', mention: 'Trout' },
  content:         { zh: '内容策划', en: 'Agent', mention: 'Lois' },
  visual:          { zh: '美术指导', en: 'Agent', mention: 'Scher' },
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

  /**
   * 胶囊点击处理：切换 @中文名提及
   * 点击 → 在输入框追加 @中文名 Agent（如 @品牌顾问 Agent）
   * 再次点击 → 移除该 @提及
   * 按点击顺序排列：第一个点击的排第一，第二个排第二
   */
  const handleCapsuleClick = (agentId: string) => {
    const label = CAPSULE_LABELS[agentId];
    if (!label) return;
    const mention = `@${label.zh} Agent`;

    // NOTE: 将输入内容拆为 「@提及前缀」 和 「用户正文」
    // 支持解析带 Agent 或不带 Agent 的旧格式
    const mentionRegex = /@[\u4e00-\u9fff]+(?:\s*Agent)?\s*/gi;
    const existingMentions: string[] = [];
    let match: RegExpExecArray | null;
    while ((match = mentionRegex.exec(value)) !== null) {
      existingMentions.push(match[0].trim());
    }
    const userText = value.replace(/@[\u4e00-\u9fff]+(?:\s*Agent)?\s*/gi, '').trim();

    const isActive = existingMentions.includes(mention);

    let newMentions: string[];
    if (isActive) {
      // 取消选中：从列表中移除
      newMentions = existingMentions.filter((m) => m !== mention);
    } else {
      // 新增选中：追加到列表末尾（保持点击顺序）
      newMentions = [...existingMentions, mention];
    }

    // 重新拼接：@提及 + 用户正文
    const mentionStr = newMentions.length > 0 ? newMentions.join(' ') + ' ' : '';
    onChange(mentionStr + userText);

    textareaRef.current?.focus();
  };

  /**
   * 判断某个胶囊是否处于选中状态（输入框中包含其 @中文名 Agent）
   */
  const isCapsuleActive = (agentId: string): boolean => {
    const label = CAPSULE_LABELS[agentId];
    if (!label) return false;
    return value.includes(`@${label.zh} Agent`);
  };

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
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
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
            const active = isCapsuleActive(agent.id);
            return (
              <button
                key={agent.id}
                type="button"
                className={`${styles.capsule} ${active ? styles.capsuleActive : ''}`}
                title={label?.zh ?? agent.name}
                onClick={() => handleCapsuleClick(agent.id)}
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

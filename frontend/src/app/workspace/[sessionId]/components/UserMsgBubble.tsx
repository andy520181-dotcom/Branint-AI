import React from 'react';
import styles from './WorkspaceFeed.module.css';

export interface UserMsgBubbleProps {
  prompt: string;
  avatarDataUrl: string | null;
}

/** 
 * 用户消息气泡（头像 + 文本）
 * 历史轮次和当前轮次复用
 */
export function UserMsgBubble({ prompt, avatarDataUrl }: UserMsgBubbleProps) {
  return (
    <div className={styles.userMsgRow}>
      <div className={styles.userBubble}>{prompt}</div>
      <div className={styles.userAvatarWrap}>
        {avatarDataUrl ? (
          <img src={avatarDataUrl} alt="avatar" className={styles.userAvatarImg} />
        ) : (
          <svg
            className={styles.userAvatarFallback}
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        )}
      </div>
    </div>
  );
}

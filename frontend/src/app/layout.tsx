import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { LocaleProvider } from '@/contexts/LocaleContext';
import ThemeInit from '@/components/ThemeInit';

export const metadata: Metadata = {
  title: 'Brandclaw AI — 品牌咨询智能体平台',
  description: '由 AI 驱动的专业品牌咨询平台，通过市场研究、品牌战略、内容策划、视觉设计四大智能体，自动生成完整品牌战略报告。',
  keywords: '品牌咨询, AI智能体, 品牌战略, 市场研究, 内容策划',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <ThemeInit />
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}

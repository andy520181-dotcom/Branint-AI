import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { LocaleProvider } from '@/contexts/LocaleContext';
import ThemeInit from '@/components/ThemeInit';

export const metadata: Metadata = {
  title: 'Brandclaw AI — 全球首个AI品牌咨询智能体',
  description: '由 AI 驱动的专业品牌咨询平台，通过市场研究、品牌战略、内容策划、美术指导四大智能体，自动生成完整品牌战略报告。',
  keywords: '品牌咨询, AI智能体, 品牌战略, 市场研究, 内容策划',
  icons: { icon: '/logo.png', apple: '/logo.png' },
};

/**
 * 首屏关键状态同步脚本，在 <head> 内以阻塞方式执行（HTML 解析阶段，早于首次绘制）。
 * 通过 data 属性 + globals.css 规则，在浏览器首次绘制前就确定正确的视觉状态：
 * - data-theme：暗色/亮色模式，防止先亮后暗
 * - data-splash-done：启动页已看过，防止刷新闪现
 * - data-auth：用户已登录，防止骨架 → 头像闪跳
 *
 * HACK: dangerouslySetInnerHTML 会触发 React 开发模式警告（"Scripts inside React
 * components are never executed when rendering on the client"），但 SSR 阶段正常注入
 * 并在浏览器解析 HTML 时同步执行，功能不受影响。next/script beforeInteractive 放在
 * <body> 中可能在首帧绘制之后才执行，时序不够可靠，因此此处刻意使用 <head> 内联脚本。
 */
const BOOTSTRAP_SCRIPT = `(function(){try{var v=localStorage.getItem('woloong_theme');var p=(v==='dark'||v==='light'||v==='system')?v:'light';var d=p==='dark'||(p==='system'&&window.matchMedia('(prefers-color-scheme:dark)').matches);document.documentElement.setAttribute('data-theme',d?'dark':'light');document.documentElement.setAttribute('data-theme-pref',p)}catch(e){}try{if(sessionStorage.getItem('bc_splash_seen')==='1'){document.documentElement.setAttribute('data-splash-done','1')}}catch(e){}try{document.documentElement.setAttribute('data-auth',localStorage.getItem('woloong_user')?'1':'0')}catch(e){document.documentElement.setAttribute('data-auth','0')}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* NOTE: 阻塞脚本必须放在 <head> 中，确保在浏览器首次绘制前同步执行 */}
        <script dangerouslySetInnerHTML={{ __html: BOOTSTRAP_SCRIPT }} />
        {/* NOTE: 预加载落地页 Agent 缩略图，与 img src 一致才能命中缓存 */}
        <link rel="preload" as="image" href="/agents/thumb/ogilvy.png" />
        <link rel="preload" as="image" href="/agents/thumb/wacksman.png" />
        <link rel="preload" as="image" href="/agents/thumb/trout.png" />
        <link rel="preload" as="image" href="/agents/thumb/lois.png" />
        <link rel="preload" as="image" href="/agents/thumb/scher.png" />
      </head>
      <body>
        <ThemeInit />
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}

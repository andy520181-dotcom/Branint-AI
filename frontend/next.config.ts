import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // NOTE: 允许通过 127.0.0.1 访问 Next.js 开发资源（HMR/JS chunks）
  // 若使用 localhost 访问则不需要此配置
  allowedDevOrigins: ["127.0.0.1"],
  async redirects() {
    return [
      {
        source: "/report/:sessionId",
        destination: "/workspace/:sessionId",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;

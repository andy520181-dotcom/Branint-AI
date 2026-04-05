# Branin AI · Web

Next.js 前端：Branin AI 品牌咨询智能体（落地页、工作台、历史与账户等）。

## 本地开发

```bash
npm install
npm run dev
```

浏览器打开 [http://localhost:3000](http://localhost:3000)。默认通过 `NEXT_PUBLIC_API_URL`（未设置时为 `http://localhost:8000`）连接后端 API。

## 脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 开发服务器（Turbopack） |
| `npm run build` | 生产构建 |
| `npm run start` | 启动生产构建产物 |
| `npm run lint` | ESLint |

## 技术栈

Next.js 16、React 19、TypeScript、Zustand、react-markdown 等。详见 `package.json`。

# Cloudflare Workers Demo

这个目录用于把客户演示页部署到 Cloudflare Workers，拿到一个长期可访问的公网 HTTPS 地址。

## 目录说明

- `public/index.html`: 客户演示页静态文件
- `src/index.ts`: Worker 入口，负责健康检查和静态资源分发
- `wrangler.jsonc`: Cloudflare Workers 配置

## 本地命令

```bash
cd cloudflare-demo
npx wrangler dev
npx wrangler deploy
```

## 访问路径

- `/`：客户演示页
- `/health`：健康检查 JSON

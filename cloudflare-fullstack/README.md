# Cloudflare Fullstack Deploy

这个目录用于把现有整站部署到 Cloudflare：

- Worker 作为公网入口
- Cloudflare Container 运行现有 FastAPI 后端
- 后端继续直接服务 React 构建产物

## 部署前

当前方案依赖 `Cloudflare Containers`。根据 Cloudflare 官方文档，Containers 目前处于 Beta，且仅对 `Workers Paid plan` 开放。

如果执行 `wrangler deploy` 时在 `/accounts/<ACCOUNT_ID>/containers/*` 返回 `401 Unauthorized`，通常表示当前账号尚未开通 Containers 能力，或者账号侧尚未具备该 Beta 访问权限。

请先确保 `backend/static` 已包含最新前端构建文件。

```bash
cd ../frontend
npm run build
cd ..
rsync -a --delete frontend/build/ backend/static/
```

## 部署

```bash
cd cloudflare-fullstack
npm install
npm run whoami
npm run deploy
```

## 说明

- 当前配置默认关闭搜索模块，减少容器镜像体积和不必要依赖
- 容器采用单实例 `singleton` 模式，适合演示和轻量访问
- 配置文件与上传文件位于容器临时磁盘中，容器休眠或重建后会丢失
- 若 Cloudflare 账号尚未具备 Containers 权限，整站无法以当前架构发布到 Workers 域名

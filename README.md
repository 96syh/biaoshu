# 华正 ai 标书系统

华正 ai 标书系统是一个面向招投标文件编制的本地 Web 工作台。系统以招标文件为事实源，把“上传解析、标准解析报告、响应矩阵、目录生成、正文生成、合规审校、Word 导出”串成一条可追踪流程，帮助用户把招标要求转成可检查、可继续编辑、可人工复核的投标文件草稿。

当前实现已经统一收敛到 **LiteLLM Proxy + OpenAI Chat Completions 兼容接口**。本应用只保存和调用 LiteLLM 的 Base URL、模型名和可选 API Key；不同模型供应商、内网模型、本地模型和云端模型由 LiteLLM 负责适配。

## 当前定位

- 面向对象：投标技术人员、方案编制人员、标书审核人员。
- 核心目标：降低招标文件阅读遗漏、目录与评分项不对齐、正文重复撰写、导出前合规检查不足等问题。
- 使用方式：本地启动前后端，浏览器中上传招标文件，配置 LiteLLM 后生成解析报告、目录、正文和审校报告。
- 输出边界：系统生成的是投标文件草稿和审校建议，最终实质性条款、签章、报价、暗标、证明材料和 Word 排版仍必须人工复核。

## 核心能力

- 招标文件上传：支持 PDF、DOCX，单文件大小限制 500MB；暂不支持 `.doc`，需另存为 `.docx` 后上传。
- 文档解析：默认使用内置 `pdfplumber` / `docx2python` / `PyPDF2` 路径；需要版面级 Markdown 时可按需启用本机 MinerU。
- 标准解析报告：提取项目基础信息、投标文件组成、评分项、资格审查、形式评审、响应性要求、实质性条款、废标风险、材料清单、固定格式、签章要求、报价规则、卷册规则和暗标规则。
- 响应矩阵：把评分项、资格项、形式项、响应性条款、废标风险、固定格式、签章、报价规则和证明材料映射到目录、正文和审校流程。
- 目录生成：基于标准解析报告、响应矩阵和招标文件编制要求生成正式目录，支持技术标、服务方案、施工组织、供货方案、商务卷、资格卷、报价卷和完整标等模式。
- 正文生成：按目录叶子节点逐章生成正文，支持 SSE 流式写入、暂停、继续、停止和章节重生成。
- 样例风格剖面：可上传成熟投标文件样例，提取结构、表达风格和常见内容块，作为后续目录和正文生成参考。
- 图表与素材规划：根据目录、解析报告和企业材料，规划表格、图片、承诺书、附件、证据链等内容块。
- 合规审校：导出前检查覆盖率、阻塞项、警告项、固定格式、签章、报价隔离、暗标泄露、证据链、页码占位、疑似虚构和重复内容，并生成修订计划。
- Word 导出：将正文和目录导出为 DOCX，后端使用 `python-docx` 生成基础 Word 文档。
- 草稿与历史：后端 SQLite 项目库保存当前草稿、章节正文和历史记录；前端会合并流式正文更新并延迟写入，减少大草稿生成时的重复写库压力。

## 工作流程

1. 配置模型：在“模型配置”中填写 LiteLLM Base URL、模型名和可选 API Key，验证端点并同步模型列表。
2. 上传文件：上传 PDF 或 DOCX 招标文件，后端解析出全文文本和解析器元信息。
3. 标准解析：调用模型生成结构化 `AnalysisReport`，并在需要时生成 `ResponseMatrix`。
4. 选择模式：选择技术标、服务方案、施工组织、供货方案、商务卷、资格卷、报价卷或完整标，决定目录、正文和审校的范围。
5. 生成目录：根据解析报告、响应矩阵、投标文件组成和可选样例风格生成 `OutlineItem` 树。
6. 生成正文：选择单章或批量生成正文，章节生成时会传入父章节、同级章节、已生成摘要、材料清单和风险映射。
7. 执行审校：对完整草稿执行覆盖性、缺料、废标风险、固定格式、报价、暗标和证据链检查。
8. 导出 Word：导出 DOCX 后继续在 Word 中处理最终页码、目录、格式、签章和人工复核。

## 页面说明

系统左侧导航包含以下页面：

- 上传文件：选择招标文件，查看项目基础信息、材料缺失提示和解析入口。
- 开始解析：抽取项目概况、评分办法、资格审查、实质性要求、投标文件组成和材料清单。
- 生成目录：查看目录结构、评分项映射、风险等级、材料关联和章节编辑入口。
- 生成正文：以 Word 类文档视图生成和预览正文，左侧目录可跳转到对应章节。
- 执行审校：查看覆盖率、阻塞问题、警告问题、提示信息和修订计划。
- 模型配置：配置 LiteLLM Proxy 接入信息、验证端点、同步模型列表。

## 模型接入

模型调用链路固定为：

```text
用户配置的模型服务 / 本地模型 / 云端模型
        ↓
LiteLLM Proxy
        ↓
华正 ai 标书系统后端
        ↓
OpenAI Chat Completions 兼容调用
```

配置项：

- LiteLLM Base URL：LiteLLM Proxy 的 OpenAI 兼容地址，例如 `http://localhost:4000/v1` 或 `https://example.com/v1`。
- 模型名：从 `/models` 同步后选择，或手动输入模型 ID。
- API Key：LiteLLM master key 或 virtual key，可为空，取决于 LiteLLM 端配置。

真实 Base URL、API Key 和模型内部名称只应保存在本机配置、运行环境或 LiteLLM 私有配置中，不应提交到源码、文档或日志。`docs/local-model-api.md` 仅保留 `${MODEL_BASE_URL}`、`${MODEL_API_KEY}`、`${MODEL_ID}` 形式的占位示例。

端点验证失败时优先检查：

- 后端服务是否已启动。
- LiteLLM Proxy 是否已启动并能访问。
- Base URL 是否包含正确的 `/v1` 路径。
- API Key 是否能被 LiteLLM 接受。
- 模型名是否存在于 LiteLLM 返回的模型列表中。

## 技术架构

```text
yibiao-simple/
  frontend/                 React + TypeScript 前端工作台
  backend/                  FastAPI 后端
  backend/app/main.py       FastAPI 应用入口、路由注册、静态前端托管
  backend/app/routers/      配置、文档、目录、正文、扩写 API
  backend/app/services/     文件解析、模型调用、搜索服务
  backend/app/models/       Pydantic 请求/响应/业务数据结构
  backend/app/utils/        Prompt、配置、SSE、JSON 校验、目录工具
  docs/                     模型接入和 Prompt 工作流补充文档
  screenshots/              截图资源
  cloudflare-demo/          Cloudflare 静态演示样例
  cloudflare-fullstack/     Cloudflare 全栈部署实验样例
```

主要技术栈：

- 前端：React、TypeScript、React Markdown、Heroicons、File Saver、Tailwind CSS。
- 后端：FastAPI、Pydantic、OpenAI SDK、python-docx、pdfplumber、PyMuPDF、docx2python。
- 模型网关：LiteLLM Proxy。
- 文档解析：默认内置解析器，可选 MinerU。
- 文档导出：`python-docx` 生成 DOCX。
- 实时输出：SSE 流式返回。

## 后端 API 分层

- `/api/config/*`：保存配置、加载配置、同步模型、验证 LiteLLM 端点。
- `/api/document/upload`：上传招标文件并提取文本。
- `/api/document/analyze-stream`：早期项目概述/技术评分流式分析接口，仍保留兼容。
- `/api/document/analyze-report-stream`：生成结构化标准解析报告。
- `/api/document/reference-style-upload`：上传成熟投标样例并生成风格剖面。
- `/api/document/document-blocks-plan-stream`：生成图表、表格、图片、承诺书和附件规划。
- `/api/outline/generate-stream`：生成目录和目录预览进度。
- `/api/content/generate-chapter-stream`：生成单章节正文。
- `/api/document/review-compliance-stream`：执行导出前合规审校。
- `/api/document/consistency-revision-stream`：生成全文一致性修订报告。
- `/api/document/export-word`：导出 Word 文档。
- `/api/expand/upload`：旧扩写兼容接口，默认不注册；需设置 `ENABLE_LEGACY_EXPAND_ROUTER=1`。

可选搜索接口 `/api/search/*` 默认不注册；需安装 `backend/requirements-optional.txt` 并设置 `ENABLE_SEARCH_ROUTER=1`。

## 重要数据结构

当前标书生成链路围绕以下结构运行：

- `AnalysisReport`：标准解析报告，是目录、正文和审校阶段的主要事实源。
- `ResponseMatrix`：响应矩阵，用于追踪评分项、审查项、材料项、风险项与目录章节的映射。
- `OutlineItem`：目录节点，保存章节层级、章节类型、风险/材料/评分项映射、预期内容块和正文内容。
- `ChapterContentRequest`：章节正文生成请求，包含当前章节、父章节、同级章节、解析报告、响应矩阵、已生成摘要和企业材料上下文。
- `ReviewReport`：导出前审校报告。
- `RevisionPlan`：审校后的修订动作清单。

正文和审校阶段不重新解析招标文件，而是复用 `AnalysisReport`、`ResponseMatrix`、目录映射、样例风格剖面、图表素材规划和企业材料上下文。

## 可选能力与产物目录

- 可选搜索路由位于 `backend/app/optional/search.py`，默认不参与 FastAPI 主流程。
- 旧扩写路由位于 `backend/app/optional/expand.py`，仅保留兼容。
- MCP DuckDuckGo 示例位于 `backend/optional/mcp/`，手动运行，不被后端默认导入。
- 构建包、发布包、历史案例库、生成素材和临时验收文件统一放入 `artifacts/`，默认由 `.gitignore` 忽略。
- 运行态路径可通过 `YIBIAO_PROJECT_DB_PATH`、`YIBIAO_HISTORY_CASE_DB_PATH`、`YIBIAO_GENERATED_ASSET_DIR`、`YIBIAO_FRONTEND_STATIC_DIR` 覆盖。

## 本地开发

### 一键启动

macOS/Linux 可在项目根目录执行：

```bash
./start-dev.sh
```

脚本默认启动：

```text
后端：http://127.0.0.1:8000
前端：http://127.0.0.1:3001
前端 API：REACT_APP_API_URL=http://127.0.0.1:8000
```

在 macOS 中也可以双击 `start-dev.command` 启动。关闭脚本窗口或按 `Ctrl+C` 会停止本脚本启动的前后端进程。

首次运行时脚本会自动安装缺失的后端或前端依赖。若只想检查环境、不允许自动安装依赖，可执行：

```bash
AUTO_INSTALL=0 ./start-dev.sh
```

### 手动启动后端

```bash
cd backend
HOST=127.0.0.1 PORT=8000 WORKERS=1 python run.py
```

后端默认地址：

```text
http://127.0.0.1:8000
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

### 手动启动前端

```bash
cd frontend
PORT=3001 npm run start
```

前端默认地址：

```text
http://localhost:3001
```

### 构建前端

```bash
cd frontend
npm run build
```

### 前端验证

```bash
cd frontend
./node_modules/.bin/tsc --noEmit --pretty false
npm run test -- --watchAll=false
npm run build
```

## 后端配置

后端核心配置位于：

```text
backend/app/config.py
```

当前关键配置：

- 默认端口：`8000`
- 上传目录：`backend/uploads`
- 最大上传文件：`500MB`
- CORS：默认允许本地 3000-3004、3010、8000、8010 端口

模型配置由应用界面写入用户目录：

```text
~/.ai_write_helper/user_config.json
```

不要把真实 API Key 写入源码、文档或日志。

### 文档解析器选择

上传解析默认不接入 MinerU，直接使用内置 `pdfplumber` / `docx2python` / `PyPDF2` 解析器。需要更接近版面结构的 Markdown 输出时，可手动启用本机 `mineru` CLI：

- `legacy`：默认模式，只用内置解析器，不调用 MinerU。
- `auto`：自动用 MinerU，失败后回退到内置解析器。
- `mineru` / `mineru_strict`：使用 MinerU。
- `mineru_strict` 模式下 MinerU 失败会直接报错，不再回退。

可选环境变量：

```bash
# legacy：默认，只用内置解析器；auto：自动用 MinerU，失败回退；
# mineru / mineru_strict：使用 MinerU，mineru_strict 失败则直接报错
export YIBIAO_DOCUMENT_PARSER=legacy

# MinerU CLI 路径，默认从 PATH 查找 mineru
export YIBIAO_MINERU_BIN=mineru

# auto：CUDA -> MPS -> CPU；也可手动指定 cuda / mps / cpu
export YIBIAO_MINERU_DEVICE=auto

# MinerU 后端，默认 pipeline；如需 VLM 可按 MinerU 文档调整
export YIBIAO_MINERU_BACKEND=pipeline

# 中文文档默认 ch
export YIBIAO_MINERU_LANG=ch

# 单文件解析超时，默认 900 秒
export YIBIAO_MINERU_TIMEOUT=900

# 默认优先速度：不在上传阶段额外渲染 DOCX 页图/HTML 预览，不提取图片并上传外部图床
export YIBIAO_ENABLE_SOURCE_PREVIEW_PAGES=0
export YIBIAO_ENABLE_DOCX_HTML_PREVIEW=0
export YIBIAO_UPLOAD_EXTRACTED_IMAGES=0

# 目录生成默认限制并发，避免本地模型或 LiteLLM 过载；图表素材规划改为前端手动触发
export YIBIAO_OUTLINE_CONCURRENCY=2
export YIBIAO_AUTO_DOCUMENT_BLOCKS_PLAN=0
```

macOS 上若安装了支持 MPS 的 MinerU/PyTorch，`YIBIAO_MINERU_DEVICE=auto` 会优先选择 MPS；Linux 上检测到 `nvidia-smi` 时会优先选择 CUDA。

### 本地安全验证模式

如果只想验证端到端流程而不把招标文件发给模型，可设置：

```bash
# 默认关闭生成链路兜底。模型失败、JSON 不完整或超时时会直接报错停止。
export YIBIAO_ENABLE_GENERATION_FALLBACKS=0

# 仅在明确接受兜底结果时打开；打开后本地安全验证兜底才会生效。
export YIBIAO_ENABLE_GENERATION_FALLBACKS=1
export YIBIAO_FORCE_LOCAL_FALLBACK=1
```

`YIBIAO_FORCE_LOCAL_FALLBACK=1` 只有在 `YIBIAO_ENABLE_GENERATION_FALLBACKS=1` 时才生效。该模式会启用本地兜底解析、兜底目录、兜底正文和兜底审校，仅适合 smoke test，不代表真实生成质量。

## Docker 运行

项目保留 Dockerfile，可按 amd64 构建：

```bash
docker buildx build --platform linux/amd64 -t huazheng-ai:amd64 . --load
```

运行：

```bash
docker run --rm -p 8000:8000 \
  -v huazheng-ai-config:/home/app/.ai_write_helper \
  -v huazheng-ai-uploads:/app/backend/uploads \
  huazheng-ai:amd64
```

访问：

```text
http://localhost:8000
```

## 部署与数据边界

- 应用默认是本地工作台，不自带用户体系、权限体系和团队协作。
- 模型配置保存到本机用户目录，草稿历史保存在后端 SQLite 项目库。
- 招标文件上传后会被后端临时保存，解析完成后会清理临时文件。
- 模型理解阶段会把招标文本发送到用户配置的 LiteLLM 后端；是否外传取决于 LiteLLM 后端接入的是本地模型、内网模型还是云端模型。
- 文件解析默认不接入 MinerU；如果手动启用 MinerU 远端 API，需要自行确认数据边界。
- 生成结果必须人工复核，不应直接作为最终投标文件提交。

## 当前限制

- 企业资料解析还不是独立模块，目前通过 `enterprise_materials` 和 `missing_materials` 传递已提供材料和待补资料。
- 大项目草稿包含原文、目录、解析报告和正文内容，仍需关注 SQLite 项目库体积、磁盘空间和长时间生成过程中的保存失败提示。
- 生成内容依赖模型质量，导出前必须人工复核实质性条款、签章、报价、暗标和证明材料。
- Word 导出提供基础 DOCX 结构，最终页码、目录、版式、图表细节和盖章位置仍建议在 Word 中人工确认。
- 前端主工作台逻辑目前集中在 `frontend/src/App.tsx`，后续大规模扩展时建议拆分组件和业务 hooks。

## 相关文档

- [LiteLLM Proxy 统一模型网关接入说明](./docs/litellm-proxy.md)
- [本地大模型调用 API 文档](./docs/local-model-api.md)
- [Prompt 工作流说明](./docs/prompt-workflow.md)
- [标书 Prompt 规则替换目标](./docs/biaoshu_prompt_replacement_target_section.md)

## 许可证

本项目基于 [MIT License](./LICENSE) 发布。

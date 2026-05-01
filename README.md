# 华正ai标书系统

华正ai标书系统是一个面向招投标文件编制的本地 Web 应用。系统以招标文件为事实源，围绕“上传解析、标准解析报告、响应矩阵、目录生成、正文生成、合规审校、Word 导出”的流程，帮助用户把招标要求转成可检查、可追踪、可继续编辑的投标文件草稿。

当前版本统一通过 LiteLLM Proxy 接入模型，由 LiteLLM 负责适配不同模型服务，本应用始终按 OpenAI Chat Completions 格式调用。

## 核心能力

- 招标文件上传：支持 PDF、DOCX，文件大小限制在 500MB 以下。
- 标准解析报告：提取项目基础信息、评分项、审查项、实质性条款、废标风险、材料清单、固定格式、签章要求、报价规则、证据链、卷册规则和暗标规则。
- 响应矩阵：把评分项、资格项、形式项、响应性条款、废标风险、固定格式、签章、报价规则和证明材料映射到后续目录、正文和审校流程。
- 目录生成：根据解析报告和响应矩阵生成正式投标文件目录，支持完整标书和技术标两种生成模式。
- 正文生成：左侧目录类似 Word 导航，点击章节后右侧跳转到对应正文位置；生成过程支持流式写入，能看到文字逐步出现。
- 生成控制：正文生成支持暂停、继续和停止，切换页面后仍保留当前生成进度。
- 合规审校：导出前检查覆盖率、阻塞项、警告项、固定格式、签章、报价隔离、暗标泄露、证据链、页码占位和疑似虚构风险，并给出修订计划。
- Word 导出：生成的正文可导出为 DOCX，并在支持的浏览器中选择本地保存位置。
- 历史记录：本地保存生成历史和草稿，避免做一半中断后丢失进度。
- 模型配置：在界面中配置 LiteLLM Base URL、模型名和 API Key，支持验证端点、同步模型列表和保存配置。

## 工作流程

1. 上传文件：上传 PDF 或 DOCX 招标文件。
2. 开始解析：生成项目基础信息、标准解析报告和响应矩阵。
3. 生成目录：把评分项、审查项、风险项、材料项映射到目录章节。
4. 生成正文：选择章节生成，或批量生成正文内容。
5. 执行审校：检查正文是否覆盖招标要求，并输出阻塞项、警告项和修订计划。
6. 导出 Word：导出 DOCX 到本地文件夹，继续在 Word 中排版和人工复核。

## 页面说明

系统左侧导航包含以下页面：

- 上传文件：选择招标文件，查看项目基础信息和材料缺失提示。
- 开始解析：抽取项目概况、评分办法、资格审查、实质性要求和材料清单。
- 生成目录：查看目录结构、评分项映射、风险等级和材料关联。
- 生成正文：以 Word 类文档视图生成和预览正文，左侧目录可跳转到对应章节。
- 执行审校：查看覆盖率、阻塞问题、警告问题、提示信息和修订计划。
- 模型配置：配置 LiteLLM Proxy 接入信息。

## 模型接入

本项目的模型调用链路固定为：

```text
用户配置的模型服务 -> LiteLLM Proxy -> 本应用 -> OpenAI Chat Completions 格式调用
```

配置项说明：

- LiteLLM Base URL：LiteLLM Proxy 的 OpenAI 兼容地址，例如 `https://example.com/v1`。
- 模型名：从 `/models` 同步后选择，或手动输入模型 ID。
- API Key：LiteLLM master key 或 virtual key，可为空，取决于 LiteLLM 端配置。

如果端点验证失败，优先确认：

- 后端服务是否已启动。
- LiteLLM Base URL 是否是完整服务地址。
- API Key 是否可用于该 LiteLLM 服务。
- 模型名是否存在于 LiteLLM 返回的模型列表中。

## 技术架构

```text
frontend/                React + TypeScript 前端
backend/                 FastAPI 后端
backend/app/routers/     API 路由
backend/app/services/    文件处理、模型调用、生成逻辑
backend/app/models/      Pydantic 数据结构
backend/app/utils/       Prompt、配置、SSE、目录工具
docs/                    补充文档
screenshots/             截图资源
```

主要技术栈：

- 前端：React、TypeScript、React Markdown、Heroicons、File Saver。
- 后端：FastAPI、Pydantic、OpenAI SDK、python-docx、pdfplumber、PyMuPDF、docx2python。
- 模型网关：LiteLLM Proxy。
- 文档导出：python-docx 生成 DOCX。
- 实时输出：SSE 流式返回。

## 本地开发

### 一键启动

macOS/Linux 可在项目根目录执行：

```bash
./start-dev.sh
```

脚本会固定启动：

```text
后端：http://127.0.0.1:8000
前端：http://127.0.0.1:3001
前端 API：REACT_APP_API_URL=http://127.0.0.1:8000
```

在 macOS 中也可以双击 `start-dev.command` 启动。关闭脚本窗口或按 `Ctrl+C` 会停止本脚本启动的前后端进程。

### 1. 启动后端

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

### 2. 启动前端

```bash
cd frontend
PORT=3001 npm run start
```

前端默认地址：

```text
http://localhost:3001
```

### 3. 构建前端

```bash
cd frontend
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
- CORS：默认允许本地 3000-3004 和 8000 端口

模型配置由应用界面写入本地配置文件，不建议把真实 API Key 写入源码。

### 本地 MinerU 文档解析

上传解析默认会自动探测本机是否有 `mineru` CLI：

- 有 MinerU：优先用本地 MinerU 将 PDF/DOCX 解析为 Markdown，再进入标准解析、目录和正文流程。
- 没有 MinerU 或解析失败：自动回退到内置 `pdfplumber` / `docx2python` 解析器。
- 不调用 MinerU 云端 API；模型理解仍通过 LiteLLM 配置的模型服务完成。

可选环境变量：

```bash
# auto：自动用 MinerU，失败回退；legacy：只用内置解析器；
# mineru_strict：MinerU 失败则直接报错
export YIBIAO_DOCUMENT_PARSER=auto

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
```

macOS 上若安装了支持 MPS 的 MinerU/PyTorch，`YIBIAO_MINERU_DEVICE=auto` 会优先选择 MPS；Linux 上检测到 `nvidia-smi` 时会优先选择 CUDA。

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

## 重要数据结构

当前标书生成链路围绕以下结构运行：

- `AnalysisReport`：标准解析报告，是后续阶段的事实源。
- `ResponseMatrix`：响应矩阵，用于确保评分项、审查项、材料项和风险项可追踪。
- `OutlineItem`：目录节点，保存章节层级、映射 ID 和正文内容。
- `ReviewReport`：导出前审校报告。
- `RevisionPlan`：审校后的修订计划。

正文和审校阶段不重新解析招标文件，只复用 `AnalysisReport`、`ResponseMatrix`、目录映射和企业材料上下文。

## 当前限制

- 企业资料解析还不是独立模块，目前通过 `enterprise_materials` 和 `missing_materials` 传递已提供材料和待补资料。
- 生成内容仍依赖模型质量，导出前必须人工复核实质性条款、签章、报价、暗标和证明材料。
- Word 导出提供基础 DOCX 结构，最终页码、目录、版式和盖章位置仍建议在 Word 中人工确认。

## 相关文档

- [LiteLLM Proxy 统一模型网关接入说明](./docs/litellm-proxy.md)
- [本地大模型调用 API 文档](./docs/local-model-api.md)

## 许可证

本项目基于 [MIT License](./LICENSE) 发布。

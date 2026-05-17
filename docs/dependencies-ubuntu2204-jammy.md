# Ubuntu 22.04 Jammy 依赖库说明

本文档面向 Ubuntu 22.04 LTS（Jammy Jellyfish）部署或本地运行 `yibiao-simple`。如果部署目标固定为 Jammy，按本文档准备系统依赖、Python 依赖和前端依赖。

## 版本基线

| 类型 | 推荐版本 | 说明 |
| --- | --- | --- |
| Ubuntu | 22.04 LTS / jammy | 本文档目标系统 |
| Python | 3.11 | Jammy 默认 Python 3.10，建议单独安装 3.11 |
| Node.js | 18 LTS | 前端 `react-scripts@5`、React 19 依赖 Node 18 更稳 |
| npm | 9+ | 随 Node 18 安装即可 |

## 最小系统依赖

用于后端 FastAPI、文档解析、Word 导出、前端构建的基础依赖：

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  git \
  build-essential \
  pkg-config \
  python3-venv \
  python3-dev \
  libffi-dev \
  libssl-dev \
  zlib1g-dev \
  libjpeg-dev \
  libpng-dev \
  libfreetype6-dev \
  libxml2 \
  libxslt1.1 \
  fontconfig \
  fonts-noto-cjk \
  fonts-wqy-zenhei
```

说明：

- `fonts-noto-cjk`、`fonts-wqy-zenhei` 用于 Linux 下中文显示、导出和预览，避免中文乱码或缺字。
- `libjpeg-dev`、`libpng-dev`、`libfreetype6-dev` 主要服务 `Pillow`、PDF/图片处理相关库。
- `build-essential`、`python3-dev` 用于缺少预编译 wheel 时本地编译 Python 依赖。

## 可选系统依赖

默认主流程不强制依赖这些工具。只有开启对应能力时安装：

```bash
sudo apt-get install -y \
  libreoffice \
  poppler-utils \
  tesseract-ocr \
  tesseract-ocr-chi-sim \
  tesseract-ocr-eng
```

| 依赖 | 用途 | 默认是否必需 |
| --- | --- | --- |
| `libreoffice` | DOCX/PPT/PDF 转换、页面预览增强 | 否 |
| `poppler-utils` | PDF 页面渲染、文本/图片辅助处理 | 否 |
| `tesseract-ocr*` | OCR 识别 | 否 |
| MinerU CLI | 版面级 Markdown 解析 | 否，默认 `YIBIAO_DOCUMENT_PARSER=legacy` |

## Python 3.11

Jammy 默认 Python 是 3.10。推荐使用 Python 3.11，方式二选一。

### 方式 A：系统 Python 3.11

```bash
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
```

创建后端虚拟环境：

```bash
cd /path/to/yibiao-simple
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
```

### 方式 B：Conda / Miniconda

```bash
conda create -n yibiao-simple python=3.11 -y
conda activate yibiao-simple
python -m pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
```

## Node.js 18

Jammy 官方源里的 Node 版本通常偏旧。建议使用 NodeSource 或 nvm 安装 Node 18。

### NodeSource

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v
npm -v
```

### nvm

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
```

安装前端依赖：

```bash
cd /path/to/yibiao-simple/frontend
npm ci
```

## 项目依赖清单

后端主依赖文件：

```text
backend/requirements.txt
```

核心库：

| 类别 | Python 包 |
| --- | --- |
| Web API | `fastapi`、`uvicorn[standard]`、`python-multipart` |
| 模型调用 | `openai` |
| 配置/数据模型 | `pydantic`、`pydantic-settings`、`python-dotenv` |
| Word 导出/解析 | `python-docx`、`docx2python` |
| PDF/文档解析 | `pdfplumber`、`PyPDF2`、`pymupdf` |
| 图片处理 | `Pillow` |
| 异步/HTTP | `aiofiles`、`aiohttp`、`requests` |

后端可选依赖文件：

```text
backend/requirements-optional.txt
```

只在开启搜索、MCP 或浏览器抓取增强能力时安装：

```bash
pip install -r backend/requirements-optional.txt
```

前端依赖文件：

```text
frontend/package.json
frontend/package-lock.json
```

核心库：

| 类别 | npm 包 |
| --- | --- |
| React 应用 | `react`、`react-dom`、`react-scripts` |
| UI/图标 | `@headlessui/react`、`@heroicons/react`、`tailwindcss` |
| API/文件 | `axios`、`file-saver` |
| Markdown/代码高亮 | `react-markdown`、`rehype-highlight`、`prism-react-renderer` |
| Word 前端辅助 | `docx`、`html-to-docx` |
| 测试/类型 | `@testing-library/*`、`typescript`、`@types/*` |

## 启动与验证

后端：

```bash
cd /path/to/yibiao-simple/backend
HOST=127.0.0.1 PORT=8000 python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

前端：

```bash
cd /path/to/yibiao-simple/frontend
REACT_APP_API_URL=http://127.0.0.1:8000 PORT=3001 npm run start
```

验证命令：

```bash
cd /path/to/yibiao-simple
python -m unittest backend.tests.test_contract_imports -v

cd /path/to/yibiao-simple/frontend
npm run test -- --watchAll=false
npm run build
```

## Jammy 适配注意事项

- 如果使用系统默认 Python 3.10，部分依赖虽然可能可安装，但建议统一到 Python 3.11。
- 如果启用 Playwright/Selenium 等 optional 能力，安装 Python optional 依赖后还需要按工具要求安装浏览器依赖，例如 `python -m playwright install --with-deps chromium`。
- 如果服务器无法访问外网，提前缓存 `backend/requirements.txt` 的 wheel 包和 `frontend/package-lock.json` 对应 npm 包。
- 如果只部署后端 API 并使用前端构建产物，可先在构建机执行 `npm ci && npm run build`，再把 `frontend/build` 复制到后端静态目录。
- 生产环境不要把模型 API Key 写入源码；使用环境变量或后端配置文件。

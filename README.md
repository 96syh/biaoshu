# 华正AI标书创作平台 - AI智能标书写作助手

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/React-18+-61dafb.svg" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>


<p align="left">
  <strong>🚀 基于 AI 的智能标书写作助手，让标书制作变得简单高效</strong>
</p>




### ✨ 核心功能

- **🤖 智能文档解析**：自动分析招标文件，提取关键信息和技术评分要求
- **📝 AI生成目录**：基于招标文件智能生成专业的三级标书目录结构  
- **⚡ 内容自动生成**：为每个章节自动生成高质量、针对性的标书内容
- **🎯 个性化定制**：支持***自定义AI模型***
- **💾 一键导出**：导出word，自由编辑

### 🌟 产品优势

- ⏱️ **效率提升**: 将传统需要数天的标书制作缩短至几小时
- 🎨 **专业质量**: AI生成的内容结构清晰、逻辑严密、符合行业标准
- 🔧 **易于使用**: 简洁直观的界面设计，无需专业培训即可上手
- 🔄 **持续优化**: 基于用户反馈不断改进AI算法和用户体验

## 📦 使用说明

### 💻 系统要求

- Windows 10/11 (64位)
- 至少 4GB 内存
- 100MB 可用磁盘空间

### ⬇️ 下载安装

1. **运行程序**：双击 `huazheng-ai.exe` 即可启动应用
2. **配置AI**：首次使用需要配置API Key密钥（推荐DeepSeek）


### 📝 使用流程

1. **📌 配置AI**：支持所有openai like的大模型，推荐DeepSeek  
  ![](./screenshots/1.png)
2. **📄 文档上传**：上传招标文件（支持Word和PDF格式）  
  ![](./screenshots/2.png)
3. **🔍 文档分析**：AI自动解析招标文件，提取项目概述和技术要求  
  ![](./screenshots/3.png)
4. **📋 生成目录**：基于分析结果智能生成标书目录结构  
  ![](./screenshots/4.png)
5. **✍️ 生成正文**：为各章节生成内容，多线程并发，极速体验  
  ![](./screenshots/5.png)
6. **📤 导出标书**：一键导出完整的标书文档  
  ![](./screenshots/6.png)

## 🛠️ 技术架构

### 架构设计

采用现代化的**前后端分离架构**，确保高性能和良好的用户体验：

- **前端**: React + TypeScript + Tailwind CSS
- **后端**: FastAPI + Python
- **AI集成**: OpenAI SDK
- **部署**: PyInstaller 单文件打包


### 🏗️ 项目结构

```
华正AI标书创作平台/
├── 📁 backend/                 # 后端服务
│   ├── 📁 app/
│   │   ├── main.py            # FastAPI应用入口
│   │   ├── config.py          # 应用配置
│   │   ├── 📁 routers/        # API路由模块
│   │   ├── 📁 services/       # 业务逻辑服务  
│   │   └── 📁 models/         # 数据模型
│   └── requirements.txt       # Python依赖
├── 📁 frontend/               # 前端应用
│   ├── 📁 src/
│   │   ├── 📁 components/     # 可复用组件
│   │   ├── 📁 pages/          # 页面组件
│   │   ├── 📁 services/       # API服务
│   │   └── 📁 hooks/          # React Hooks
│   └── package.json           # 前端依赖
├── single_port.bat            # 一键启动脚本
├── build.py                   # 打包脚本
└── README.md                  # 项目文档
```


## 🚀 开发说明

### 开发环境运行

```bash
# 进入项目目录
cd yibiao-simple

# 一键启动
./single_port.bat

```

### 生产环境打包

```bash
# 一键构建exe
python build.py

# Windows批处理脚本
build.bat
```

构建完成后，exe文件位于 `dist/huazheng-ai.exe`

### Docker 打包（精简运行时，默认 amd64）

当前 Docker 方案采用两阶段构建：

- 前端在 `node` 阶段编译为静态文件
- 运行时仅保留 `FastAPI` 后端、前端静态产物和核心 Python 依赖
- 默认关闭搜索路由，避免把 `Playwright / Selenium / MCP` 这类重依赖打进镜像

在项目根目录执行：

```bash
docker buildx build --platform linux/amd64 -t huazheng-ai:amd64 . --load
```

本地运行：

```bash
docker run --rm -p 8000:8000 \
  -v huazheng-ai-config:/home/app/.ai_write_helper \
  -v huazheng-ai-uploads:/app/backend/uploads \
  huazheng-ai:amd64
```

启动后访问：

- `http://localhost:8000`
- `http://localhost:8000/docs`

如果需要把镜像发给 amd64 服务器，建议直接使用带平台参数的 `buildx` 构建；若需要推送到镜像仓库，可把 `build` 改为 `build --push`。

## 📚 API文档

启动应用后访问 `http://localhost:8000/docs` 查看完整的FastAPI自动生成的API文档。

补充文档：

- [本地大模型调用 API 文档](./docs/local-model-api.md)
- [LiteLLM Proxy 统一模型网关接入说明](./docs/litellm-proxy.md)


## 📌代办任务
- [ ] 录入预期字数


## 📄 许可证

本项目基于 [MIT License](LICENSE) 协议发布。

## 🙋‍♂️ 联系我们

- **邮箱联系**: support@huazheng-ai.com

---

<p align="center">
  Made with ❤️ by 华正AI团队 
</p>

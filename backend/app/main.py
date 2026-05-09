"""FastAPI应用主入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path
import fastapi.middleware.cors
import starlette.middleware.cors

from .config import settings
from .routers import config, document, outline, content, projects, history_cases
from .services.file_service import FileService
from .services.model_runtime_monitor import ModelRuntimeMonitor

HTML_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


search = None
if _env_enabled("ENABLE_SEARCH_ROUTER", False):
    try:
        from .optional import search
    except Exception as search_import_error:
        print(f"搜索模块未启用: {search_import_error}")

expand = None
if _env_enabled("ENABLE_LEGACY_EXPAND_ROUTER", False):
    try:
        from .optional import expand
    except Exception as expand_import_error:
        print(f"旧扩写模块未启用: {expand_import_error}")

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于FastAPI的AI写标书助手后端API"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(config.router)
app.include_router(document.router)
app.include_router(outline.router)
app.include_router(content.router)
app.include_router(projects.router)
app.include_router(history_cases.router)

if search is not None:
    app.include_router(search.router)

if expand is not None:
    app.include_router(expand.router)

FileService.GENERATED_ASSET_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    FileService.GENERATED_ASSET_URL_PREFIX,
    StaticFiles(directory=str(FileService.GENERATED_ASSET_DIR)),
    name="generated_assets",
)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "model_runtime": ModelRuntimeMonitor.snapshot(),
    }

def _frontend_static_dir() -> Path | None:
    configured = os.getenv("YIBIAO_FRONTEND_STATIC_DIR", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend([
        Path("static"),
        Path(__file__).resolve().parents[2] / "artifacts" / "build" / "backend-static",
    ])
    for candidate in candidates:
        if candidate and (candidate / "index.html").exists():
            return candidate
    return None


FRONTEND_STATIC_DIR = _frontend_static_dir()

# 静态文件服务（用于服务前端构建文件，默认作为 artifact 而非源码主路径）
if FRONTEND_STATIC_DIR:
    # 挂载静态资源文件夹
    static_assets_dir = FRONTEND_STATIC_DIR / "static"
    if static_assets_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_assets_dir)), name="static")

    def frontend_index_response() -> FileResponse:
        """返回前端入口页，并显式禁止浏览器缓存 HTML 入口"""
        return FileResponse(str(FRONTEND_STATIC_DIR / "index.html"), headers=HTML_NO_CACHE_HEADERS)
    
    # 处理React应用的路由（SPA路由支持）
    @app.get("/")
    async def read_index():
        """根路径，返回前端首页"""
        return frontend_index_response()
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """处理React路由，所有非API路径都返回index.html"""
        # 排除API路径
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("health"):
            # 这些路径应该由FastAPI处理，如果到这里说明404
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # 检查是否是静态文件
        static_file_path = FRONTEND_STATIC_DIR / full_path
        if static_file_path.exists() and static_file_path.is_file():
            return FileResponse(str(static_file_path))
        
        # 对于其他所有路径，返回React应用的index.html（SPA路由）
        return frontend_index_response()
else:
    # 如果没有静态文件，返回API信息
    @app.get("/")
    async def read_root():
        """根路径，返回API信息"""
        return {
            "message": f"欢迎使用 {settings.app_name} API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health"
        }

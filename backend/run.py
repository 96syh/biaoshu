"""后端服务启动脚本"""
import uvicorn
import os
import multiprocessing

if __name__ == "__main__":
    # 确保在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", str(multiprocessing.cpu_count() * 2)))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # 多进程模式下不支持reload
        log_level="info",
        workers=workers  # 默认使用 CPU 核心数的 2 倍，可通过环境变量覆盖
    )

"""后端服务启动脚本"""
import uvicorn
import os

if __name__ == "__main__":
    # 确保在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # 多进程模式下不支持reload
        log_level="info",
        workers=workers  # 本地长任务默认单进程，避免多 worker 分散日志或中断后台解析任务
    )

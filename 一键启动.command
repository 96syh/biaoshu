#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
REACT_APP_API_URL="${REACT_APP_API_URL:-http://$BACKEND_HOST:$BACKEND_PORT}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$SCRIPT_DIR/.venv311/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv311/bin/python"
  elif [ -x "/opt/anaconda3/bin/python" ]; then
    PYTHON_BIN="/opt/anaconda3/bin/python"
  else
    PYTHON_BIN="$(command -v python3 || true)"
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "未找到 Python，请先安装 Python 或设置 PYTHON_BIN。"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请先安装 Node.js。"
  exit 1
fi

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return 0
  fi

  echo "停止端口 $port: $pids"
  kill $pids 2>/dev/null || true
  sleep 1

  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "端口 $port 仍被占用，强制停止: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

clear || true
printf '\n'
printf '========================================\n'
printf ' 华正 AI 标书系统 - 一键启动\n'
printf '========================================\n\n'
printf '项目目录: %s\n' "$SCRIPT_DIR"
printf '后端地址: http://%s:%s\n' "$BACKEND_HOST" "$BACKEND_PORT"
printf '前端地址: http://%s:%s/#project\n' "$FRONTEND_HOST" "$FRONTEND_PORT"
printf 'API 地址:  %s\n\n' "$REACT_APP_API_URL"
printf '正在清理当前占用端口...\n'

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
if [ "$FRONTEND_PORT" != "3000" ]; then
  kill_port "3000"
fi

LAUNCH_DIR="${TMPDIR:-/tmp}/yibiao-simple-launch"
mkdir -p "$LAUNCH_DIR"
BACKEND_LAUNCHER="$LAUNCH_DIR/backend.command"
FRONTEND_LAUNCHER="$LAUNCH_DIR/frontend.command"

cat >"$BACKEND_LAUNCHER" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
clear || true
echo "华正 AI 标书系统 - 后端 API"
echo "目录: $BACKEND_DIR"
echo "地址: http://$BACKEND_HOST:$BACKEND_PORT"
echo "模型监听: 本窗口会输出 [model-runtime] 开始请求 / 首段输出 / 完成 / 失败"
echo "状态接口: http://$BACKEND_HOST:$BACKEND_PORT/api/config/model-runtime"
echo
cd "$BACKEND_DIR"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
HOST="$BACKEND_HOST" PORT="$BACKEND_PORT" WORKERS=1 "$PYTHON_BIN" run.py
EOF

cat >"$FRONTEND_LAUNCHER" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
clear || true
echo "华正 AI 标书系统 - 前端页面"
echo "目录: $FRONTEND_DIR"
echo "地址: http://$FRONTEND_HOST:$FRONTEND_PORT/#project"
echo "API:  $REACT_APP_API_URL"
echo
cd "$FRONTEND_DIR"
HOST="$FRONTEND_HOST" PORT="$FRONTEND_PORT" REACT_APP_API_URL="$REACT_APP_API_URL" BROWSER=none npm run start
EOF
chmod +x "$BACKEND_LAUNCHER" "$FRONTEND_LAUNCHER"

if command -v open >/dev/null 2>&1; then
  open -a Terminal "$BACKEND_LAUNCHER"
  open -a Terminal "$FRONTEND_LAUNCHER"
else
  echo "未找到 open，无法自动打开终端窗口。"
  echo "请手动运行："
  printf '%s\n' "$BACKEND_LAUNCHER"
  printf '%s\n' "$FRONTEND_LAUNCHER"
  exit 1
fi

printf '\n已打开两个终端窗口：后端 API 与前端页面。\n'
printf '如需停止服务，关闭对应终端窗口或按 Ctrl+C。\n'

if [ "$OPEN_BROWSER" = "1" ]; then
  sleep 3
  open "http://$FRONTEND_HOST:$FRONTEND_PORT/#project" >/dev/null 2>&1 || true
fi

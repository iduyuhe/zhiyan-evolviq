#!/bin/bash
# 智衍 EvolvIQ — 一键启动脚本（本地开发模式）
# 用法: bash scripts/startup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 智衍 EvolvIQ — 启动中..."
echo "================================"

# 1. 检查虚拟环境
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi
source "$PROJECT_DIR/.venv/bin/activate"

# 2. 安装依赖
echo "📦 安装依赖..."
pip install -q -e "$PROJECT_DIR"

# 3. 生成种子数据
echo "🌱 生成种子数据..."
python "$PROJECT_DIR/scripts/seed_data.py"

# 4. 启动后端 Runtime
echo "⚙️  启动 Runtime (port 8000)..."
cd "$PROJECT_DIR"
uvicorn src.runtime.main:app --host 0.0.0.0 --port 8000 --reload &
RUNTIME_PID=$!
echo "   Runtime PID: $RUNTIME_PID"

# 5. 启动前端 Studio
echo "🎨 启动 Studio (port 5173)..."
cd "$PROJECT_DIR/studio"
npm run dev -- --host 0.0.0.0 &
STUDIO_PID=$!
echo "   Studio PID: $STUDIO_PID"

# 6. 等待就绪并验证
sleep 4
echo ""
echo "================================"
echo "✅ 智衍 EvolvIQ 已启动!"
echo ""
echo "   Agent Studio: http://localhost:5173"
echo "   Runtime API:  http://localhost:8000"
echo "   API文档:      http://localhost:8000/docs"
echo "   MCP工具:      http://localhost:8000/mcp/tools"
echo ""
echo "   按 Ctrl+C 停止所有服务"
echo "================================"

# 等待进程结束
trap "kill $RUNTIME_PID $STUDIO_PID 2>/dev/null; exit" SIGINT SIGTERM
wait

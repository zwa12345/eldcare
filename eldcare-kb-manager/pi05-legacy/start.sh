#!/bin/bash
# 家庭影院启动脚本
# 用法: ./start.sh [端口]

PORT=${1:-5001}
cd "$(dirname "$0")"

echo "🎬 家庭影院启动中..."
echo "📂 电影目录: $(pwd)/movies"
echo "🌐 访问地址: http://$(hostname -I | awk '{print $1}'):$PORT"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 安装依赖
echo "📦 安装依赖..."
./venv/bin/pip install -q -r requirements.txt

# 启动服务
echo "🚀 服务启动: http://0.0.0.0:$PORT"
exec ./venv/bin/python app.py

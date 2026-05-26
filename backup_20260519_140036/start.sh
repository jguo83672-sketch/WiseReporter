#!/bin/bash
echo "========================================"
echo "  WiseReporter 教育信息收集平台"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python，请先安装Python 3.8+"
    exit 1
fi

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "[2/4] 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "[3/4] 安装依赖包..."
pip install -q -r requirements.txt

# 初始化数据库
echo "[4/4] 初始化数据库..."
python init_db.py

# 启动服务
echo ""
echo "========================================"
echo "  启动服务中..."
echo "  访问 http://localhost:5000"
echo "========================================"
echo ""

python run.py

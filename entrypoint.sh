#!/bin/bash
# ==============================================
# WiseReporter Docker 容器启动脚本
# ==============================================
set -e

echo "=========================================="
echo "  WiseReporter - 教育行业信息收集平台"
echo "=========================================="

# 确保必要的目录存在
mkdir -p /app/logs /app/instance

# 等待数据库就绪（PostgreSQL/MySQL）
if [[ -n "$DB_HOST" ]]; then
    echo "[INFO] 等待数据库连接 $DB_HOST:$DB_PORT ..."
    while ! nc -z "$DB_HOST" "${DB_PORT:-5432}" 2>/dev/null; do
        sleep 1
    done
    echo "[INFO] 数据库连接就绪"
fi

echo "[INFO] 启动 WiseReporter 应用..."

# 使用 Gunicorn 启动（生产环境）
exec gunicorn -w 4 \
    -b 0.0.0.0:5000 \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    --preload \
    "app:create_app()"

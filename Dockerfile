# ==============================================
# WiseReporter Dockerfile
# 教育行业信息收集平台
# ==============================================
FROM python:3.11-slim

LABEL maintainer="WiseReporter"
LABEL description="WiseReporter - 教育行业信息收集平台"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_CONFIG=production \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p logs instance

# 创建非 root 用户
RUN useradd -m -u 1000 wisereporter && \
    chown -R wisereporter:wisereporter /app
USER wisereporter

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "120", \
     "app:create_app()"]

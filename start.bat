@echo off
chcp 65001 >nul
echo ========================================
echo   WiseReporter 教育信息收集平台
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo [3/4] 安装依赖包...
pip install -q -r requirements.txt

REM 初始化数据库
echo [4/4] 初始化数据库...
python init_db.py

REM 启动服务
echo.
echo ========================================
echo   启动服务中...
echo   访问 http://localhost:5000
echo ========================================
echo.
python run.py

pause

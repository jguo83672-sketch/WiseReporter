#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WiseReporter 启动脚本
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from scheduler import init_scheduler

# 创建应用
app = create_app()

if __name__ == '__main__':
    # 开发环境
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    if debug_mode:
        # 启动定时任务调度器
        scheduler = init_scheduler(app)
        
        try:
            # 启动Flask应用
            app.run(
                host='0.0.0.0',
                port=int(os.environ.get('PORT', 5000)),
                debug=True
            )
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
    else:
        # 生产环境使用 gunicorn
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000))
        )

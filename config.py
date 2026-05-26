import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'wise-reporter-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///wisereporter.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 调试配置
    DEBUG = False
    
    # Cookie池配置
    COOKIE_POOL_SIZE = 5
    COOKIE_EXPIRY_HOURS = 24
    
    # 爬虫配置
    REQUEST_TIMEOUT = 30
    RETRY_TIMES = 3
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    
    # 定时任务配置
    SCHEDULER_API_ENABLED = True
    
    # 分页配置
    ITEMS_PER_PAGE = 20

    # Coze工作流配置
    COZE_API_URL = 'https://api.coze.cn/v1/workflow/run'
    COZE_WORKFLOW_ID = '7641508293730467875'  # 微信公众号链接获取工作流
    COZE_API_TOKEN = os.environ.get('COZE_API_TOKEN') or ''  # 需要在环境变量中设置

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

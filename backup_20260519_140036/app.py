"""
WiseReporter - 教育行业信息收集平台
Flask应用入口
"""
import os
import logging
from flask import Flask
from flask_migrate import Migrate
from config import config
from models import db, login_manager

migrate = Migrate()

def create_app(config_name=None):
    """应用工厂"""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    app = Flask(__name__,
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))
    
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # 用户加载器
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return db.session.get(User, int(user_id))
    
    # API未认证处理 - 返回JSON而不是重定向
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import jsonify
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    
    # 全局错误处理器 - 确保所有错误返回JSON
    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import jsonify, request
        # 如果是 API 请求，返回 JSON 错误
        if request.path.startswith('/api'):
            import traceback
            app.logger.error(f'API Error: {str(e)}\n{traceback.format_exc()}')
            return jsonify({'code': 500, 'message': f'服务器错误: {str(e)}'}), 500
        # 非 API 请求返回 HTML
        return jsonify({'code': 500, 'message': str(e)}), 500
    
    # BadRequest 错误处理器 - 处理无效JSON等情况
    @app.errorhandler(400)
    def handle_bad_request(e):
        from flask import jsonify, request
        if request.path.startswith('/api'):
            return jsonify({'code': 400, 'message': f'请求格式错误: {str(e)}'}), 400
        return jsonify({'code': 400, 'message': str(e)}), 400
    
    # 配置日志
    if not app.debug:
        # 生产环境日志配置
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10*1024*1024, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('WiseReporter startup')
    
    # 注册蓝图
    from routes.main import main_bp
    from routes.api import api_bp
    from routes.auth import auth_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # 添加自定义 Jinja2 过滤器
    @app.template_filter('format_date')
    def format_date(value, fmt='%Y-%m-%d'):
        """安全格式化日期，支持字符串或datetime对象"""
        if value is None:
            return '-'
        if isinstance(value, str):
            # 如果是字符串，尝试提取日期部分
            if len(value) >= 10:
                return value[:10]
            return value
        try:
            return value.strftime(fmt)
        except AttributeError:
            return str(value)
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

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
        from flask import jsonify, request
        if request.path.startswith('/api'):
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        # 非API请求重定向到登录页
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    # 全局错误处理器 - 确保所有错误返回正确的响应格式
    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import jsonify, request, render_template
        # 如果是 API 请求，返回 JSON 错误
        if request.path.startswith('/api'):
            import traceback
            app.logger.error(f'API Error: {str(e)}\n{traceback.format_exc()}')
            return jsonify({'code': 500, 'message': f'服务器错误: {str(e)}'}), 500
        # 非 API 请求返回错误页面
        import traceback
        app.logger.error(f'Page Error: {str(e)}\n{traceback.format_exc()}')
        return render_template('error.html', error=str(e)), 500

    # BadRequest 错误处理器 - 处理无效JSON等情况
    @app.errorhandler(400)
    def handle_bad_request(e):
        from flask import jsonify, request, redirect, url_for
        if request.path.startswith('/api'):
            return jsonify({'code': 400, 'message': f'请求格式错误: {str(e)}'}), 400
        return redirect(url_for('main.index'))

    # 404 Not Found 错误处理器
    @app.errorhandler(404)
    def handle_not_found(e):
        from flask import jsonify, request, render_template
        if request.path.startswith('/api'):
            return jsonify({'code': 404, 'message': '资源不存在'}), 404
        return render_template('error.html', error='页面不存在'), 404

    # 405 Method Not Allowed 错误处理器
    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        from flask import jsonify, request, redirect, url_for
        if request.path.startswith('/api'):
            return jsonify({'code': 405, 'message': '请求方法不允许'}), 405
        return redirect(url_for('main.index'))
    
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
        # 迁移：为已有的表添加缺失的列
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)

        # 初始化默认周报设置（仅在不存在时）
        from models import SystemConfig
        if SystemConfig.get('weekly_report_day_of_week') is None:
            SystemConfig.set('weekly_report_day_of_week', 'mon', '周报自动生成日（mon-sun）')
            SystemConfig.set('weekly_report_hour', '9', '周报自动生成小时（0-23）')
            SystemConfig.set('weekly_report_minute', '0', '周报自动生成分钟（0-59）')
            SystemConfig.set('weekly_report_enabled', 'true', '是否自动生成周报')
            app.logger.info('[Migration] Initialized default weekly report settings')
        
        # education_company 表：添加 category 列
        if 'education_company' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('education_company')]
            if 'category' not in columns:
                db.session.execute(text("ALTER TABLE education_company ADD COLUMN category VARCHAR(30) NOT NULL DEFAULT 'education_company'"))
                db.session.commit()
                app.logger.info('[Migration] Added category column to education_company table')
        
        # leidui_content 表：添加 matched_keyword 列
        if 'leidui_content' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('leidui_content')]
            if 'matched_keyword' not in columns:
                db.session.execute(text("ALTER TABLE leidui_content ADD COLUMN matched_keyword VARCHAR(200)"))
                db.session.commit()
                app.logger.info('[Migration] Added matched_keyword column to leidui_content table')
        
        # finance_content 表：添加 matched_keyword 列
        if 'finance_content' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('finance_content')]
            if 'matched_keyword' not in columns:
                db.session.execute(text("ALTER TABLE finance_content ADD COLUMN matched_keyword VARCHAR(200)"))
                db.session.commit()
                app.logger.info('[Migration] Added matched_keyword column to finance_content table')

        # 回填：为已有收藏但缺少 matched_keyword 的记录补充关键词
        from core.report_generator import find_matching_education_company
        try:
            from models import LeiduiContent, FinanceContent
            for model_class, label in [(LeiduiContent, '雷递网'), (FinanceContent, '投资界')]:
                records = model_class.query.filter(
                    model_class.is_favorite == True,
                    model_class.matched_keyword.is_(None)
                ).all()
                if records:
                    for r in records:
                        matched = find_matching_education_company(r.title or '', r.summary or '')
                        if matched:
                            r.matched_keyword = matched
                    db.session.commit()
                    app.logger.info(f'[Backfill] 为 {label} {len(records)} 条收藏记录补充了匹配关键词')
        except Exception as e:
            app.logger.warning(f'[Backfill] matched_keyword 回填跳过: {e}')
    
    return app

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

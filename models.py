from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()
login_manager = LoginManager()

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

def now_beijing():
    """获取北京时间"""
    return datetime.now(BEIJING_TZ)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')  # super_admin / admin / user
    permissions = db.Column(db.Text, default='[]')  # JSON数组，普通用户的额外权限
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    @property
    def is_admin(self):
        return self.role in ('super_admin', 'admin')
    
    @property
    def can_write(self):
        """是否有写入权限（管理员或有任意写入权限的普通用户）"""
        if self.is_admin:
            return True
        perms = self.get_permissions_list()
        return len(perms) > 0
    
    def get_permissions_list(self):
        """解析权限JSON为列表"""
        import json
        try:
            return json.loads(self.permissions or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_permissions(self, perm_list):
        """设置权限列表"""
        import json
        self.permissions = json.dumps(perm_list, ensure_ascii=False)
    
    def has_permission(self, perm_name):
        """检查是否有指定权限（管理员始终拥有所有权限）"""
        if self.is_admin:
            return True
        return perm_name in self.get_permissions_list()
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class OfficialAccount(db.Model):
    """公众号表"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 公众号名称
    account_id = db.Column(db.String(100), unique=True, nullable=False)  # 公众号ID
    biz = db.Column(db.String(100), unique=True, nullable=False)  # 公众号biz标识（__biz参数）
    description = db.Column(db.Text)  # 描述
    category = db.Column(db.String(50))  # 分类：行业动态、公司动态、投融资等
    is_active = db.Column(db.Boolean, default=True)  # 是否启用采集
    crawl_interval = db.Column(db.Integer, default=24)  # 采集间隔（小时）
    last_crawl_time = db.Column(db.DateTime)  # 上次采集时间
    created_at = db.Column(db.DateTime, default=now_beijing)
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    articles = db.relationship('Article', backref='account', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'account_id': self.account_id,
            'biz': self.biz,
            'description': self.description,
            'category': self.category,
            'is_active': self.is_active,
            'crawl_interval': self.crawl_interval,
            'last_crawl_time': self.last_crawl_time.strftime('%Y-%m-%d %H:%M') if self.last_crawl_time else None
        }
    
    def __repr__(self):
        return f'<OfficialAccount {self.name}>'


class WechatCredential(db.Model):
    """微信公众号凭证（Cookie和Token）"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 凭证名称，如"我的公众号"
    cookie = db.Column(db.Text, nullable=False)  # Cookie字符串
    token = db.Column(db.String(200))  # Token（可选）
    user_agent = db.Column(db.String(500))  # User-Agent
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    is_primary = db.Column(db.Boolean, default=False)  # 是否为主凭证
    failure_count = db.Column(db.Integer, default=0)  # 失败次数
    last_used = db.Column(db.DateTime)  # 上次使用时间
    expires_at = db.Column(db.DateTime)  # 过期时间
    created_at = db.Column(db.DateTime, default=now_beijing)
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    def __repr__(self):
        return f'<WechatCredential {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cookie': self.cookie[:50] + '...' if len(self.cookie) > 50 else self.cookie,
            'token': self.token,
            'is_active': self.is_active,
            'is_primary': self.is_primary,
            'failure_count': self.failure_count,
            'last_used': self.last_used.strftime('%Y-%m-%d %H:%M') if self.last_used else None,
            'expires_at': self.expires_at.strftime('%Y-%m-%d %H:%M') if self.expires_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

class Article(db.Model):
    """文章表"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    author = db.Column(db.String(200))
    summary = db.Column(db.Text)  # 摘要
    content = db.Column(db.Text)  # 完整内容
    publish_date = db.Column(db.DateTime)
    category = db.Column(db.String(50))  # 文章分类
    tags = db.Column(db.String(500))  # 标签，逗号分隔
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    is_important = db.Column(db.Boolean, default=False)  # 是否重要
    account_id = db.Column(db.Integer, db.ForeignKey('official_account.id'))
    created_at = db.Column(db.DateTime, default=now_beijing)
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    def __repr__(self):
        return f'<Article {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'author': self.author,
            'summary': self.summary,
            'publish_date': self.publish_date.strftime('%Y-%m-%d') if self.publish_date else None,
            'category': self.category,
            'tags': self.tags.split(',') if self.tags else [],
            'account_name': self.account.name if self.account else None,
            'is_important': self.is_important,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

class CookiePool(db.Model):
    """Cookie池"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Cookie名称/标识
    cookie_data = db.Column(db.Text, nullable=False)  # Cookie的JSON数据
    user_agent = db.Column(db.String(500))  # 对应的User-Agent
    is_available = db.Column(db.Boolean, default=True)  # 是否可用
    failure_count = db.Column(db.Integer, default=0)  # 失败次数
    last_used = db.Column(db.DateTime)  # 上次使用时间
    expires_at = db.Column(db.DateTime)  # 过期时间
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<CookiePool {self.name}>'

class AIContent(db.Model):
    """AI前沿资讯"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    source = db.Column(db.String(100))  # 来源：36kr AI、机器之心、AI前线等
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    publish_date = db.Column(db.DateTime)
    category = db.Column(db.String(50))  # AI分类
    tags = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<AIContent {self.title}>'


class EducationContent(db.Model):
    """教育资讯"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    source = db.Column(db.String(100))  # 来源：jiemodui/duozhi
    source_name = db.Column(db.String(100))  # 来源名称：芥末堆/多知网
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    publish_date = db.Column(db.DateTime)  # 备用，已解析的日期
    publish_date_str = db.Column(db.String(100))  # 原始时间字符串，如 "5/12/2026, 5:04:30 PM"
    category = db.Column(db.String(50))  # 分类
    tags = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)  # 是否已读
    is_favorite = db.Column(db.Boolean, default=False)  # 是否收藏
    ai_summary = db.Column(db.Text)  # AI生成的摘要
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<EducationContent {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'source_name': self.source_name,
            'summary': self.summary,
            'ai_summary': self.ai_summary,
            'publish_date': self.publish_date.strftime('%Y-%m-%d') if self.publish_date else None,
            'publish_date_str': self.publish_date_str,
            'category': self.category,
            'tags': self.tags.split(',') if self.tags else [],
            'is_read': self.is_read,
            'is_favorite': self.is_favorite,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

class WeeklyReport(db.Model):
    """周报表"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Markdown格式
    report_date = db.Column(db.Date, nullable=False)  # 周报日期
    period_start = db.Column(db.Date)  # 周期开始
    period_end = db.Column(db.Date)  # 周期结束
    article_count = db.Column(db.Integer, default=0)  # 文章数量
    ai_news_count = db.Column(db.Integer, default=0)  # AI资讯数量
    status = db.Column(db.String(20), default='draft')  # 状态：draft/published
    created_at = db.Column(db.DateTime, default=now_beijing)
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    def __repr__(self):
        return f'<WeeklyReport {self.title}>'

class CrawlLog(db.Model):
    """采集日志"""
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('official_account.id'))
    status = db.Column(db.String(20))  # success/failed
    message = db.Column(db.Text)
    articles_count = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<CrawlLog {self.id}>'

class CrawlProgress(db.Model):
    """爬取进度记录"""
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # duozhi, jiemodui等
    last_article_id = db.Column(db.Integer, nullable=False)  # 最后爬取的ID
    last_article_date = db.Column(db.String(20))  # 最后文章对应的日期 YYYYMMDD
    last_crawl_date = db.Column(db.String(20))  # 最后爬取日期 YYYYMMDD
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    def __repr__(self):
        return f'<CrawlProgress {self.source}>'


class WechatContent(db.Model):
    """微信公众号文章"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    account_name = db.Column(db.String(100))  # 公众号名称
    account_id = db.Column(db.String(100))  # 公众号ID
    author = db.Column(db.String(200))
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    cover_image = db.Column(db.String(500))  # 封面图
    publish_date = db.Column(db.DateTime)
    tags = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<WechatContent {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'account_name': self.account_name,
            'account_id': self.account_id,
            'author': self.author,
            'summary': self.summary,
            'cover_image': self.cover_image,
            'publish_date': self.publish_date.strftime('%Y-%m-%d') if self.publish_date else None,
            'tags': self.tags.split(',') if self.tags else [],
            'is_read': self.is_read,
            'is_favorite': self.is_favorite,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class NewsSource(db.Model):
    """资讯来源配置"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    source_type = db.Column(db.String(50))  # wechat/ai_news/industry
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    last_crawl = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<NewsSource {self.name}>'


class LeiduiContent(db.Model):
    """雷递网投融资/财报资讯"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    source = db.Column(db.String(100), default='leinews')  # 来源
    source_name = db.Column(db.String(100), default='雷递网')  # 来源名称
    summary = db.Column(db.Text)  # 摘要
    content = db.Column(db.Text)  # 完整内容
    cover_image = db.Column(db.String(500))  # 封面图
    category = db.Column(db.String(50))  # 分类：投融资/财报/上市等
    tags = db.Column(db.String(500))  # 标签
    author = db.Column(db.String(100))  # 作者
    publish_date = db.Column(db.DateTime)  # 发布时间
    is_read = db.Column(db.Boolean, default=False)  # 是否已读
    is_favorite = db.Column(db.Boolean, default=False)  # 是否收藏
    matched_keyword = db.Column(db.String(200))  # 自动收藏时匹配到的关键词
    created_at = db.Column(db.DateTime, default=now_beijing)
    
    def __repr__(self):
        return f'<LeiduiContent {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'source_name': self.source_name,
            'summary': self.summary,
            'cover_image': self.cover_image,
            'category': self.category,
            'tags': self.tags.split(',') if self.tags else [],
            'author': self.author,
            'publish_date': self.publish_date.strftime('%Y-%m-%d') if self.publish_date else None,
            'is_read': self.is_read,
            'is_favorite': self.is_favorite,
            'matched_keyword': self.matched_keyword,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class FinanceContent(db.Model):
    """投融资/财报资讯（投资界等）"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000), unique=True, nullable=False)
    source = db.Column(db.String(100), default='pedaily')
    source_name = db.Column(db.String(100), default='投资界')
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    cover_image = db.Column(db.String(500))
    category = db.Column(db.String(50))  # 投融资/财报/IPO等
    tags = db.Column(db.String(500))
    author = db.Column(db.String(100))
    publish_date = db.Column(db.DateTime)
    publish_date_str = db.Column(db.String(100))
    is_read = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)
    matched_keyword = db.Column(db.String(200))  # 自动收藏时匹配到的关键词
    created_at = db.Column(db.DateTime, default=now_beijing)

    def __repr__(self):
        return f'<FinanceContent {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'source_name': self.source_name,
            'summary': self.summary,
            'cover_image': self.cover_image,
            'category': self.category,
            'tags': self.tags.split(',') if self.tags else [],
            'author': self.author,
            'publish_date': self.publish_date.strftime('%Y-%m-%d') if self.publish_date else None,
            'publish_date_str': self.publish_date_str,
            'is_read': self.is_read,
            'is_favorite': self.is_favorite,
            'matched_keyword': self.matched_keyword,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class EducationCompany(db.Model):
    """教育公司关键词（用于投融资/财报资讯筛选）

    分类说明：
    - education_company: 全球教育公司中英文名称
    - other: 其他教育相关关键词
    """
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(200), unique=True, nullable=False)  # 关键词（支持中文/英文）
    category = db.Column(db.String(30), default='education_company', nullable=False)  # 分类
    created_at = db.Column(db.DateTime, default=now_beijing)

    CATEGORY_LABELS = {
        'education_company': '教育公司中英文名称',
        'other': '其他教育相关关键词',
    }

    @classmethod
    def get_category_label(cls, category):
        """获取分类的显示名称（兼容旧数据NULL）"""
        cat = category or 'education_company'
        return cls.CATEGORY_LABELS.get(cat, cat)

    def to_dict(self):
        cat = self.category or 'education_company'
        return {
            'id': self.id,
            'keyword': self.keyword,
            'category': cat,
            'category_label': self.CATEGORY_LABELS.get(cat, cat),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

    def __repr__(self):
        return f'<EducationCompany {self.keyword}>'


class CrawlTaskConfig(db.Model):
    """定时采集任务配置"""
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(50), unique=True, nullable=False)  # ai_news, education_news
    task_type = db.Column(db.String(50), nullable=False)  # ai_news, education_news, wechat_article
    display_name = db.Column(db.String(100), nullable=False)  # 显示名称
    description = db.Column(db.String(500))  # 任务描述
    is_enabled = db.Column(db.Boolean, default=True)  # 是否启用
    cron_hour = db.Column(db.Integer, default=2)  # 执行小时
    cron_minute = db.Column(db.Integer, default=0)  # 执行分钟
    cron_day_of_week = db.Column(db.String(20))  # 每周几执行，如 'mon,wed,fri'
    keywords = db.Column(db.String(500))  # 搜索关键词，逗号分隔
    max_count = db.Column(db.Integer, default=20)  # 每次最大采集数量
    auto_crawl_content = db.Column(db.Boolean, default=True)  # 是否自动采集文章内容
    last_run = db.Column(db.DateTime)  # 上次执行时间
    last_status = db.Column(db.String(20))  # success, failed, disabled
    last_message = db.Column(db.String(500))  # 上次执行消息
    created_at = db.Column(db.DateTime, default=now_beijing)
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'task_type': self.task_type,
            'display_name': self.display_name,
            'description': self.description,
            'is_enabled': self.is_enabled,
            'cron_hour': self.cron_hour,
            'cron_minute': self.cron_minute,
            'cron_day_of_week': self.cron_day_of_week,
            'keywords': self.keywords.split(',') if self.keywords else [],
            'max_count': self.max_count,
            'auto_crawl_content': self.auto_crawl_content,
            'last_run': self.last_run.strftime('%Y-%m-%d %H:%M') if self.last_run else None,
            'last_status': self.last_status,
            'last_message': self.last_message
        }
    
    def __repr__(self):
        return f'<CrawlTaskConfig {self.task_name}>'


class SystemConfig(db.Model):
    """系统配置（键值对，持久化存储）"""
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False)
    config_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=now_beijing, onupdate=now_beijing)

    @staticmethod
    def get(key, default=None):
        """获取配置值"""
        entry = SystemConfig.query.filter_by(config_key=key).first()
        if entry is None:
            return default
        return entry.config_value

    @staticmethod
    def set(key, value, description=''):
        """设置配置值（不存在则创建）"""
        entry = SystemConfig.query.filter_by(config_key=key).first()
        if entry is None:
            entry = SystemConfig(config_key=key, config_value=str(value), description=description)
            db.session.add(entry)
        else:
            entry.config_value = str(value)
            if description:
                entry.description = description
        db.session.commit()

    @staticmethod
    def get_bool(key, default=False):
        """获取布尔类型配置值"""
        val = SystemConfig.get(key)
        if val is None:
            return default
        return val.lower() in ('true', '1', 'yes')

    @staticmethod
    def get_int(key, default=0):
        """获取整数类型配置值"""
        val = SystemConfig.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def to_dict(self):
        return {
            'key': self.config_key,
            'value': self.config_value,
            'description': self.description,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def __repr__(self):
        return f'<SystemConfig {self.config_key}={self.config_value}>'

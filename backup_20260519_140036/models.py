from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.username}>'

class OfficialAccount(db.Model):
    """公众号表"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 公众号名称
    account_id = db.Column(db.String(100), unique=True, nullable=False)  # 公众号ID
    description = db.Column(db.Text)  # 描述
    category = db.Column(db.String(50))  # 分类：行业动态、公司动态、投融资等
    is_active = db.Column(db.Boolean, default=True)  # 是否启用采集
    crawl_interval = db.Column(db.Integer, default=24)  # 采集间隔（小时）
    last_crawl_time = db.Column(db.DateTime)  # 上次采集时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    articles = db.relationship('Article', backref='account', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'account_id': self.account_id,
            'description': self.description,
            'category': self.category,
            'is_active': self.is_active,
            'crawl_interval': self.crawl_interval,
            'last_crawl_time': self.last_crawl_time.strftime('%Y-%m-%d %H:%M') if self.last_crawl_time else None
        }
    
    def __repr__(self):
        return f'<OfficialAccount {self.name}>'

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CrawlLog {self.id}>'

class CrawlProgress(db.Model):
    """爬取进度记录"""
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50), nullable=False)  # duozhi, jiemodui等
    last_article_id = db.Column(db.Integer, nullable=False)  # 最后爬取的ID
    last_article_date = db.Column(db.String(20))  # 最后文章对应的日期 YYYYMMDD
    last_crawl_date = db.Column(db.String(20))  # 最后爬取日期 YYYYMMDD
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<NewsSource {self.name}>'

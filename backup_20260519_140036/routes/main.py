"""
主路由
"""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from models import db, OfficialAccount, Article, AIContent, EducationContent, WeeklyReport, CookiePool, CrawlLog, WechatContent
from core.data_store import ArticleStore
from datetime import datetime, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """首页仪表盘"""
    # 统计信息
    total_accounts = OfficialAccount.query.count()
    active_accounts = OfficialAccount.query.filter_by(is_active=True).count()
    total_articles = Article.query.count()
    total_ai_news = AIContent.query.count()
    total_cookies = CookiePool.query.filter_by(is_available=True).count()
    
    # 最近一周的数据
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_articles = Article.query.filter(Article.created_at >= week_ago).count()
    week_ai_news = AIContent.query.filter(AIContent.created_at >= week_ago).count()
    
    # 最近的重要文章
    important_articles = Article.query.filter_by(is_important=True).order_by(
        Article.created_at.desc()
    ).limit(5).all()
    
    # 最近的AI资讯
    recent_ai_news = AIContent.query.order_by(
        AIContent.created_at.desc()
    ).limit(5).all()
    
    # 最近的采集日志
    recent_logs = CrawlLog.query.order_by(
        CrawlLog.created_at.desc()
    ).limit(10).all()
    
    # 最新周报
    latest_report = WeeklyReport.query.filter_by(status='published').order_by(
        WeeklyReport.report_date.desc()
    ).first()
    
    return render_template('index.html',
                         total_accounts=total_accounts,
                         active_accounts=active_accounts,
                         total_articles=total_articles,
                         total_ai_news=total_ai_news,
                         total_cookies=total_cookies,
                         week_articles=week_articles,
                         week_ai_news=week_ai_news,
                         important_articles=important_articles,
                         recent_ai_news=recent_ai_news,
                         recent_logs=recent_logs,
                         latest_report=latest_report)

@main_bp.route('/accounts')
@login_required
def accounts():
    """公众号管理页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    pagination = OfficialAccount.query.order_by(
        OfficialAccount.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # 转换为字典列表用于JSON序列化
    accounts_list = [{
        'id': a.id,
        'name': a.name,
        'account_id': a.account_id,
        'description': a.description,
        'category': a.category,
        'is_active': a.is_active,
        'crawl_interval': a.crawl_interval,
        'last_crawl_time': a.last_crawl_time.strftime('%Y-%m-%d %H:%M') if a.last_crawl_time else None
    } for a in pagination.items]
    
    return render_template('accounts/index.html',
                         accounts=accounts_list,
                         pagination=pagination)

@main_bp.route('/articles')
@login_required
def articles():
    """文章列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    account_id = request.args.get('account_id', type=int)
    keyword = request.args.get('keyword')
    content_type = request.args.get('type', 'all')  # all, wechat, article
    
    # 查询Article表
    article_query = Article.query
    if category:
        article_query = article_query.filter(Article.category == category)
    if account_id:
        article_query = article_query.filter(Article.account_id == account_id)
    if keyword:
        article_query = article_query.filter(Article.title.contains(keyword) | Article.summary.contains(keyword))
    
    # 查询WechatContent表
    wechat_query = WechatContent.query
    if keyword:
        wechat_query = wechat_query.filter(
            WechatContent.title.contains(keyword) | 
            WechatContent.summary.contains(keyword) |
            WechatContent.content.contains(keyword)
        )
    
    # 根据类型过滤
    articles_list = []
    if content_type == 'all':
        # 合并两个表的数据
        articles_list = article_query.order_by(Article.created_at.desc()).all()
        wechat_list = wechat_query.order_by(WechatContent.created_at.desc()).all()
    elif content_type == 'wechat':
        articles_list = []
        wechat_list = wechat_query.order_by(WechatContent.created_at.desc()).all()
    else:
        articles_list = article_query.order_by(Article.created_at.desc()).all()
        wechat_list = []
    
    # 合并并排序
    all_articles = []
    for a in articles_list:
        all_articles.append({
            'id': a.id,
            'title': a.title,
            'url': a.url,
            'author': a.author,
            'summary': a.summary,
            'publish_date': a.publish_date,
            'category': a.category,
            'account_name': a.account.name if a.account else None,
            'account_id': a.account_id,
            'is_important': a.is_important,
            'created_at': a.created_at,
            'content_type': 'article'
        })
    
    for w in wechat_list:
        all_articles.append({
            'id': w.id,
            'title': w.title,
            'url': w.url,
            'author': w.author,
            'summary': w.summary,
            'publish_date': w.publish_date,
            'category': w.tags,
            'account_name': w.account_name,
            'account_id': None,
            'is_important': False,
            'created_at': w.created_at,
            'content_type': 'wechat'
        })
    
    # 按时间排序
    all_articles.sort(key=lambda x: x['created_at'] or datetime.min, reverse=True)
    
    # 分页
    total = len(all_articles)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_articles = all_articles[start:end]
    
    # 获取所有公众号用于筛选
    all_accounts = OfficialAccount.query.all()
    categories = db.session.query(Article.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('articles/index.html',
                         articles=paginated_articles,
                         pagination={'page': page, 'per_page': per_page, 'total': total, 'pages': (total + per_page - 1) // per_page},
                         all_accounts=all_accounts,
                         categories=categories,
                         current_category=category,
                         current_account_id=account_id,
                         keyword=keyword,
                         current_type=content_type)

@main_bp.route('/articles/<int:article_id>')
@login_required
def article_detail(article_id):
    """文章详情页面"""
    from flask import abort
    
    # 尝试从Article表获取
    article = Article.query.get(article_id)
    if article:
        return render_template('articles/detail.html', article=article)
    
    # 尝试从WechatContent表获取
    wechat = WechatContent.query.get(article_id)
    if wechat:
        # 将WechatContent转换为类似Article的结构
        article_dict = {
            'id': wechat.id,
            'title': wechat.title,
            'url': wechat.url,
            'author': wechat.author,
            'summary': wechat.summary,
            'content': wechat.content,
            'publish_date': wechat.publish_date,
            'category': wechat.tags,
            'account_name': wechat.account_name,
            'account_id': None,
            'is_important': False,
            'created_at': wechat.created_at,
            'content_type': 'wechat'
        }
        return render_template('articles/detail.html', article=article_dict)
    
    abort(404)

@main_bp.route('/ai-news')
@login_required
def ai_news():
    """AI资讯页面"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    keyword = request.args.get('keyword')
    sort = request.args.get('sort', 'publish_date')
    
    pagination = ArticleStore.get_ai_contents(
        page=page, per_page=per_page,
        category=category,
        keyword=keyword, sort_by=sort
    )
    
    # 获取所有分类
    categories = db.session.query(AIContent.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('ai_news/index.html',
                         ai_news=pagination.items,
                         pagination=pagination,
                         categories=categories,
                         current_category=category,
                         current_sort=sort,
                         keyword=keyword)

@main_bp.route('/education')
@login_required
def education_news():
    """教育资讯页面"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    source = request.args.get('source')
    keyword = request.args.get('keyword')
    sort = request.args.get('sort', 'publish_date')  # 默认按发布时间排序
    
    pagination = ArticleStore.get_education_contents(
        page=page, per_page=per_page, source=source, keyword=keyword, sort_by=sort
    )
    
    # 获取各来源统计
    source_stats_query = db.session.query(
        EducationContent.source,
        EducationContent.source_name,
        db.func.count(EducationContent.id).label('count')
    ).group_by(EducationContent.source, EducationContent.source_name).all()
    
    # 转换为列表
    source_stats = [
        {'source': s[0], 'source_name': s[1] or s[0], 'count': s[2]}
        for s in source_stats_query
    ]
    
    return render_template('education/index.html',
                         education_news=pagination.items,
                         pagination=pagination,
                         source_stats=source_stats,
                         current_source=source,
                         current_sort=sort,
                         keyword=keyword)

@main_bp.route('/education/<int:news_id>')
@login_required
def education_news_detail(news_id):
    """教育资讯详情页面"""
    content = EducationContent.query.get_or_404(news_id)
    # 标记为已读
    ArticleStore.toggle_education_read(news_id)
    return render_template('education/detail.html', content=content)

@main_bp.route('/reports')
@login_required
def reports():
    """周报列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    pagination = WeeklyReport.query.order_by(
        WeeklyReport.report_date.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('reports/index.html',
                         reports=pagination.items,
                         pagination=pagination)

@main_bp.route('/reports/<int:report_id>')
@login_required
def report_detail(report_id):
    """周报详情页面"""
    report = WeeklyReport.query.get_or_404(report_id)
    return render_template('reports/detail.html', report=report)

@main_bp.route('/reports/generate', methods=['GET', 'POST'])
@login_required
def generate_report():
    """生成周报页面"""
    from core.report_generator import WeeklyReportGenerator
    
    if request.method == 'POST':
        generator = WeeklyReportGenerator()
        report = generator.generate_report()
        return redirect(url_for('main.report_detail', report_id=report.id))
    
    return render_template('reports/generate.html')

@main_bp.route('/crawl')
@login_required
def crawl():
    """文章采集页面"""
    accounts = OfficialAccount.query.filter_by(is_active=True).all()
    cookies = CookiePool.query.filter_by(is_available=True).all()
    
    # 提取wxuin用于显示
    import json
    cookies_data = []
    for c in cookies:
        try:
            cookie_dict = json.loads(c.cookie_data) if isinstance(c.cookie_data, str) else c.cookie_data
            wxuin = cookie_dict.get('wxuin', '') if cookie_dict else ''
        except:
            wxuin = ''
        cookies_data.append({
            'id': c.id,
            'name': c.name,
            'is_available': c.is_available,
            'wxuin': wxuin
        })
    
    return render_template('crawl/index.html', 
                         accounts=accounts,
                         cookies=cookies_data)

@main_bp.route('/cookies')
@login_required
def cookies():
    """Cookie池管理页面"""
    cookies_list = CookiePool.query.order_by(
        CookiePool.created_at.desc()
    ).all()
    
    # 转换为字典列表
    cookies_data = [{
        'id': c.id,
        'name': c.name,
        'is_available': c.is_available,
        'failure_count': c.failure_count,
        'user_agent': c.user_agent,
        'last_used': c.last_used.strftime('%Y-%m-%d %H:%M') if c.last_used else None,
        'expires_at': c.expires_at.strftime('%Y-%m-%d %H:%M') if c.expires_at else None
    } for c in cookies_list]
    
    return render_template('cookies/index.html', cookies=cookies_data)

@main_bp.route('/logs')
@login_required
def logs():
    """采集日志页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    pagination = CrawlLog.query.order_by(
        CrawlLog.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('logs/index.html',
                         logs=pagination.items,
                         pagination=pagination)

@main_bp.route('/settings')
@login_required
def settings():
    """设置页面"""
    return render_template('settings/index.html')

"""
API路由
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, AIContent, EducationContent, WechatContent, CookiePool, WeeklyReport, NewsSource, CrawlLog, OfficialAccount, Article
from core.data_store import ArticleStore, CrawlManager, CrawlProgressManager
from core.cookie_manager import CookieManager
from core.report_generator import WeeklyReportGenerator
from datetime import datetime, timedelta
import json

api_bp = Blueprint('api', __name__)

# ==================== AI资讯API ====================

@api_bp.route('/ai-news', methods=['GET'])
@login_required
def get_ai_news():
    """获取AI资讯列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = ArticleStore.get_ai_contents(
        page=page,
        per_page=per_page,
        source=request.args.get('source'),
        category=request.args.get('category'),
        keyword=request.args.get('keyword')
    )
    
    return jsonify({
        'code': 0,
        'data': {
            'items': [{
                'id': n.id,
                'title': n.title,
                'url': n.url,
                'source': n.source,
                'summary': n.summary,
                'publish_date': n.publish_date.strftime('%Y-%m-%d') if n.publish_date else None,
                'category': n.category,
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else None
            } for n in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        }
    })

@api_bp.route('/ai-news/crawl', methods=['POST'])
@login_required
def crawl_ai_news():
    """爬取AI资讯"""
    source = None
    try:
        json_data = request.get_json(silent=True)
        if json_data:
            source = json_data.get('source')
    except Exception:
        pass
    
    manager = CrawlManager()
    result = manager.crawl_ai_news(source=source or 'aihot', take=10)
    
    return jsonify({
        'code': 0 if result['success'] else 1,
        'data': result
    })

# ==================== Cookie池API ====================

@api_bp.route('/cookies/parse', methods=['POST'])
@login_required
def parse_cookie():
    """解析Cookie字符串"""
    data = request.json
    
    if not data or 'cookie_string' not in data:
        return jsonify({'code': 1, 'message': '请提供cookie_string参数'})
    
    try:
        analysis = CookieManager.analyze_cookie(data['cookie_string'])
        return jsonify({
            'code': 0,
            'data': analysis
        })
    except ValueError as e:
        return jsonify({'code': 1, 'message': str(e)})
    except Exception as e:
        return jsonify({'code': 1, 'message': f'解析失败: {str(e)}'})

@api_bp.route('/cookies/import', methods=['POST'])
@login_required
def import_cookie():
    """导入Cookie"""
    data = request.json
    
    if not data or 'cookie_string' not in data:
        return jsonify({'code': 1, 'message': '请提供cookie_string参数'})
    
    try:
        analysis = CookieManager.analyze_cookie(data['cookie_string'])
        
        cookie = CookieManager.add_cookie(
            name=data.get('name') or analysis['suggested_name'],
            cookie_data=analysis['cookies'],
            user_agent=data.get('user_agent'),
            expires_at=None
        )
        
        return jsonify({
            'code': 0,
            'data': {
                'id': cookie.id,
                'name': cookie.name,
                'analysis': {
                    'wxuin': analysis['wxuin'],
                    'bizuin': analysis['bizuin'],
                    'total_count': analysis['total_count']
                },
                'message': 'Cookie导入成功'
            }
        })
    except ValueError as e:
        return jsonify({'code': 1, 'message': str(e)})
    except Exception as e:
        return jsonify({'code': 1, 'message': f'导入失败: {str(e)}'})

@api_bp.route('/cookies', methods=['GET'])
@login_required
def get_cookies():
    """获取Cookie列表"""
    cookies = CookieManager.get_all_cookies()
    return jsonify({
        'code': 0,
        'data': [{
            'id': c.id,
            'name': c.name,
            'is_available': c.is_available,
            'failure_count': c.failure_count,
            'last_used': c.last_used.strftime('%Y-%m-%d %H:%M') if c.last_used else None,
            'expires_at': c.expires_at.strftime('%Y-%m-%d %H:%M') if c.expires_at else None
        } for c in cookies]
    })

@api_bp.route('/cookies', methods=['POST'])
@login_required
def add_cookie():
    """添加Cookie"""
    data = request.json
    expires_at = None
    if data.get('expires_at'):
        expires_at = datetime.fromisoformat(data['expires_at'])
    
    cookie = CookieManager.add_cookie(
        name=data.get('name', 'unnamed'),
        cookie_data=data.get('cookie_data', {}),
        user_agent=data.get('user_agent'),
        expires_at=expires_at
    )
    
    return jsonify({
        'code': 0,
        'data': {'id': cookie.id, 'message': '添加成功'}
    })

@api_bp.route('/cookies/<int:cookie_id>', methods=['PUT'])
@login_required
def update_cookie(cookie_id):
    """更新Cookie"""
    data = request.json
    cookie = CookieManager.update_cookie(
        cookie_id,
        name=data.get('name'),
        cookie_data=data.get('cookie_data'),
        user_agent=data.get('user_agent'),
        is_available=data.get('is_available')
    )
    
    if cookie:
        return jsonify({'code': 0, 'message': '更新成功'})
    return jsonify({'code': 1, 'message': 'Cookie不存在'})

@api_bp.route('/cookies/<int:cookie_id>', methods=['DELETE'])
@login_required
def delete_cookie(cookie_id):
    """删除Cookie"""
    CookieManager.delete_cookie(cookie_id)
    return jsonify({'code': 0, 'message': '删除成功'})

# ==================== 周报API ====================

@api_bp.route('/reports', methods=['GET'])
@login_required
def get_reports():
    """获取周报列表"""
    reports = WeeklyReportGenerator.get_reports()
    return jsonify({
        'code': 0,
        'data': [{
            'id': r.id,
            'title': r.title,
            'report_date': r.report_date.strftime('%Y-%m-%d'),
            'period_start': r.period_start.strftime('%Y-%m-%d'),
            'period_end': r.period_end.strftime('%Y-%m-%d'),
            'article_count': r.article_count,
            'ai_news_count': r.ai_news_count,
            'status': r.status
        } for r in reports]
    })

@api_bp.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    """生成周报"""
    data = request.json or {}
    
    start_date = None
    end_date = None
    if data.get('start_date'):
        start_date = datetime.fromisoformat(data['start_date'])
    if data.get('end_date'):
        end_date = datetime.fromisoformat(data['end_date'])
    
    generator = WeeklyReportGenerator()
    report = generator.generate_report(start_date, end_date)
    
    return jsonify({
        'code': 0,
        'data': {
            'id': report.id,
            'title': report.title
        }
    })

@api_bp.route('/reports/<int:report_id>/publish', methods=['POST'])
@login_required
def publish_report(report_id):
    """发布周报"""
    report = WeeklyReportGenerator.publish_report(report_id)
    return jsonify({
        'code': 0,
        'data': {'status': report.status if report else None}
    })

@api_bp.route('/reports/<int:report_id>/html', methods=['GET'])
@login_required
def get_report_html(report_id):
    """获取周报HTML"""
    report = WeeklyReport.query.get_or_404(report_id)
    html = WeeklyReportGenerator.convert_to_html(report.content)
    return jsonify({'code': 0, 'data': {'html': html}})

# ==================== 教育资讯API ====================

@api_bp.route('/education/news', methods=['GET'])
@login_required
def get_education_news():
    """获取教育资讯列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    source = request.args.get('source')
    keyword = request.args.get('keyword')
    
    pagination = ArticleStore.get_education_contents(
        page=page, per_page=per_page, source=source, keyword=keyword
    )
    
    return jsonify({
        'code': 0,
        'data': {
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        }
    })

@api_bp.route('/education/news/<int:news_id>', methods=['GET'])
@login_required
def get_education_news_detail(news_id):
    """获取教育资讯详情"""
    content = EducationContent.query.get_or_404(news_id)
    ArticleStore.toggle_education_read(news_id)
    return jsonify({
        'code': 0,
        'data': content.to_dict()
    })

@api_bp.route('/education/news/<int:news_id>/favorite', methods=['POST'])
@login_required
def toggle_education_favorite(news_id):
    """切换收藏状态"""
    content = ArticleStore.toggle_education_favorite(news_id)
    return jsonify({
        'code': 0,
        'data': {
            'id': content.id,
            'is_favorite': content.is_favorite
        }
    })

@api_bp.route('/education/news/<int:news_id>/read', methods=['POST'])
@login_required
def mark_education_read(news_id):
    """标记已读"""
    content = ArticleStore.toggle_education_read(news_id)
    return jsonify({
        'code': 0,
        'data': {
            'id': content.id,
            'is_read': content.is_read
        }
    })

@api_bp.route('/education/news/<int:news_id>', methods=['DELETE'])
@login_required
def delete_education_news(news_id):
    """删除教育资讯"""
    success = ArticleStore.delete_education_content(news_id)
    return jsonify({
        'code': 0 if success else 1,
        'message': '删除成功' if success else '删除失败'
    })

@api_bp.route('/education/crawl', methods=['POST'])
@login_required
def crawl_education_news():
    """采集教育资讯"""
    try:
        data = request.get_json(silent=True) or {}
    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'请求解析失败: {str(e)}'
        }), 400
    
    source = data.get('source', 'jiemodui')
    days = data.get('days', 7)
    
    try:
        manager = CrawlManager()
        result = manager.crawl_education_news(source, days=days)
        
        return jsonify({
            'code': 0 if result.get('success') else 1,
            'data': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 1,
            'message': f'采集失败: {str(e)}'
        }), 500

@api_bp.route('/education/sources', methods=['GET'])
@login_required
def get_education_sources():
    """获取教育资讯来源"""
    sources = db.session.query(
        EducationContent.source, 
        EducationContent.source_name,
        db.func.count(EducationContent.id).label('count')
    ).group_by(EducationContent.source, EducationContent.source_name).all()
    
    return jsonify({
        'code': 0,
        'data': [{'source': s[0], 'name': s[1], 'count': s[2]} for s in sources]
    })

# ==================== 采集进度API ====================

@api_bp.route('/crawl/progress', methods=['GET'])
@login_required
def get_crawl_progress():
    """获取爬取进度"""
    source = request.args.get('source', 'duozhi')
    progress = CrawlProgressManager.get_progress(source)
    return jsonify({
        'code': 0,
        'data': progress
    })

@api_bp.route('/crawl/progress/reset', methods=['POST'])
@login_required
def reset_crawl_progress():
    """重置爬取进度"""
    data = request.get_json() or {}
    source = data.get('source', 'duozhi')
    start_id = data.get('start_id', 18450)
    
    success = CrawlProgressManager.reset_progress(source, start_id)
    
    if success:
        return jsonify({
            'code': 0,
            'message': f'已重置{source}爬取进度，将从ID {start_id}重新开始',
            'data': {'source': source, 'start_id': start_id}
        })
    else:
        return jsonify({
            'code': 1,
            'message': '重置失败'
        })

# ==================== 采集日志API ====================

@api_bp.route('/crawl/logs', methods=['GET'])
@login_required
def get_crawl_logs():
    """获取采集日志"""
    limit = request.args.get('limit', 50, type=int)
    manager = CrawlManager()
    logs = manager.get_crawl_logs(limit=limit)
    
    return jsonify({
        'code': 0,
        'data': [{
            'id': log.id,
            'source': log.source,
            'status': log.status,
            'message': log.message,
            'articles_count': log.articles_count,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else None
        } for log in logs]
    })

# ==================== 数据统计API ====================

@api_bp.route('/stats/dashboard', methods=['GET'])
@login_required
def get_dashboard_stats():
    """获取仪表盘统计"""
    return jsonify({
        'code': 0,
        'data': {
            'total_ai_news': AIContent.query.count(),
            'total_education_news': EducationContent.query.count(),
            'available_cookies': CookiePool.query.filter_by(is_available=True).count(),
            'published_reports': WeeklyReport.query.filter_by(status='published').count()
        }
    })

# ==================== 资讯来源API ====================

@api_bp.route('/sources', methods=['GET'])
@login_required
def get_sources():
    """获取资讯来源列表"""
    sources = NewsSource.query.all()
    return jsonify({
        'code': 0,
        'data': [{
            'id': s.id,
            'name': s.name,
            'url': s.url,
            'source_type': s.source_type,
            'last_crawl': s.last_crawl.strftime('%Y-%m-%d %H:%M') if s.last_crawl else None
        } for s in sources]
    })


# ==================== 公众号管理API ====================

@api_bp.route('/wechat/accounts', methods=['GET'])
@login_required
def get_wechat_accounts():
    """获取公众号列表"""
    accounts = OfficialAccount.query.order_by(OfficialAccount.created_at.desc()).all()
    return jsonify({
        'code': 0,
        'data': [acc.to_dict() for acc in accounts]
    })

@api_bp.route('/wechat/accounts', methods=['POST'])
@login_required
def add_wechat_account():
    """添加公众号"""
    data = request.json
    
    if not data or 'name' not in data or 'account_id' not in data:
        return jsonify({'code': 1, 'message': '请提供公众号名称和ID'})
    
    # 检查是否已存在
    existing = OfficialAccount.query.filter_by(account_id=data['account_id']).first()
    if existing:
        return jsonify({'code': 1, 'message': '该公众号ID已存在'})
    
    account = OfficialAccount(
        name=data['name'],
        account_id=data['account_id'],
        description=data.get('description'),
        category=data.get('category', '行业动态'),
        is_active=data.get('is_active', True),
        crawl_interval=data.get('crawl_interval', 24)
    )
    
    db.session.add(account)
    db.session.commit()
    
    return jsonify({
        'code': 0,
        'data': account.to_dict(),
        'message': '添加成功'
    })

@api_bp.route('/wechat/accounts/<int:account_id>', methods=['PUT'])
@login_required
def update_wechat_account(account_id):
    """更新公众号"""
    account = OfficialAccount.query.get_or_404(account_id)
    data = request.json
    
    if 'name' in data:
        account.name = data['name']
    if 'description' in data:
        account.description = data['description']
    if 'category' in data:
        account.category = data['category']
    if 'is_active' in data:
        account.is_active = data['is_active']
    if 'crawl_interval' in data:
        account.crawl_interval = data['crawl_interval']
    
    db.session.commit()
    
    return jsonify({
        'code': 0,
        'data': account.to_dict(),
        'message': '更新成功'
    })

@api_bp.route('/wechat/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def delete_wechat_account(account_id):
    """删除公众号"""
    account = OfficialAccount.query.get_or_404(account_id)
    db.session.delete(account)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})

# ==================== 公众号文章API ====================

@api_bp.route('/wechat/articles', methods=['GET'])
@login_required
def get_wechat_articles():
    """获取公众号文章列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    account_name = request.args.get('account_name')
    keyword = request.args.get('keyword')
    
    pagination = ArticleStore.get_wechat_contents(
        page=page, per_page=per_page,
        account_name=account_name, keyword=keyword
    )
    
    return jsonify({
        'code': 0,
        'data': {
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        }
    })

@api_bp.route('/wechat/articles/<int:article_id>', methods=['GET'])
@login_required
def get_wechat_article_detail(article_id):
    """获取公众号文章详情"""
    content = WechatContent.query.get_or_404(article_id)
    return jsonify({
        'code': 0,
        'data': content.to_dict()
    })

@api_bp.route('/wechat/articles/<int:article_id>/favorite', methods=['POST'])
@login_required
def toggle_wechat_favorite(article_id):
    """切换公众号文章收藏状态"""
    content = ArticleStore.toggle_wechat_favorite(article_id)
    return jsonify({
        'code': 0,
        'data': {
            'id': content.id,
            'is_favorite': content.is_favorite
        }
    })

@api_bp.route('/wechat/articles/<int:article_id>', methods=['DELETE'])
@login_required
def delete_wechat_article(article_id):
    """删除公众号文章"""
    success = ArticleStore.delete_wechat_content(article_id)
    return jsonify({
        'code': 0 if success else 1,
        'message': '删除成功' if success else '删除失败'
    })

@api_bp.route('/wechat/crawl', methods=['POST'])
@login_required
def crawl_wechat_article():
    """爬取单个公众号文章"""
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({'code': 1, 'message': '请提供文章URL'})
    
    manager = CrawlManager()
    result = manager.crawl_wechat_article(
        url=data['url'],
        account_name=data.get('account_name'),
        account_id=data.get('account_id')
    )
    
    return jsonify({
        'code': 0 if result.get('success') else 1,
        'data': result,
        'message': result.get('message', '')
    })

@api_bp.route('/wechat/test-spider', methods=['POST'])
@login_required
def test_wechat_spider():
    """测试公众号爬虫"""
    from core.scraper import WechatScraper
    from core.cookie_manager import CookieManager
    
    data = request.json
    url = data.get('url') if data else None
    
    if not url:
        return jsonify({'code': 1, 'message': '请提供文章URL'})
    
    try:
        cookie_manager = CookieManager()
        scraper = WechatScraper(cookie_manager=cookie_manager)
        result = scraper.parse_article_detail(url)
        
        return jsonify({
            'code': 0,
            'data': {
                'success': result.get('success', False),
                'title': result.get('title', ''),
                'author': result.get('author', ''),
                'summary': result.get('summary', ''),
                'publish_time': result.get('publish_time'),
                'images_count': len(result.get('images', []))
            }
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'爬取失败: {str(e)}'
        })

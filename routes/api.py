"""
API路由
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, AIContent, EducationContent, WechatContent, CookiePool, WeeklyReport, NewsSource, CrawlLog, OfficialAccount, Article, WechatCredential, CrawlTaskConfig, LeiduiContent
from core.data_store import ArticleStore, CrawlManager, CrawlProgressManager
from core.cookie_manager import CookieManager
from core.report_generator import WeeklyReportGenerator
from core.wechat_scraper import WechatArticleSpider
from core.decorators import write_required, require_permission
from datetime import datetime, timedelta
import pytz
import json
import time
import random
import requests

api_bp = Blueprint('api', __name__)

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

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
@require_permission('write_ai_news')
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
@require_permission('manage_crawl')
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
@require_permission('manage_crawl')
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
@require_permission('manage_crawl')
def add_cookie():
    """添加Cookie"""
    data = request.json
    if not data:
        return jsonify({'code': 1, 'message': '请求数据为空或格式错误'})
    
    if not data.get('name'):
        return jsonify({'code': 1, 'message': '请提供Cookie名称'})
    if not data.get('cookie_data'):
        return jsonify({'code': 1, 'message': '请提供Cookie数据'})
    
    expires_at = None
    if data.get('expires_at'):
        try:
            expires_at = datetime.fromisoformat(data['expires_at'])
        except (ValueError, TypeError):
            pass
    
    try:
        cookie = CookieManager.add_cookie(
            name=data['name'],
            cookie_data=data['cookie_data'],
            user_agent=data.get('user_agent'),
            expires_at=expires_at
        )
        
        return jsonify({
            'code': 0,
            'data': {'id': cookie.id, 'message': '添加成功'}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 1, 'message': f'添加失败: {str(e)}'})

@api_bp.route('/cookies/<int:cookie_id>', methods=['PUT'])
@require_permission('manage_crawl')
def update_cookie(cookie_id):
    """更新Cookie"""
    data = request.json
    if not data:
        return jsonify({'code': 1, 'message': '请求数据为空或格式错误'})
    
    try:
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
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 1, 'message': f'更新失败: {str(e)}'})

@api_bp.route('/cookies/<int:cookie_id>', methods=['DELETE'])
@require_permission('manage_crawl')
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
@require_permission('write_reports')
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
@require_permission('write_reports')
def publish_report(report_id):
    """发布周报"""
    report = WeeklyReportGenerator.publish_report(report_id)
    return jsonify({
        'code': 0,
        'data': {'status': report.status if report else None}
    })

@api_bp.route('/reports/<int:report_id>', methods=['PUT'])
@require_permission('write_reports')
def update_report(report_id):
    """更新周报"""
    report = WeeklyReport.query.get_or_404(report_id)
    data = request.json

    if data.get('title'):
        report.title = data['title']
    if 'content' in data:
        report.content = data['content']
    if 'period_start' in data and data['period_start']:
        report.period_start = datetime.strptime(data['period_start'], '%Y-%m-%d').date()
    if 'period_end' in data and data['period_end']:
        report.period_end = datetime.strptime(data['period_end'], '%Y-%m-%d').date()
    if 'article_count' in data:
        report.article_count = data['article_count']
    if 'ai_news_count' in data:
        report.ai_news_count = data['ai_news_count']
    if 'status' in data:
        report.status = data['status']

    db.session.commit()
    return jsonify({
        'code': 0,
        'data': {
            'id': report.id,
            'title': report.title,
            'status': report.status
        },
        'message': '更新成功'
    })

@api_bp.route('/reports/<int:report_id>', methods=['DELETE'])
@require_permission('write_reports')
def delete_report(report_id):
    """删除周报"""
    report = WeeklyReport.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    return jsonify({
        'code': 0,
        'message': '删除成功'
    })

@api_bp.route('/reports/<int:report_id>/html', methods=['GET'])
@login_required
def get_report_html(report_id):
    """获取周报HTML"""
    report = WeeklyReport.query.get_or_404(report_id)
    return jsonify({'code': 0, 'data': {'html': report.content}})

@api_bp.route('/reports/<int:report_id>/export', methods=['GET'])
@login_required
def export_report(report_id):
    """导出周报"""
    report = WeeklyReport.query.get_or_404(report_id)
    export_type = request.args.get('type', 'html')  # html, markdown

    if export_type == 'markdown':
        # 将HTML内容转为纯文本作为Markdown导出
        text_content = WeeklyReportGenerator.convert_to_markdown(report.content)
        return jsonify({
            'code': 0,
            'data': {
                'content': text_content,
                'filename': f'{report.title}.md'
            }
        })
    else:
        # HTML格式 - content 本身就是HTML
        return jsonify({
            'code': 0,
            'data': {
                'html': report.content,
                'title': report.title,
                'filename': f'{report.title}.html'
            }
        })

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
@require_permission('write_education')
def delete_education_news(news_id):
    """删除教育资讯"""
    success = ArticleStore.delete_education_content(news_id)
    return jsonify({
        'code': 0 if success else 1,
        'message': '删除成功' if success else '删除失败'
    })

@api_bp.route('/education/crawl', methods=['POST'])
@require_permission('write_education')
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
        
        # 采集全部来源
        if source == 'all':
            sources = ['jiemodui', 'duozhi', 'cctv']
            source_names = {'jiemodui': '芥末堆', 'duozhi': '多知网', 'cctv': '央视网'}
            total_saved = 0
            per_source_result = {}
            
            for src in sources:
                try:
                    result = manager.crawl_education_news(src, days=days)
                    if result.get('success'):
                        saved = result.get('saved_count', 0)
                        total_saved += saved
                        per_source_result[src] = {'name': source_names.get(src, src), 'saved': saved, 'status': 'success'}
                    else:
                        per_source_result[src] = {'name': source_names.get(src, src), 'saved': 0, 'status': 'failed', 'error': result.get('message', '')}
                except Exception as e:
                    per_source_result[src] = {'name': source_names.get(src, src), 'saved': 0, 'status': 'error', 'error': str(e)}
                    print(f"采集 {source_names.get(src, src)} 失败: {e}")
            
            # 构建详细消息
            parts = []
            for src, info in per_source_result.items():
                if info['status'] == 'success':
                    parts.append(f"{info['name']}: +{info['saved']}条")
                else:
                    parts.append(f"{info['name']}: 失败({info.get('error', '')})")
            message = f"采集完成！共保存 {total_saved} 条新资讯\n" + " | ".join(parts)
            
            return jsonify({
                'code': 0,
                'data': {
                    'success': True,
                    'saved_count': total_saved,
                    'per_source': per_source_result,
                    'message': message
                }
            })
        else:
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

# ==================== 雷递网资讯API ====================

@api_bp.route('/leidui/news', methods=['GET'])
@login_required
def get_leidui_news():
    """获取雷递网资讯列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    keyword = request.args.get('keyword')
    
    pagination = ArticleStore.get_leidui_contents(
        page=page, per_page=per_page, category=category, keyword=keyword
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

@api_bp.route('/leidui/news/<int:news_id>', methods=['GET'])
@login_required
def get_leidui_news_detail(news_id):
    """获取雷递网资讯详情"""
    content = LeiduiContent.query.get_or_404(news_id)
    ArticleStore.toggle_leidui_read(news_id)
    return jsonify({
        'code': 0,
        'data': content.to_dict()
    })

@api_bp.route('/leidui/news/<int:news_id>/favorite', methods=['POST'])
@login_required
def toggle_leidui_favorite(news_id):
    """切换收藏状态"""
    content = ArticleStore.toggle_leidui_favorite(news_id)
    return jsonify({
        'code': 0,
        'data': {
            'id': content.id,
            'is_favorite': content.is_favorite
        }
    })

@api_bp.route('/leidui/news/<int:news_id>', methods=['DELETE'])
@require_permission('write_leidui')
def delete_leidui_news(news_id):
    """删除雷递网资讯"""
    success = ArticleStore.delete_leidui_content(news_id)
    return jsonify({
        'code': 0 if success else 1,
        'message': '删除成功' if success else '删除失败'
    })

@api_bp.route('/leidui/crawl', methods=['POST'])
@require_permission('write_leidui')
def crawl_leidui_news():
    """采集雷递网最新资讯（首页，最多10篇）"""
    try:
        manager = CrawlManager()
        result = manager.crawl_leidui_news()
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
@require_permission('manage_crawl')
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
@require_permission('write_articles')
def add_wechat_account():
    """添加公众号"""
    data = request.json

    if not data or 'name' not in data:
        return jsonify({'code': 1, 'message': '请提供公众号名称'})

    biz = data.get('biz', '').strip()
    if not biz:
        return jsonify({'code': 1, 'message': '请提供Biz标识'})

    # 检查biz是否已存在
    existing = OfficialAccount.query.filter_by(biz=biz).first()
    if existing:
        return jsonify({'code': 1, 'message': '该Biz已存在'})

    account = OfficialAccount(
        name=data['name'].strip(),
        account_id=data.get('account_id', biz).strip(),
        biz=biz,
        description=data.get('description', '').strip() if data.get('description') else None,
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
@require_permission('write_articles')
def update_wechat_account(account_id):
    """更新公众号"""
    account = OfficialAccount.query.get_or_404(account_id)
    data = request.json

    if 'name' in data:
        account.name = data['name']
    if 'biz' in data and data['biz']:
        # 检查新biz是否与其他公众号冲突
        existing = OfficialAccount.query.filter(
            OfficialAccount.biz == data['biz'],
            OfficialAccount.id != account_id
        ).first()
        if existing:
            return jsonify({'code': 1, 'message': '该Biz已被其他公众号使用'})
        account.biz = data['biz']
    if 'account_id' in data:
        account.account_id = data['account_id']
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
@require_permission('write_articles')
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
@require_permission('write_articles')
def delete_wechat_article(article_id):
    """删除公众号文章"""
    success = ArticleStore.delete_wechat_content(article_id)
    return jsonify({
        'code': 0 if success else 1,
        'message': '删除成功' if success else '删除失败'
    })

@api_bp.route('/wechat/crawl', methods=['POST'])
@require_permission('manage_crawl')
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
@require_permission('manage_crawl')
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

@api_bp.route('/crawl/batch', methods=['POST'])
@require_permission('manage_crawl')
def crawl_wechat_account():
    """批量采集公众号文章"""
    data = request.json
    
    if not data:
        return jsonify({'code': 1, 'message': '请提供参数'})
    
    account_id = data.get('account_id')
    count = data.get('count', 20)
    cookie_id = data.get('cookie_id')
    
    # 如果没有指定公众号ID，返回错误
    if not account_id:
        return jsonify({'code': 1, 'message': '请选择要采集的公众号'})
    
    try:
        # 将 account_id 转换为整数
        account_id = int(account_id)
        count = int(count)
    except ValueError:
        return jsonify({'code': 1, 'message': '参数格式错误'})
    
    try:
        manager = CrawlManager()
        result = manager.crawl_account(account_id, max_articles=count)
        
        return jsonify({
            'code': 0 if result.get('success') else 1,
            'data': result,
            'message': result.get('message', '')
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 1,
            'message': f'批量采集失败: {str(e)}'
        }), 500

# ==================== 微信公众号凭证API ====================

@api_bp.route('/wechat/credentials', methods=['GET'])
@login_required
def get_wechat_credentials():
    """获取微信凭证列表"""
    credentials = WechatCredential.query.order_by(WechatCredential.is_primary.desc(), WechatCredential.created_at.desc()).all()
    return jsonify({
        'code': 0,
        'data': [c.to_dict() for c in credentials]
    })

@api_bp.route('/wechat/credentials', methods=['POST'])
@require_permission('manage_crawl')
def add_wechat_credential():
    """添加微信凭证"""
    data = request.json

    if not data or 'name' not in data or 'cookie' not in data:
        return jsonify({'code': 1, 'message': '请提供凭证名称和Cookie'})

    # 检查是否设置为主凭证
    if data.get('is_primary', False):
        # 取消其他主凭证
        WechatCredential.query.update({'is_primary': False})

    credential = WechatCredential(
        name=data['name'],
        cookie=data['cookie'],
        token=data.get('token'),
        user_agent=data.get('user_agent'),
        is_active=data.get('is_active', True),
        is_primary=data.get('is_primary', False)
    )

    db.session.add(credential)
    db.session.commit()

    return jsonify({
        'code': 0,
        'data': credential.to_dict(),
        'message': '凭证添加成功'
    })

@api_bp.route('/wechat/credentials/<int:credential_id>', methods=['PUT'])
@require_permission('manage_crawl')
def update_wechat_credential(credential_id):
    """更新微信凭证"""
    credential = WechatCredential.query.get_or_404(credential_id)
    data = request.json

    if 'name' in data:
        credential.name = data['name']
    if 'cookie' in data:
        credential.cookie = data['cookie']
    if 'token' in data:
        credential.token = data['token']
    if 'user_agent' in data:
        credential.user_agent = data['user_agent']
    if 'is_active' in data:
        credential.is_active = data['is_active']
    if 'is_primary' in data and data['is_primary']:
        # 取消其他主凭证
        WechatCredential.query.filter(WechatCredential.id != credential_id).update({'is_primary': False})
        credential.is_primary = True

    credential.updated_at = datetime.now(BEIJING_TZ)
    db.session.commit()

    return jsonify({
        'code': 0,
        'data': credential.to_dict(),
        'message': '更新成功'
    })

@api_bp.route('/wechat/credentials/<int:credential_id>', methods=['DELETE'])
@require_permission('manage_crawl')
def delete_wechat_credential(credential_id):
    """删除微信凭证"""
    credential = WechatCredential.query.get_or_404(credential_id)
    db.session.delete(credential)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})

@api_bp.route('/wechat/credentials/<int:credential_id>/set-primary', methods=['POST'])
@require_permission('manage_crawl')
def set_primary_credential(credential_id):
    """设置为主凭证"""
    credential = WechatCredential.query.get_or_404(credential_id)

    # 取消其他主凭证
    WechatCredential.query.update({'is_primary': False})

    credential.is_primary = True
    credential.updated_at = datetime.now(BEIJING_TZ)
    db.session.commit()

    return jsonify({
        'code': 0,
        'data': credential.to_dict(),
        'message': '已设置为主凭证'
    })

# ==================== 公众号Biz管理API ====================

@api_bp.route('/wechat/accounts-by-biz', methods=['POST'])
@require_permission('write_articles')
def add_account_by_biz():
    """通过biz添加公众号"""
    data = request.json

    if not data or 'name' not in data or 'biz' not in data:
        return jsonify({'code': 1, 'message': '请提供公众号名称和biz'})

    # 检查biz是否已存在
    existing = OfficialAccount.query.filter_by(biz=data['biz']).first()
    if existing:
        return jsonify({'code': 1, 'message': '该biz已存在'})

    account = OfficialAccount(
        name=data['name'],
        account_id=data.get('account_id') or data['biz'],  # 使用biz作为account_id
        biz=data['biz'],
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

# ==================== 批量采集API ====================

@api_bp.route('/wechat/batch-crawl', methods=['POST'])
@require_permission('manage_crawl')
def batch_crawl_wechat():
    """
    批量采集公众号文章（使用profile_ext接口）

    请求参数：
    - account_ids: 要采集的公众号ID列表（可选，不传则采集所有活跃公众号）
    - count_per_account: 每个公众号采集的文章数量（默认10）
    - credential_id: 使用的凭证ID（可选，不传则使用主凭证）
    """
    data = request.json or {}

    account_ids = data.get('account_ids')
    count_per_account = data.get('count_per_account', 10)
    credential_id = data.get('credential_id')

    # 获取凭证
    cookie = None
    token = None
    if credential_id:
        cred = WechatCredential.query.get(credential_id)
        if cred:
            cookie = cred.cookie
            token = cred.token
            cred.last_used = datetime.now(BEIJING_TZ)
            db.session.commit()
    else:
        # 使用主凭证
        cred = WechatCredential.query.filter_by(is_primary=True, is_active=True).first()
        if cred:
            cookie = cred.cookie
            token = cred.token
            cred.last_used = datetime.now(BEIJING_TZ)
            db.session.commit()
        else:
            # 使用第一个可用凭证
            cred = WechatCredential.query.filter_by(is_active=True).first()
            if cred:
                cookie = cred.cookie
                token = cred.token
                cred.last_used = datetime.now(BEIJING_TZ)
                db.session.commit()

    if not cookie:
        return jsonify({
            'code': 1,
            'message': '请先添加微信凭证（Cookie）'
        })

    # 获取要采集的公众号
    if account_ids:
        accounts = OfficialAccount.query.filter(
            OfficialAccount.id.in_(account_ids),
            OfficialAccount.is_active == True
        ).all()
    else:
        accounts = OfficialAccount.query.filter_by(is_active=True).all()

    if not accounts:
        return jsonify({
            'code': 1,
            'message': '没有找到要采集的公众号'
        })

    spider = WechatArticleSpider()
    total_articles = 0
    results = []
    errors = []

    print(f"[API] 开始批量采集 {len(accounts)} 个公众号...")

    for i, account in enumerate(accounts):
        print(f"[API] 采集进度: {i+1}/{len(accounts)} - {account.name}")

        try:
            # 使用biz获取文章列表
            articles = spider.fetch_articles_by_biz(account.biz, cookie, count_per_account)

            # 保存文章到数据库
            saved_count = 0
            for article_data in articles:
                # 检查是否已存在
                existing = WechatContent.query.filter_by(url=article_data.get('url', '')).first()
                if existing:
                    continue

                content = WechatContent(
                    title=article_data.get('title', '无标题'),
                    url=article_data.get('url', ''),
                    account_name=account.name,
                    account_id=account.biz,
                    author=article_data.get('author', ''),
                    summary=article_data.get('digest', ''),
                    cover_image=article_data.get('cover', ''),
                    publish_date=article_data.get('publish_time')
                )
                db.session.add(content)
                saved_count += 1

            db.session.commit()

            # 更新公众号采集时间
            account.last_crawl_time = datetime.now(BEIJING_TZ)

            results.append({
                'account_id': account.id,
                'account_name': account.name,
                'fetched': len(articles),
                'saved': saved_count
            })
            total_articles += saved_count

        except Exception as e:
            import traceback
            print(f"[API] {account.name} 采集失败: {e}")
            traceback.print_exc()
            errors.append({
                'account_id': account.id,
                'account_name': account.name,
                'error': str(e)
            })

        # 避免请求过快
        if i < len(accounts) - 1:
            time.sleep(1)

    db.session.commit()

    return jsonify({
        'code': 0,
        'data': {
            'total_accounts': len(accounts),
            'total_articles': total_articles,
            'results': results,
            'errors': errors
        },
        'message': f'采集完成，共 {total_articles} 篇文章'
    })

@api_bp.route('/wechat/test-credential', methods=['POST'])
@require_permission('manage_crawl')
def test_wechat_credential():
    """测试微信凭证是否有效"""
    data = request.json

    if not data or 'biz' not in data:
        return jsonify({'code': 1, 'message': '请提供biz参数'})

    biz = data['biz']
    cookie = data.get('cookie')

    # 如果没有提供cookie，尝试使用主凭证
    if not cookie:
        cred = WechatCredential.query.filter_by(is_primary=True, is_active=True).first()
        if not cred:
            cred = WechatCredential.query.filter_by(is_active=True).first()
        if cred:
            cookie = cred.cookie

    if not cookie:
        return jsonify({
            'code': 1,
            'message': '请提供Cookie或先添加微信凭证'
        })

    spider = WechatArticleSpider()
    articles = spider.fetch_articles_by_biz(biz, cookie, count=5)

    if articles:
        return jsonify({
            'code': 0,
            'data': {
                'success': True,
                'articles_count': len(articles),
                'sample': [{
                    'title': a.get('title', ''),
                    'url': a.get('url', '')
                } for a in articles[:3]]
            },
            'message': '凭证有效，成功获取文章'
        })
    else:
        return jsonify({
            'code': 1,
            'message': '凭证可能无效或无法获取文章，请检查Cookie'
        })


@api_bp.route('/wechat/crawl-links', methods=['POST'])
@require_permission('manage_crawl')
def crawl_wechat_links():
    """
    批量采集公众号文章链接
    支持两种输入格式：
    1. 单个链接：{"url": "https://..."}
    2. 链接列表：{"articles": [{"link": "https://...", "title": "..."}]}
    3. JSON文件格式：直接传入上述格式

    请求参数：
    - url: 单个文章链接
    - articles: 文章列表（包含link和可选的title字段）
    - account_name: 公众号名称（可选）
    """
    try:
        data = request.get_json(silent=True)
    except Exception as e:
        return jsonify({'code': 1, 'message': f'请求格式错误: {str(e)}'})

    if not data:
        return jsonify({'code': 1, 'message': '请提供文章链接或文章列表'})

    # 解析输入格式
    article_links = []

    # 格式1: 单个URL
    if 'url' in data and data['url']:
        url = data['url'].strip()
        if url.startswith('http'):
            article_links.append({
                'url': url,
                'title': data.get('title', '')
            })

    # 格式2: articles数组
    if 'articles' in data and isinstance(data['articles'], list):
        for item in data['articles']:
            if isinstance(item, dict):
                link = item.get('link') or item.get('url') or ''
                if link and link.startswith('http'):
                    article_links.append({
                        'url': link.strip(),
                        'title': item.get('title', '')
                    })

    # 格式3: 直接是链接数组（兼容 ["url1", "url2"]）
    if not article_links and isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.startswith('http'):
                article_links.append({
                    'url': item.strip(),
                    'title': ''
                })

    if not article_links:
        return jsonify({
            'code': 1,
            'message': '未找到有效的文章链接，请检查输入格式'
        })

    # 执行采集
    manager = CrawlManager()
    saved_count = 0
    failed_count = 0
    skip_count = 0
    results = []

    print(f"[API] 开始批量采集 {len(article_links)} 个链接...")

    # 获取已存在的URL用于去重
    existing_urls = set(
        row[0] for row in db.session.query(WechatContent.url).all()
        if row[0]
    )

    for i, article in enumerate(article_links, 1):
        url = article['url']

        # 跳过已存在的文章
        if url in existing_urls:
            skip_count += 1
            print(f"[API] [{i}/{len(article_links)}] 跳过重复: {article.get('title', url[:40])}...")
            results.append({
                'url': url,
                'title': article.get('title', ''),
                'status': 'skipped',
                'message': '文章已存在'
            })
            continue

        print(f"[API] [{i}/{len(article_links)}] 采集: {article.get('title', url[:40])}...")

        try:
            result = manager.crawl_wechat_article(
                url=url,
                account_name=data.get('account_name')
            )

            if result.get('success'):
                saved_count += 1
                existing_urls.add(url)
                results.append({
                    'url': url,
                    'title': article.get('title', ''),
                    'status': 'success',
                    'message': result.get('message', '采集成功')
                })
            else:
                failed_count += 1
                results.append({
                    'url': url,
                    'title': article.get('title', ''),
                    'status': 'failed',
                    'message': result.get('message', '采集失败')
                })

        except Exception as e:
            failed_count += 1
            print(f"[API] 采集异常: {e}")
            results.append({
                'url': url,
                'title': article.get('title', ''),
                'status': 'failed',
                'message': f'异常: {str(e)}'
            })

        # 避免请求过快
        if i < len(article_links):
            time.sleep(random.uniform(0.5, 1.5))

    return jsonify({
        'code': 0,
        'data': {
            'total': len(article_links),
            'saved': saved_count,
            'failed': failed_count,
            'skipped': skip_count,
            'results': results[:50]  # 限制返回结果数量
        },
        'message': f'采集完成：成功 {saved_count} 篇，跳过 {skip_count} 篇，失败 {failed_count} 篇'
    })


# ==================== Coze工作流API ====================

@api_bp.route('/coze/workflow-status', methods=['GET'])
@login_required
def get_coze_workflow_status():
    """获取Coze工作流配置状态"""
    api_token = current_app.config.get('COZE_API_TOKEN')
    workflow_id = current_app.config.get('COZE_WORKFLOW_ID')

    if not api_token:
        return jsonify({
            'code': 1,
            'message': 'Coze API Token未配置',
            'data': {
                'configured': False,
                'workflow_id': workflow_id
            }
        })

    return jsonify({
        'code': 0,
        'data': {
            'configured': True,
            'workflow_id': workflow_id
        },
        'message': 'Coze工作流已配置'
    })


@api_bp.route('/coze/run-workflow', methods=['POST'])
@require_permission('manage_crawl')
def run_coze_workflow():
    """
    调用Coze工作流获取微信文章链接

    请求参数：
    - keyword: 搜索关键词（如公众号名称、主题等）
    - count: 要获取的文章数量（默认10）
    - auto_crawl: 是否自动采集获取的文章（默认true）
    """
    api_token = current_app.config.get('COZE_API_TOKEN')
    workflow_id = current_app.config.get('COZE_WORKFLOW_ID')
    workflow_url = current_app.config.get('COZE_API_URL')

    if not api_token:
        return jsonify({
            'code': 1,
            'message': '请先配置Coze API Token（设置环境变量 COZE_API_TOKEN）'
        })

    data = request.json or {}
    keyword = data.get('keyword', '').strip()
    count = data.get('count', 10)
    auto_crawl = data.get('auto_crawl', True)

    if not keyword:
        return jsonify({
            'code': 1,
            'message': '请提供搜索关键词（公众号名称或主题）'
        })

    # 调用Coze工作流
    try:
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            'workflow_id': workflow_id,
            'parameters': {
                'keyword': keyword,
                'count': count
            },
            'is_async': False  # 同步执行
        }

        print(f"[Coze] 调用工作流，关键词: {keyword}, 数量: {count}")

        response = requests.post(
            workflow_url,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            return jsonify({
                'code': 1,
                'message': f'Coze API调用失败: {response.status_code} - {response.text}'
            })

        result = response.json()
        print(f"[Coze] 工作流响应: {json.dumps(result, ensure_ascii=False)[:500]}")

        # 解析工作流返回的数据
        # Coze工作流返回格式：{"code": 0, "data": {...}, "msg": "..."}
        if result.get('code') != 0:
            return jsonify({
                'code': 1,
                'message': f'工作流执行失败: {result.get("msg", "未知错误")}'
            })

        # 提取文章链接
        workflow_data = result.get('data', {})
        output_data = workflow_data.get('output', {})

        # 支持多种返回格式
        articles = []
        if isinstance(output_data, list):
            articles = output_data
        elif isinstance(output_data, dict):
            # 尝试从不同字段提取文章
            articles = output_data.get('articles', []) or \
                       output_data.get('links', []) or \
                       output_data.get('data', []) or \
                       [output_data]  # 单篇文章
        elif isinstance(output_data, str):
            # 尝试解析字符串为JSON
            try:
                articles = json.loads(output_data)
                if isinstance(articles, dict):
                    articles = articles.get('articles', [articles])
            except:
                pass

        # 标准化文章格式
        normalized_articles = []
        for article in articles:
            if isinstance(article, dict):
                link = article.get('link') or article.get('url') or ''
                if link:
                    normalized_articles.append({
                        'link': link.strip(),
                        'title': article.get('title', '')
                    })
            elif isinstance(article, str) and article.startswith('http'):
                normalized_articles.append({
                    'link': article.strip(),
                    'title': ''
                })

        print(f"[Coze] 获取到 {len(normalized_articles)} 个文章链接")

        if not normalized_articles:
            return jsonify({
                'code': 0,
                'data': {
                    'articles': [],
                    'count': 0
                },
                'message': '工作流执行成功，但未获取到文章链接'
            })

        # 如果开启自动采集
        if auto_crawl:
            # 调用批量采集
            crawl_result = _crawl_articles_from_links(normalized_articles, keyword)
            return jsonify({
                'code': 0,
                'data': {
                    'workflow': {
                        'fetched': len(normalized_articles),
                        'sample': normalized_articles[:3]
                    },
                    'crawl': crawl_result
                },
                'message': f'获取 {len(normalized_articles)} 个链接，已开始采集'
            })
        else:
            return jsonify({
                'code': 0,
                'data': {
                    'articles': normalized_articles,
                    'count': len(normalized_articles)
                },
                'message': f'成功获取 {len(normalized_articles)} 个文章链接'
            })

    except requests.exceptions.Timeout:
        return jsonify({
            'code': 1,
            'message': 'Coze工作流执行超时，请稍后重试'
        })
    except requests.exceptions.RequestException as e:
        return jsonify({
            'code': 1,
            'message': f'网络请求失败: {str(e)}'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 1,
            'message': f'执行失败: {str(e)}'
        })


def _crawl_articles_from_links(articles, account_name=''):
    """从链接列表采集文章（内部函数）"""
    manager = CrawlManager()
    saved_count = 0
    failed_count = 0
    skip_count = 0

    # 获取已存在的URL
    existing_urls = set(
        row[0] for row in db.session.query(WechatContent.url).all()
        if row[0]
    )

    for article in articles:
        url = article.get('link', '')

        if url in existing_urls:
            skip_count += 1
            continue

        try:
            result = manager.crawl_wechat_article(
                url=url,
                account_name=account_name
            )

            if result.get('success'):
                saved_count += 1
                existing_urls.add(url)
            else:
                failed_count += 1

        except Exception as e:
            failed_count += 1
            print(f"采集失败: {e}")

        # 避免请求过快
        time.sleep(random.uniform(0.5, 1.5))

    return {
        'saved': saved_count,
        'failed': failed_count,
        'skipped': skip_count
    }


# ==================== 设置页面API ====================

@api_bp.route('/settings/tasks', methods=['GET'])
@login_required
def get_crawl_tasks():
    """获取所有采集任务配置"""
    tasks = CrawlTaskConfig.query.order_by(CrawlTaskConfig.task_type).all()
    return jsonify({
        'code': 0,
        'data': [task.to_dict() for task in tasks]
    })


@api_bp.route('/settings/tasks/<int:task_id>', methods=['GET'])
@login_required
def get_crawl_task(task_id):
    """获取单个采集任务配置"""
    task = CrawlTaskConfig.query.get_or_404(task_id)
    return jsonify({
        'code': 0,
        'data': task.to_dict()
    })


@api_bp.route('/settings/tasks/<int:task_id>', methods=['PUT'])
@require_permission('manage_crawl')
def update_crawl_task(task_id):
    """更新采集任务配置"""
    task = CrawlTaskConfig.query.get_or_404(task_id)
    data = request.json

    if 'is_enabled' in data:
        task.is_enabled = data['is_enabled']
    if 'cron_hour' in data:
        task.cron_hour = data['cron_hour']
    if 'cron_minute' in data:
        task.cron_minute = data['cron_minute']
    if 'cron_day_of_week' in data:
        task.cron_day_of_week = data['cron_day_of_week']
    if 'max_count' in data:
        task.max_count = data['max_count']
    if 'auto_crawl_content' in data:
        task.auto_crawl_content = data['auto_crawl_content']

    db.session.commit()

    # 通知调度器更新任务
    try:
        from scheduler import update_scheduler_job
        update_scheduler_job(task.task_name)
    except Exception as e:
        print(f"更新调度器任务失败: {e}")

    return jsonify({
        'code': 0,
        'data': task.to_dict(),
        'message': '保存成功'
    })


@api_bp.route('/settings/tasks/<int:task_id>/run', methods=['POST'])
@require_permission('manage_crawl')
def run_crawl_task_now(task_id):
    """手动执行采集任务"""
    task = CrawlTaskConfig.query.get_or_404(task_id)

    try:
        task.last_run = datetime.now(BEIJING_TZ)

        if task.task_type == 'ai_news':
            manager = CrawlManager()
            result = manager.crawl_ai_news()
            task.last_status = 'success'
            task.last_message = result.get('message', '采集成功')
        elif task.task_type == 'education_news':
            manager = CrawlManager()
            result = manager.crawl_education_news()
            task.last_status = 'success'
            task.last_message = result.get('message', '采集成功')
        elif task.task_type == 'leidui_news':
            manager = CrawlManager()
            result = manager.crawl_leidui_news()
            task.last_status = 'success'
            task.last_message = result.get('message', '采集成功')
        else:
            task.last_status = 'failed'
            task.last_message = f'未知的任务类型: {task.task_type}'

        db.session.commit()

        return jsonify({
            'code': 0,
            'data': task.to_dict(),
            'message': f'执行完成: {task.last_message}'
        })

    except Exception as e:
        task.last_status = 'failed'
        task.last_message = str(e)
        db.session.commit()

        return jsonify({
            'code': 1,
            'message': f'执行失败: {str(e)}'
        })


@api_bp.route('/settings/save', methods=['POST'])
@require_permission('manage_settings')
def save_settings():
    """保存系统设置"""
    data = request.json

    if not data:
        return jsonify({'code': 1, 'message': '请提供设置数据'})

    # 保存到Flask配置
    if 'crawl_interval' in data:
        current_app.config['CRAWL_INTERVAL'] = data['crawl_interval']
    if 'request_timeout' in data:
        current_app.config['REQUEST_TIMEOUT'] = data['request_timeout']
    if 'min_cookie_count' in data:
        current_app.config['MIN_COOKIE_COUNT'] = data['min_cookie_count']

    return jsonify({
        'code': 0,
        'message': '设置已保存'
    })


@api_bp.route('/settings/tasks', methods=['POST'])
@require_permission('manage_crawl')
def create_crawl_task():
    """创建新的采集任务"""
    data = request.json

    if not data:
        return jsonify({'code': 1, 'message': '请提供任务数据'})

    # 验证必填字段
    required = ['task_name', 'task_type', 'display_name']
    for field in required:
        if not data.get(field):
            return jsonify({'code': 1, 'message': f'缺少必填字段: {field}'})

    # 检查任务名是否已存在
    existing = CrawlTaskConfig.query.filter_by(task_name=data['task_name']).first()
    if existing:
        return jsonify({'code': 1, 'message': '任务名称已存在'})

    # 验证任务类型
    valid_types = ['ai_news', 'education_news', 'wechat_search']
    if data['task_type'] not in valid_types:
        return jsonify({'code': 1, 'message': f'无效的任务类型，有效值: {", ".join(valid_types)}'})

    try:
        task = CrawlTaskConfig(
            task_name=data['task_name'],
            task_type=data['task_type'],
            display_name=data['display_name'],
            description=data.get('description', ''),
            is_enabled=data.get('is_enabled', True),
            cron_hour=data.get('cron_hour', 2),
            cron_minute=data.get('cron_minute', 0),
            cron_day_of_week=data.get('cron_day_of_week'),
            keywords=data.get('keywords', ''),
            max_count=data.get('max_count', 20),
            auto_crawl_content=data.get('auto_crawl_content', True)
        )

        db.session.add(task)
        db.session.commit()

        # 添加到调度器
        try:
            from scheduler import update_scheduler_job
            if task.is_enabled:
                update_scheduler_job(task.task_name)
        except Exception as e:
            print(f"更新调度器任务失败: {e}")

        return jsonify({
            'code': 0,
            'data': task.to_dict(),
            'message': '任务创建成功'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 1, 'message': f'创建失败: {str(e)}'})


@api_bp.route('/settings/tasks/<int:task_id>', methods=['DELETE'])
@require_permission('manage_crawl')
def delete_crawl_task(task_id):
    """删除采集任务"""
    task = CrawlTaskConfig.query.get_or_404(task_id)

    try:
        # 从调度器移除
        try:
            from scheduler import _scheduler
            if _scheduler:
                job_id = f'task_{task.task_name}'
                if _scheduler.get_job(job_id):
                    _scheduler.remove_job(job_id)
        except Exception as e:
            print(f"从调度器移除任务失败: {e}")

        db.session.delete(task)
        db.session.commit()

        return jsonify({
            'code': 0,
            'message': '任务已删除'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 1, 'message': f'删除失败: {str(e)}'})


@api_bp.route('/settings/task-types', methods=['GET'])
@login_required
def get_task_types():
    """获取可用的任务类型"""
    types = [
        {
            'type': 'ai_news',
            'name': 'AI资讯采集',
            'description': '通过搜狗搜索采集AI领域最新资讯',
            'has_keywords': True
        },
        {
            'type': 'education_news',
            'name': '教育资讯采集',
            'description': '通过搜狗搜索采集教育行业资讯',
            'has_keywords': True
        },
        {
            'type': 'wechat_search',
            'name': '微信公众号搜索',
            'description': '通过关键词搜索微信公众号文章',
            'has_keywords': True
        }
    ]
    return jsonify({
        'code': 0,
        'data': types
    })


@api_bp.route('/settings/tasks/init', methods=['POST'])
@require_permission('manage_crawl')
def init_default_tasks():
    """初始化默认采集任务"""
    # 检查是否已有任务配置
    existing = CrawlTaskConfig.query.count()
    if existing > 0:
        return jsonify({
            'code': 0,
            'message': '任务已存在，无需初始化'
        })

    # 创建默认任务
    default_tasks = [
        {
            'task_name': 'ai_news',
            'task_type': 'ai_news',
            'display_name': 'AI资讯采集',
            'description': '自动采集AI领域最新资讯',
            'is_enabled': True,
            'cron_hour': 2,
            'cron_minute': 0,
            'max_count': 20,
            'auto_crawl_content': True
        },
        {
            'task_name': 'education_news',
            'task_type': 'education_news',
            'display_name': '教育资讯采集',
            'description': '自动采集教育行业最新资讯',
            'is_enabled': True,
            'cron_hour': 8,
            'cron_minute': 0,
            'cron_day_of_week': 'mon,tue,wed,thu,fri',
            'max_count': 20,
            'auto_crawl_content': True
        }
    ]

    for task_data in default_tasks:
        task = CrawlTaskConfig(**task_data)
        db.session.add(task)

    db.session.commit()

    return jsonify({
        'code': 0,
        'message': f'已初始化 {len(default_tasks)} 个默认任务'
    })

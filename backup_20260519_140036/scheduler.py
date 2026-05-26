"""
定时任务调度器
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def init_scheduler(app):
    """初始化定时任务"""
    scheduler = BackgroundScheduler()
    
    with app.app_context():
        # 每日凌晨2点执行AI资讯采集
        scheduler.add_job(
            func=crawl_ai_news_task,
            trigger=CronTrigger(hour=2, minute=0),
            id='crawl_ai_news',
            name='每日AI资讯采集',
            replace_existing=True
        )
        
        # 每日8:00、12:00、18:00执行教育资讯采集
        for hour in [8, 12, 18]:
            scheduler.add_job(
                func=crawl_education_news_task,
                trigger=CronTrigger(hour=hour, minute=0),
                id=f'crawl_education_news_{hour}',
                name=f'教育资讯采集({hour}:00)',
                replace_existing=True
            )
        
        # 每6小时执行一次Cookie池清理
        scheduler.add_job(
            func=cleanup_cookies_task,
            trigger=CronTrigger(hour='*/6'),
            id='cleanup_cookies',
            name='清理过期Cookie',
            replace_existing=True
        )
        
        # 每周一早上9点生成周报
        scheduler.add_job(
            func=generate_weekly_report_task,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='generate_weekly_report',
            name='自动生成周报',
            replace_existing=True
        )
    
    scheduler.start()
    logger.info('定时任务调度器已启动')
    
    return scheduler


def crawl_ai_news_task():
    """AI资讯采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    
    app = create_app()
    with app.app_context():
        try:
            manager = CrawlManager()
            result = manager.crawl_ai_news()
            logger.info(f"AI资讯采集完成: {result['message']}")
        except Exception as e:
            logger.error(f"AI资讯采集失败: {str(e)}")


def crawl_education_news_task():
    """教育资讯采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    
    app = create_app()
    with app.app_context():
        try:
            manager = CrawlManager()
            result = manager.crawl_education_news()
            logger.info(f"教育资讯采集完成: {result['message']}")
        except Exception as e:
            logger.error(f"教育资讯采集失败: {str(e)}")


def cleanup_cookies_task():
    """Cookie池清理任务"""
    from app import create_app
    from core.cookie_manager import CookieManager
    
    app = create_app()
    with app.app_context():
        try:
            count = CookieManager.cleanup_expired_cookies()
            logger.info(f"清理了 {count} 个过期Cookie")
        except Exception as e:
            logger.error(f"Cookie清理失败: {str(e)}")


def generate_weekly_report_task():
    """自动生成周报任务（生成本周周报）"""
    from app import create_app
    from core.report_generator import WeeklyReportGenerator
    
    app = create_app()
    with app.app_context():
        try:
            # 使用默认本周日期范围
            generator = WeeklyReportGenerator()
            report = generator.generate_report()  # 不传参数，使用本周
            
            # 自动发布
            report.status = 'published'
            from models import db
            db.session.commit()
            
            logger.info(f"自动生成周报成功: {report.title}")
        except Exception as e:
            logger.error(f"自动生成周报失败: {str(e)}")


def crawl_accounts_task(account_ids=None):
    """公众号采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    from models import OfficialAccount
    
    app = create_app()
    with app.app_context():
        try:
            manager = CrawlManager()
            
            if account_ids:
                results = []
                for account_id in account_ids:
                    result = manager.crawl_account(account_id)
                    results.append(result)
            else:
                # 采集所有启用的公众号
                accounts = OfficialAccount.query.filter_by(is_active=True).all()
                results = []
                for account in accounts:
                    result = manager.crawl_account(account.id)
                    results.append(result)
            
            logger.info(f"公众号采集完成，共 {len(results)} 个")
            return results
        except Exception as e:
            logger.error(f"公众号采集失败: {str(e)}")
            return []

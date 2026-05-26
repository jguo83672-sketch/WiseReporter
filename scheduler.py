"""
定时任务调度器
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import pytz

logger = logging.getLogger(__name__)

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 全局调度器实例
_scheduler = None


def init_scheduler(app):
    """初始化定时任务"""
    global _scheduler
    
    # 如果已有调度器，先停止
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    
    # 使用北京时间
    scheduler = BackgroundScheduler(timezone=BEIJING_TZ)
    
    with app.app_context():
        # 初始化默认任务配置
        from models import CrawlTaskConfig
        _init_default_tasks()
        
        # 从数据库加载任务配置
        _load_tasks_from_config(scheduler)
        
        # 每6小时执行一次Cookie池清理
        scheduler.add_job(
            func=cleanup_cookies_task,
            trigger=CronTrigger(hour='*/6', timezone=BEIJING_TZ),
            id='cleanup_cookies',
            name='清理过期Cookie',
            replace_existing=True
        )
        
        # 每周一早上9点生成周报
        scheduler.add_job(
            func=generate_weekly_report_task,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=BEIJING_TZ),
            id='generate_weekly_report',
            name='自动生成周报',
            replace_existing=True
        )
    
    scheduler.start()
    logger.info('定时任务调度器已启动（使用北京时间）')
    
    _scheduler = scheduler
    return scheduler


def _init_default_tasks():
    """初始化默认任务配置"""
    from models import CrawlTaskConfig
    
    # 检查是否已有任务配置
    if CrawlTaskConfig.query.count() > 0:
        return
    
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
            'description': '自动采集教育行业最新资讯（工作日）',
            'is_enabled': True,
            'cron_hour': 8,
            'cron_minute': 0,
            'cron_day_of_week': 'mon,tue,wed,thu,fri',
            'max_count': 20,
            'auto_crawl_content': True
        },
        {
            'task_name': 'leidui_news',
            'task_type': 'leidui_news',
            'display_name': '雷递网资讯采集',
            'description': '自动采集雷递网最新资讯',
            'is_enabled': True,
            'cron_hour': 10,
            'cron_minute': 0,
            'max_count': 10,
            'auto_crawl_content': True
        }
    ]
    
    from models import db
    for task_data in default_tasks:
        task = CrawlTaskConfig(**task_data)
        db.session.add(task)
    
    db.session.commit()
    logger.info('已初始化默认采集任务（包含雷递网）')


def _load_tasks_from_config(scheduler):
    """从数据库配置加载任务"""
    from models import CrawlTaskConfig
    
    tasks = CrawlTaskConfig.query.all()
    for task in tasks:
        _add_job_from_task(scheduler, task)


def _add_job_from_task(scheduler, task):
    """根据任务配置添加调度任务"""
    if not task.is_enabled:
        return
    
    # 确定任务函数
    if task.task_type == 'ai_news':
        func = crawl_ai_news_task
    elif task.task_type == 'education_news':
        func = crawl_education_news_task
    elif task.task_type == 'leidui_news':
        func = crawl_leidui_news_task
    else:
        logger.warning(f'未知的任务类型: {task.task_type}')
        return
    
    # 构建触发器
    trigger_kwargs = {
        'hour': task.cron_hour,
        'minute': task.cron_minute,
        'timezone': BEIJING_TZ
    }
    
    if task.cron_day_of_week:
        trigger_kwargs['day_of_week'] = task.cron_day_of_week
    
    try:
        trigger = CronTrigger(**trigger_kwargs)
        
        scheduler.add_job(
            func=func,
            trigger=trigger,
            id=f'task_{task.task_name}',
            name=f'{task.display_name}',
            replace_existing=True,
            kwargs={'task_id': task.id}
        )
        logger.info(f'已添加任务: {task.display_name} ({task.cron_hour}:{task.cron_minute:02d} 北京时间)')
    except Exception as e:
        logger.error(f'添加任务失败 {task.display_name}: {e}')


def update_scheduler_job(task_name):
    """更新指定任务（重新加载配置）"""
    global _scheduler
    
    if not _scheduler:
        logger.warning('调度器未初始化')
        return
    
    from models import CrawlTaskConfig
    
    # 移除旧任务
    job_id = f'task_{task_name}'
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        logger.info(f'已移除旧任务: {task_name}')
    
    # 加载新配置
    task = CrawlTaskConfig.query.filter_by(task_name=task_name).first()
    if task and task.is_enabled:
        _add_job_from_task(_scheduler, task)


def crawl_ai_news_task(task_id=None):
    """AI资讯采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    from models import CrawlTaskConfig, db
    
    app = create_app()
    with app.app_context():
        try:
            # 获取任务配置
            task = None
            if task_id:
                task = CrawlTaskConfig.query.get(task_id)
            
            max_count = task.max_count if task else 20
            
            manager = CrawlManager()
            result = manager.crawl_ai_news()
            logger.info(f"AI资讯采集完成: {result['message']}")
            
            # 更新任务状态（使用北京时间）
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'success'
                task.last_message = result.get('message', '采集成功')
                db.session.commit()
                
        except Exception as e:
            logger.error(f"AI资讯采集失败: {str(e)}")
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'failed'
                task.last_message = str(e)
                db.session.commit()


def crawl_education_news_task(task_id=None):
    """教育资讯采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    from models import CrawlTaskConfig, db
    
    app = create_app()
    with app.app_context():
        try:
            # 获取任务配置
            task = None
            if task_id:
                task = CrawlTaskConfig.query.get(task_id)
            
            max_count = task.max_count if task else 20
            
            manager = CrawlManager()
            result = manager.crawl_all_education_news()
            logger.info(f"教育资讯采集完成: {result['message']}")
            
            # 更新任务状态（使用北京时间）
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'success'
                task.last_message = result.get('message', '采集成功')
                db.session.commit()
                
        except Exception as e:
            logger.error(f"教育资讯采集失败: {str(e)}")
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'failed'
                task.last_message = str(e)
                db.session.commit()


def crawl_leidui_news_task(task_id=None):
    """雷递网资讯采集任务"""
    from app import create_app
    from core.data_store import CrawlManager
    from models import CrawlTaskConfig, db
    
    app = create_app()
    with app.app_context():
        try:
            # 获取任务配置
            task = None
            if task_id:
                task = CrawlTaskConfig.query.get(task_id)
            
            max_count = task.max_count if task else 10
            
            manager = CrawlManager()
            result = manager.crawl_leidui_news()
            logger.info(f"雷递网资讯采集完成: {result['message']}")
            
            # 更新任务状态（使用北京时间）
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'success'
                task.last_message = result.get('message', '采集成功')
                db.session.commit()
                
        except Exception as e:
            logger.error(f"雷递网资讯采集失败: {str(e)}")
            if task:
                task.last_run = datetime.now(BEIJING_TZ)
                task.last_status = 'failed'
                task.last_message = str(e)
                db.session.commit()


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

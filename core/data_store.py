"""
数据存储模块
"""
from datetime import datetime
from typing import List, Optional
import random
import pytz
from models import db, AIContent, EducationContent, WechatContent, NewsSource, CrawlLog, LeiduiContent
from core.scraper import AINewsScraper, EducationNewsScraper, JiemoduiScraper, DuozhiScraper, CctvScraper, AIHotSpider, WechatScraper
from core.wechat_scraper import WechatArticleSpider
from core.cookie_manager import CookieManager
from core.leidui_scraper import LeinewsSpider

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


class ArticleStore:
    """文章存储管理"""
    
    @staticmethod
    def save_ai_content(content_data: dict) -> Optional[AIContent]:
        """保存AI资讯"""
        existing = AIContent.query.filter_by(url=content_data.get('url')).first()
        if existing:
            return existing
        
        ai_content = AIContent(
            title=content_data.get('title', ''),
            url=content_data.get('url', ''),
            source=content_data.get('source'),
            summary=content_data.get('summary'),
            content=content_data.get('content'),
            publish_date=content_data.get('publish_date'),
            category=content_data.get('category'),
            tags=','.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else content_data.get('tags')
        )
        
        db.session.add(ai_content)
        db.session.commit()
        return ai_content
    
    @staticmethod
    def get_ai_contents(page: int = 1, per_page: int = 20,
                        source: str = None, category: str = None,
                        keyword: str = None,
                        sort_by: str = 'publish_date') -> List[AIContent]:
        """获取AI资讯列表
        
        Args:
            page: 页码
            per_page: 每页数量
            source: 来源筛选
            category: 分类筛选
            keyword: 搜索关键词
            sort_by: 排序字段，默认为 publish_date（发布时间），可选 created_at（入库时间）
        """
        from sqlalchemy import desc
        
        query = AIContent.query
        
        if source:
            query = query.filter(AIContent.source == source)
        if category:
            query = query.filter(AIContent.category == category)
        if keyword:
            query = query.filter(
                AIContent.title.contains(keyword) | 
                AIContent.summary.contains(keyword) |
                AIContent.content.contains(keyword)
            )
        
        # 按发布时间排序（publish_date优先，created_at作为次要排序）
        if sort_by == 'publish_date':
            query = query.order_by(
                desc(db.func.coalesce(AIContent.publish_date, AIContent.created_at))
            )
        else:
            query = query.order_by(AIContent.created_at.desc())
        
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def save_education_content(content_data: dict) -> Optional[EducationContent]:
        """保存教育资讯"""
        existing = EducationContent.query.filter_by(url=content_data.get('url')).first()
        if existing:
            return existing
        
        edu_content = EducationContent(
            title=content_data.get('title', ''),
            url=content_data.get('url', ''),
            source=content_data.get('source'),
            source_name=content_data.get('source_name'),
            summary=content_data.get('summary'),
            content=content_data.get('content'),
            publish_date=content_data.get('publish_date'),
            publish_date_str=content_data.get('publish_date_str'),
            category=content_data.get('category'),
            tags=','.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else content_data.get('tags')
        )
        
        db.session.add(edu_content)
        db.session.commit()
        return edu_content
    
    @staticmethod
    def get_education_contents(page: int = 1, per_page: int = 20,
                               source: str = None, keyword: str = None,
                               start_date: datetime = None, end_date: datetime = None,
                               is_favorite: bool = None,
                               sort_by: str = 'publish_date') -> List[EducationContent]:
        """获取教育资讯列表
        
        Args:
            page: 页码
            per_page: 每页数量
            source: 来源筛选（jiemodui/duozhi/cctv）
            keyword: 搜索关键词
            start_date: 开始日期
            end_date: 结束日期
            is_favorite: 是否收藏
            sort_by: 排序字段，默认为 publish_date（发布时间），可选 created_at（入库时间）
        """
        from sqlalchemy import desc, asc
        
        query = EducationContent.query
        
        if source:
            query = query.filter(EducationContent.source == source)
        if keyword:
            query = query.filter(
                EducationContent.title.contains(keyword) | 
                EducationContent.summary.contains(keyword) |
                EducationContent.content.contains(keyword)
            )
        if start_date:
            query = query.filter(EducationContent.created_at >= start_date)
        if end_date:
            query = query.filter(EducationContent.created_at <= end_date)
        if is_favorite is not None:
            query = query.filter(EducationContent.is_favorite == is_favorite)
        
        # 按发布时间排序（publish_date优先，created_at作为次要排序）
        if sort_by == 'publish_date':
            query = query.order_by(
                desc(db.func.coalesce(EducationContent.publish_date, EducationContent.created_at))
            )
        else:
            query = query.order_by(desc(EducationContent.created_at))
        
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def toggle_education_favorite(content_id: int) -> Optional[EducationContent]:
        """切换收藏状态"""
        content = EducationContent.query.get(content_id)
        if content:
            content.is_favorite = not content.is_favorite
            db.session.commit()
        return content
    
    @staticmethod
    def toggle_education_read(content_id: int) -> Optional[EducationContent]:
        """标记已读"""
        content = EducationContent.query.get(content_id)
        if content:
            content.is_read = True
            db.session.commit()
        return content
    
    @staticmethod
    def delete_education_content(content_id: int) -> bool:
        """删除教育资讯"""
        content = EducationContent.query.get(content_id)
        if content:
            db.session.delete(content)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def save_wechat_content(content_data: dict) -> Optional[WechatContent]:
        """保存公众号文章"""
        existing = WechatContent.query.filter_by(url=content_data.get('url')).first()
        if existing:
            return existing
        
        wechat_content = WechatContent(
            title=content_data.get('title', ''),
            url=content_data.get('url', ''),
            account_name=content_data.get('account_name'),
            account_id=content_data.get('account_id'),
            summary=content_data.get('summary'),
            content=content_data.get('content'),
            author=content_data.get('author'),
            publish_date=content_data.get('publish_date'),
            cover_image=content_data.get('cover_image'),
            tags=','.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else content_data.get('tags')
        )
        
        db.session.add(wechat_content)
        db.session.commit()
        return wechat_content
    
    @staticmethod
    def get_wechat_contents(page: int = 1, per_page: int = 20,
                            account_name: str = None, keyword: str = None,
                            start_date: datetime = None, end_date: datetime = None,
                            is_favorite: bool = None,
                            sort_by: str = 'publish_date') -> List[WechatContent]:
        """获取公众号文章列表
        
        Args:
            page: 页码
            per_page: 每页数量
            account_name: 公众号名称筛选
            keyword: 搜索关键词
            start_date: 开始日期
            end_date: 结束日期
            is_favorite: 是否收藏
            sort_by: 排序字段
        """
        from sqlalchemy import desc
        
        query = WechatContent.query
        
        if account_name:
            query = query.filter(WechatContent.account_name.contains(account_name))
        if keyword:
            query = query.filter(
                WechatContent.title.contains(keyword) | 
                WechatContent.summary.contains(keyword) |
                WechatContent.content.contains(keyword)
            )
        if start_date:
            query = query.filter(WechatContent.created_at >= start_date)
        if end_date:
            query = query.filter(WechatContent.created_at <= end_date)
        if is_favorite is not None:
            query = query.filter(WechatContent.is_favorite == is_favorite)
        
        if sort_by == 'publish_date':
            query = query.order_by(
                desc(db.func.coalesce(WechatContent.publish_date, WechatContent.created_at))
            )
        else:
            query = query.order_by(desc(WechatContent.created_at))
        
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def toggle_wechat_favorite(content_id: int) -> Optional[WechatContent]:
        """切换公众号文章收藏状态"""
        content = WechatContent.query.get(content_id)
        if content:
            content.is_favorite = not content.is_favorite
            db.session.commit()
        return content
    
    @staticmethod
    def delete_wechat_content(content_id: int) -> bool:
        """删除公众号文章"""
        content = WechatContent.query.get(content_id)
        if content:
            db.session.delete(content)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def save_leidui_content(content_data: dict) -> Optional[LeiduiContent]:
        """保存雷递网资讯"""
        existing = LeiduiContent.query.filter_by(url=content_data.get('url')).first()
        if existing:
            return existing
        
        leidui_content = LeiduiContent(
            title=content_data.get('title', ''),
            url=content_data.get('url', ''),
            source=content_data.get('source', 'leinews'),
            source_name=content_data.get('source_name', '雷递网'),
            summary=content_data.get('summary'),
            content=content_data.get('content'),
            cover_image=content_data.get('cover_image'),
            category=content_data.get('category'),
            tags=','.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else content_data.get('tags'),
            author=content_data.get('author'),
            publish_date=content_data.get('publish_date')
        )
        
        db.session.add(leidui_content)
        db.session.commit()
        return leidui_content
    
    @staticmethod
    def get_leidui_contents(page: int = 1, per_page: int = 20,
                            category: str = None, keyword: str = None,
                            is_favorite: bool = None,
                            sort_by: str = 'publish_date') -> List[LeiduiContent]:
        """获取雷递网资讯列表
        
        Args:
            page: 页码
            per_page: 每页数量
            category: 分类筛选
            keyword: 搜索关键词
            is_favorite: 是否收藏
            sort_by: 排序字段
        """
        from sqlalchemy import desc
        
        query = LeiduiContent.query
        
        if category:
            query = query.filter(LeiduiContent.category == category)
        if keyword:
            query = query.filter(
                LeiduiContent.title.contains(keyword) | 
                LeiduiContent.summary.contains(keyword) |
                LeiduiContent.content.contains(keyword)
            )
        if is_favorite is not None:
            query = query.filter(LeiduiContent.is_favorite == is_favorite)
        
        if sort_by == 'publish_date':
            query = query.order_by(
                desc(db.func.coalesce(LeiduiContent.publish_date, LeiduiContent.created_at))
            )
        else:
            query = query.order_by(desc(LeiduiContent.created_at))
        
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def toggle_leidui_favorite(content_id: int) -> Optional[LeiduiContent]:
        """切换雷递网资讯收藏状态"""
        content = LeiduiContent.query.get(content_id)
        if content:
            content.is_favorite = not content.is_favorite
            db.session.commit()
        return content
    
    @staticmethod
    def toggle_leidui_read(content_id: int) -> Optional[LeiduiContent]:
        """标记雷递网资讯已读"""
        content = LeiduiContent.query.get(content_id)
        if content:
            content.is_read = True
            db.session.commit()
        return content
    
    @staticmethod
    def delete_leidui_content(content_id: int) -> bool:
        """删除雷递网资讯"""
        content = LeiduiContent.query.get(content_id)
        if content:
            db.session.delete(content)
            db.session.commit()
            return True
        return False


class CrawlManager:
    """采集管理"""
    
    def __init__(self):
        self.cookie_manager = CookieManager()
    
    def crawl_ai_news(self, source: str = '36kr', days: int = 7, take: int = 10, mode: str = 'selected') -> dict:
        """
        采集AI资讯 - 优先使用AI HOT API，失败则使用备用源
        
        Args:
            source: 数据源，默认 36kr，可选 aihot
            days: 采集最近天数，默认7天
            take: 每次采集条数，默认50条，最大100
            mode: 'selected' 精选 / 'all' 全部 (仅AI HOT有效)
        """
        try:
            # 优先尝试AIHotSpider API
            spider = AIHotSpider()
            raw_items = spider.get_items(mode=mode, days=days, take=min(take, 100))
            
            if raw_items:
                # AI HOT API 可用，保存数据
                saved_count = 0
                for raw_item in raw_items:
                    article_data = spider.format_item(raw_item)
                    if article_data.get('url'):
                        content = ArticleStore.save_ai_content(article_data)
                        if content:
                            saved_count += 1
                
                news_source = NewsSource.query.filter_by(name='aihot').first()
                if news_source:
                    news_source.last_crawl = datetime.now(BEIJING_TZ)
                else:
                    news_source = NewsSource(
                        name='aihot', 
                        url='https://aihot.cn', 
                        source_type='ai', 
                        last_crawl=datetime.now(BEIJING_TZ)
                    )
                    db.session.add(news_source)
                db.session.commit()
                
                return {
                    'success': True,
                    'saved_count': saved_count,
                    'total_fetched': len(raw_items),
                    'source': 'aihot',
                    'message': f'成功采集 {saved_count} 条AI资讯 (AI HOT)'
                }
            
            # AI HOT API 不可用，使用 36kr
            print("AI HOT API 不可用，使用 36kr 采集...")
            scraper = AINewsScraper('36kr', self.cookie_manager)
            articles_data = scraper.crawl_ai_news()
            
            saved_count = 0
            for article_data in articles_data:
                content = ArticleStore.save_ai_content(article_data)
                if content:
                    saved_count += 1
            
            news_source = NewsSource.query.filter_by(name='36kr').first()
            if news_source:
                news_source.last_crawl = datetime.now(BEIJING_TZ)
            else:
                news_source = NewsSource(
                    name='36kr', 
                    url='https://36kr.com', 
                    source_type='ai', 
                    last_crawl=datetime.now(BEIJING_TZ)
                )
                db.session.add(news_source)
            db.session.commit()
            
            return {
                'success': True,
                'saved_count': saved_count,
                'total_fetched': len(articles_data),
                'source': '36kr',
                'message': f'成功采集 {saved_count} 条AI资讯 (36kr)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def crawl_education_news(self, source: str = 'jiemodui', days: int = 7) -> dict:
        """采集教育资讯
        
        Args:
            source: 数据源，默认 jiemedui，可选 jiemodui/duozhi/cctv
            days: 采集天数，默认7天
        """
        try:
            # 获取已存在的URL集合，用于跳过已采集的文章
            existing_urls = set(
                row[0] for row in db.session.query(EducationContent.url).filter_by(source=source).all()
                if row[0]
            )
            
            if source == 'jiemodui':
                # 使用芥末堆专用爬虫
                scraper = JiemoduiScraper(self.cookie_manager)
                articles_data = scraper.crawl_articles_in_range(days=days, existing_urls=existing_urls)
                source_name = '芥末堆'
            elif source == 'duozhi':
                # 使用多知网专用爬虫
                scraper = DuozhiScraper(self.cookie_manager)
                articles_data = scraper.crawl_articles_in_range(existing_urls=existing_urls)
                source_name = '多知网'
            elif source == 'cctv':
                # 使用央视网专用爬虫
                scraper = CctvScraper(self.cookie_manager)
                articles_data = scraper.crawl_articles_in_range(existing_urls=existing_urls)
                source_name = '央视网'
            else:
                # 其他数据源使用原有的爬虫
                scraper = EducationNewsScraper(source, self.cookie_manager)
                articles_data = scraper.crawl_education_news()
                source_name = source
            
            saved_count = 0
            for article_data in articles_data:
                content = ArticleStore.save_education_content(article_data)
                if content:
                    saved_count += 1
            
            # 更新源采集时间
            news_source = NewsSource.query.filter_by(name=f'edu_{source}').first()
            if news_source:
                news_source.last_crawl = datetime.now(BEIJING_TZ)
                db.session.commit()
            
            return {
                'success': True,
                'saved_count': saved_count,
                'message': f'成功采集 {saved_count} 条{source_name}资讯'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def crawl_all_education_news(self) -> dict:
        """采集所有教育资讯源"""
        results = []
        total_saved = 0
        
        for source in ['jiemodui', 'duozhi', 'cctv']:
            result = self.crawl_education_news(source)
            source_names = {'jiemodui': '芥末堆', 'duozhi': '多知网', 'cctv': '央视网'}
            results.append({
                'source': source,
                'source_name': source_names.get(source, source),
                **result
            })
            if result.get('success'):
                total_saved += result.get('saved_count', 0)
        
        return {
            'success': True,
            'saved_count': total_saved,
            'results': results,
            'message': f'成功采集 {total_saved} 条教育资讯'
        }
    
    def get_crawl_logs(self, limit: int = 50) -> List[CrawlLog]:
        """获取采集日志"""
        return CrawlLog.query.order_by(
            CrawlLog.created_at.desc()
        ).limit(limit).all()
    
    def crawl_wechat_article(self, url: str, account_name: str = None, account_id: str = None) -> dict:
        """爬取单个微信公众号文章
        
        Args:
            url: 文章URL
            account_name: 公众号名称
            account_id: 公众号ID
        """
        try:
            print(f"[CrawlManager] 开始采集文章: {url}")
            
            # 检查Cookie是否可用
            cookie_info = self.cookie_manager.get_random_cookie()
            if not cookie_info:
                print("[CrawlManager] 错误: 没有可用的Cookie，请先在Cookie池中添加有效Cookie")
                return {
                    'success': False,
                    'message': '没有可用的Cookie，请先在Cookie池中添加有效Cookie'
                }
            
            scraper = WechatScraper(account_id, self.cookie_manager)
            print(f"[CrawlManager] 正在解析文章...")
            article_data = scraper.parse_article_detail(url)
            
            if article_data and article_data.get('title'):
                article_data['account_name'] = account_name
                article_data['account_id'] = account_id
                print(f"[CrawlManager] 文章解析成功: {article_data.get('title')}")
                content = ArticleStore.save_wechat_content(article_data)
                
                return {
                    'success': True,
                    'saved': True,
                    'message': f'成功保存文章: {article_data.get("title")}'
                }
            
            # 解析失败但没有抛出异常，打印更多信息
            print(f"[CrawlManager] 解析结果: {article_data}")
            return {
                'success': False,
                'message': '文章解析失败，可能是Cookie已过期或页面结构变化'
            }
        except Exception as e:
            import traceback
            print(f"[CrawlManager] 采集异常: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'message': f'采集异常: {str(e)}'
            }
    
    def crawl_account(self, account_id: int, max_articles: int = 20) -> dict:
        """
        批量采集公众号文章
        
        Args:
            account_id: 公众号ID (数据库主键)
            max_articles: 最大采集文章数，默认20
        
        Returns:
            采集结果字典
        """
        try:
            # 获取公众号信息
            from models import OfficialAccount
            account = OfficialAccount.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': f'未找到ID为 {account_id} 的公众号'
                }
            
            print(f"[CrawlManager] 开始采集公众号: {account.name}")
            
            # 获取已存在的文章URL，避免重复采集
            existing_urls = set(
                row[0] for row in db.session.query(WechatContent.url).filter_by(account_id=account.account_id).all()
                if row[0]
            )
            
            # 使用搜狗搜索获取公众号文章列表（不需要特殊Cookie）
            spider = WechatArticleSpider(cookie_manager=self.cookie_manager)
            
            # 使用公众号名称搜索文章
            articles = spider.fetch_articles_by_sogou(account.name, max_articles)
            
            if not articles:
                return {
                    'success': False,
                    'message': f'未能获取到 {account.name} 的文章列表，请检查公众号名称是否正确'
                }
            
            print(f"[CrawlManager] 获取到 {len(articles)} 篇文章，开始采集...")
            
            saved_count = 0
            fail_count = 0
            skip_count = 0
            
            # 限制采集数量
            articles_to_crawl = articles[:max_articles]
            
            for i, article in enumerate(articles_to_crawl, 1):
                url = article.get('url', '')
                
                # 跳过已存在的文章
                if url in existing_urls:
                    skip_count += 1
                    print(f"[CrawlManager] [{i}/{len(articles_to_crawl)}] 跳过重复文章: {article.get('title', '')[:30]}...")
                    continue
                
                print(f"[CrawlManager] [{i}/{len(articles_to_crawl)}] 采集: {article.get('title', '')[:40]}...")
                
                try:
                    # 解析文章详情
                    article_data = spider.parse_article(url)
                    
                    if article_data and article_data.get('success') and article_data.get('title'):
                        # 补充公众号信息
                        article_data['account_name'] = account.name
                        article_data['account_id'] = account.account_id
                        
                        # 保存文章
                        content = ArticleStore.save_wechat_content(article_data)
                        if content:
                            saved_count += 1
                            existing_urls.add(url)
                            print(f"[CrawlManager] ✓ 保存成功: {article_data.get('title')[:40]}...")
                        else:
                            fail_count += 1
                    else:
                        fail_count += 1
                        print(f"[CrawlManager] ✗ 解析失败")
                    
                    # 避免请求过快
                    import time
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    fail_count += 1
                    print(f"[CrawlManager] 采集异常: {e}")
                    continue
            
            return {
                'success': True,
                'saved_count': saved_count,
                'skip_count': skip_count,
                'fail_count': fail_count,
                'total_fetched': len(articles),
                'message': f'成功采集 {saved_count} 篇文章（跳过 {skip_count} 篇重复，失败 {fail_count} 篇）'
            }
            
        except Exception as e:
            import traceback
            print(f"[CrawlManager] 批量采集异常: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'message': f'批量采集异常: {str(e)}'
            }
    
    def crawl_leidui_news(self, category: str = 'all', pages: int = 2) -> dict:
        """采集雷递网最新资讯
        
        通过文章ID遍历爬取，最多10篇，遇重复或连续5篇空值时停止
        """
        try:
            spider = LeinewsSpider()
            
            # 获取已存在的文章URL，用于去重
            existing_urls = set(
                row[0] for row in 
                db.session.query(LeiduiContent.url).all()
            )
            
            # 获取上次最后爬取的ID
            last_id = None
            news_source = NewsSource.query.filter_by(name='leinews').first()
            if news_source and news_source.last_crawl:
                # 从last_crawl中解析ID（使用extra字段存储）
                if hasattr(news_source, 'category') and news_source.category:
                    try:
                        last_id = int(news_source.category)
                    except:
                        pass
            
            # 爬取文章
            articles_data, last_success_id = spider.crawl(
                existing_urls=existing_urls,
                start_id=33701,
                last_id=last_id
            )
            
            saved_count = 0
            for article_data in articles_data:
                content = ArticleStore.save_leidui_content(article_data)
                if content:
                    saved_count += 1
            
            # 保存最后成功的ID
            if last_success_id:
                if not news_source:
                    news_source = NewsSource(
                        name='leinews',
                        url='https://www.leinews.com',
                        source_type='industry',
                        category=str(last_success_id),
                        last_crawl=datetime.now(BEIJING_TZ)
                    )
                    db.session.add(news_source)
                else:
                    news_source.category = str(last_success_id)
                    news_source.last_crawl = datetime.now(BEIJING_TZ)
                db.session.commit()
            
            return {
                'success': True,
                'saved_count': saved_count,
                'total_fetched': len(articles_data),
                'last_id': last_success_id,
                'message': f'成功采集 {saved_count} 条雷递网资讯 (最后ID: {last_success_id})'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'采集失败: {str(e)}'
            }


class CrawlProgressManager:
    """爬取进度管理"""
    
    @staticmethod
    def get_progress(source: str = 'duozhi') -> dict:
        """获取爬取进度"""
        from models import CrawlProgress
        progress = CrawlProgress.query.filter_by(source=source).first()
        if progress:
            return {
                'source': progress.source,
                'last_article_id': progress.last_article_id,
                'last_article_date': progress.last_article_date,
                'last_crawl_date': progress.last_crawl_date
            }
        return {
            'source': source,
            'last_article_id': 18450,
            'last_article_date': None,
            'last_crawl_date': None
        }
    
    @staticmethod
    def reset_progress(source: str = 'duozhi', start_id: int = 18450) -> bool:
        """重置爬取进度（清空记录，从指定ID重新开始）
        
        Args:
            source: 数据源，默认 duozhi
            start_id: 新的起始ID，默认 18450
        
        Returns:
            是否成功
        """
        from models import CrawlProgress, db
        try:
            progress = CrawlProgress.query.filter_by(source=source).first()
            if progress:
                db.session.delete(progress)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

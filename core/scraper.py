"""
数据采集核心模块
支持标准库urllib + requests双模式
"""
import requests
import urllib.request
import urllib.error
import json
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional, Callable
from abc import ABC, abstractmethod
import time
import random
from datetime import timedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from core.cookie_manager import CookieManager
from core.wechat_scraper import WechatArticleSpider


class BaseScraper(ABC):
    """爬虫基类"""
    
    def __init__(self, cookie_manager: CookieManager = None):
        self.cookie_manager = cookie_manager or CookieManager()
        self.session = requests.Session()
        self.request_timeout = Config.REQUEST_TIMEOUT
        self.retry_times = Config.RETRY_TIMES
    
    def get_headers(self, user_agent: str = None) -> Dict:
        """获取请求头"""
        ua = user_agent or random.choice(Config.USER_AGENTS)
        return {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def request_with_retry(self, url: str, method: str = 'GET', 
                          use_cookie_pool: bool = True, **kwargs) -> Optional[requests.Response]:
        """带重试的请求"""
        for attempt in range(self.retry_times):
            try:
                headers = kwargs.pop('headers', {})
                
                if use_cookie_pool and self.cookie_manager:
                    cookie_info = self.cookie_manager.get_random_cookie()
                    if cookie_info:
                        self.session.cookies.update(cookie_info['cookies'])
                        headers['User-Agent'] = cookie_info['user_agent']
                
                headers.update(self.get_headers())
                kwargs['headers'] = headers
                kwargs['timeout'] = kwargs.get('timeout', self.request_timeout)
                
                if method.upper() == 'POST':
                    response = self.session.post(url, **kwargs)
                else:
                    response = self.session.get(url, **kwargs)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    # Cookie被封禁，切换Cookie
                    continue
                    
            except requests.RequestException as e:
                if attempt < self.retry_times - 1:
                    time.sleep(random.uniform(1, 3))
                    continue
                raise
        
        return None
    
    @abstractmethod
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析文章列表"""
        pass
    
    @abstractmethod
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析文章详情"""
        pass
    
    def crawl(self, url: str) -> List[Dict]:
        """执行爬取"""
        response = self.request_with_retry(url)
        if not response:
            return []
        return self.parse_article_list(response.text)


class WechatScraper(BaseScraper):
    """微信公众号爬虫（增强版 - 使用纯标准库）"""
    
    def __init__(self, account_id: str = None, cookie_manager: CookieManager = None):
        super().__init__(cookie_manager)
        self.account_id = account_id
    
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析微信公众号文章列表"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 查找文章列表项
        article_items = soup.select('.appmsg_item') or soup.select('[class*="article"]')
        
        for item in article_items:
            try:
                title_elem = item.select_one('.title') or item.select_one('h4')
                link_elem = item.select_one('a') or item.select_one('[href*="mp.weixin.qq.com"]')
                date_elem = item.select_one('.date') or item.select_one('[class*="time"]')
                
                if title_elem and link_elem:
                    href = link_elem.get('href', '')
                    if not href.startswith('http'):
                        href = 'https://mp.weixin.qq.com' + href
                    
                    articles.append({
                        'title': title_elem.get_text(strip=True),
                        'url': href,
                        'publish_date': self._parse_date(date_elem.get_text(strip=True) if date_elem else None)
                    })
            except Exception:
                continue
        
        return articles
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析文章详情 - 使用增强版标准库爬虫"""
        spider = WechatArticleSpider(cookie_manager=self.cookie_manager)
        result = spider.parse_article(url)
        
        if result.get('success'):
            return {
                'title': result.get('title'),
                'author': result.get('author'),
                'content': result.get('content'),
                'summary': result.get('summary'),
                'url': url,
                'publish_date': result.get('publish_time') or datetime.utcnow(),
                'images': result.get('images', [])
            }
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            for fmt in ['%Y-%m-%d', '%m-%d', '%Y年%m月%d日']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None


class AINewsScraper(BaseScraper):
    """AI资讯爬虫"""
    
    def __init__(self, source: str = 'default', cookie_manager: CookieManager = None):
        super().__init__(cookie_manager)
        self.source = source
        self.source_urls = {
            '36kr': 'https://36kr.com/information/ai/',
            'jiqizhixin': 'https://www.jiqizhixin.com/AI-news',
            'ai_qianxun': 'https://aihot.virxact.com/',
        }
    
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析AI资讯列表"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 通用文章列表选择器
        selectors = [
            '.article-item',
            '.news-item', 
            '[class*="article"]',
            '.post-item',
            '.article-list li'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                for item in items:
                    try:
                        title_elem = item.select_one('h2, h3, h4, .title')
                        link_elem = item.select_one('a[href]')
                        date_elem = item.select_one('.date, .time, [class*="date"]')
                        summary_elem = item.select_one('.summary, .desc, .excerpt')
                        
                        if title_elem and link_elem:
                            href = link_elem.get('href', '')
                            if href and not href.startswith('http'):
                                href = 'https://' + self.source_urls.get(self.source, 'aihot.virxact.com') + href.lstrip('/')
                            
                            articles.append({
                                'title': title_elem.get_text(strip=True),
                                'url': href,
                                'summary': summary_elem.get_text(strip=True) if summary_elem else '',
                                'publish_date': self._parse_date(date_elem.get_text(strip=True) if date_elem else None),
                                'source': self.source
                            })
                    except Exception:
                        continue
                break
        
        return articles
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析文章详情"""
        response = self.request_with_retry(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 提取正文
        content_elem = soup.select_one('article, .article-content, .post-content, main, [role="main"]')
        
        return {
            'title': soup.select_one('h1, .article-title') and soup.select_one('h1, .article-title').get_text(strip=True),
            'content': content_elem and content_elem.get_text(separator='\n', strip=True),
            'url': url,
            'publish_date': datetime.utcnow()
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None
        try:
            for fmt in ['%Y-%m-%d', '%m-%d', '%Y/%m/%d', '%Y年%m月%d日']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
    
    def crawl_ai_news(self) -> List[Dict]:
        """爬取AI资讯"""
        url = self.source_urls.get(self.source, self.source_urls['ai_qianxun'])
        return self.crawl(url)


class AIHotSpider:
    """
    AI HOT 热点信息爬虫
    数据来源: https://aihot.virxact.com
    API调用方式获取数据，比网页解析更稳定
    """
    
    BASE_URL = "https://aihot.virxact.com"
    DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 aihot-skill/0.2.0"
    
    # 分类映射
    CATEGORIES = {
        "ai-models": "模型发布/更新",
        "ai-products": "产品发布/更新",
        "industry": "行业动态",
        "paper": "论文研究",
        "tip": "技巧与观点",
    }
    
    def __init__(self, user_agent: str = None):
        self.user_agent = user_agent or self.DEFAULT_UA
    
    def _build_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
    
    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """发送API请求"""
        import logging
        logger = logging.getLogger(__name__)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = requests.get(
                url, 
                params=params, 
                headers=self._build_headers(),
                timeout=30,
                allow_redirects=True
            )
            
            logger.info(f"[AIHotSpider] 请求 {url}, 状态码: {response.status_code}")
            
            # 检查状态码
            if response.status_code != 200:
                logger.warning(f"[AIHotSpider] 非200状态码: {response.status_code}, 响应: {response.text[:200]}")
                return None
            
            content = response.text.strip()
            
            # 检查返回的是否为HTML
            if content.startswith('<'):
                logger.warning(f"[AIHotSpider] 响应为HTML而非JSON: {content[:100]}")
                return None
            
            return json.loads(content)
        except requests.exceptions.Timeout:
            logger.error(f"[AIHotSpider] 请求超时: {url}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[AIHotSpider] 连接错误: {url}, {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"[AIHotSpider] JSON解析错误: {e}, 响应: {content[:200] if 'content' in dir() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"[AIHotSpider] 请求失败: {url}, {e}")
            return None
    
    def get_items(self, mode: str = "selected", category: str = None, 
                  since: str = None, days: int = 7, take: int = 50) -> List[Dict]:
        """
        获取AI热点条目
        
        Args:
            mode: 'selected' 精选 / 'all' 全部
            category: 分类筛选 (ai-models/ai-products/industry/paper/tip)
            since: ISO格式时间起点
            days: 最近天数（与since互斥）
            take: 返回条数 (1-100)
        
        Returns:
            条目列表
        """
        import logging
        logger = logging.getLogger(__name__)
        
        params = {"mode": mode, "take": min(take, 100)}
        
        if category and category in self.CATEGORIES:
            params["category"] = category
        
        if since:
            params["since"] = since
        elif days:
            since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["since"] = since_date
        
        logger.info(f"[AIHotSpider] get_items: mode={mode}, days={days}, take={take}")
        
        result = self._request("/api/public/items", params)
        if result and "items" in result:
            logger.info(f"[AIHotSpider] 获取到 {len(result['items'])} 条数据")
            return result["items"]
        
        logger.warning("[AIHotSpider] API返回空或无items字段，将使用备用源")
        return []
    
    def get_daily(self, date: str = None) -> Optional[Dict]:
        """
        获取日报
        
        Args:
            date: YYYY-MM-DD格式日期，不传则获取最新日报
        
        Returns:
            日报数据
        """
        endpoint = "/api/public/daily"
        if date:
            endpoint = f"/api/public/daily/{date}"
        return self._request(endpoint)
    
    def get_daily_list(self) -> List[Dict]:
        """获取日报列表"""
        result = self._request("/api/public/dailies")
        if result and "items" in result:
            return result["items"]
        return []
    
    def search(self, keyword: str, take: int = 20) -> List[Dict]:
        """
        关键词搜索
        
        Args:
            keyword: 搜索关键词 (2-200字)
            take: 返回条数
        
        Returns:
            匹配的条目列表
        """
        if len(keyword) < 2:
            return []
        
        params = {"q": keyword, "take": min(take, 100)}
        result = self._request("/api/public/items", params)
        if result and "items" in result:
            return result["items"]
        return []
    
    def format_item(self, item: Dict) -> Dict:
        """
        格式化单个条目为标准文章格式
        
        Args:
            item: API返回的原始条目
        
        Returns:
            标准化的文章字典
        """
        category = item.get("category")
        category_text = self.CATEGORIES.get(category, category or "未分类") if category else "未分类"
        
        published = item.get("publishedAt", "")
        publish_date = None
        if published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                publish_date = dt
            except:
                pass
        
        # 构建摘要
        summary = item.get("summary", "")
        if not summary and item.get("leadParagraph"):
            summary = item["leadParagraph"]
        
        return {
            'title': item.get('title', '无标题'),
            'url': item.get('url', ''),
            'summary': summary,
            'content': item.get('content', '') or summary,
            'publish_date': publish_date,
            'source': item.get('source', 'aihot') or 'aihot',
            'source_name': item.get('sourceName', 'AI HOT'),
            'category': category_text,
            'tags': item.get('tags', ''),
        }


class JiemoduiScraper(BaseScraper):
    """芥末堆专用爬虫 - 采集近7天文章"""
    
    BASE_URL = 'https://www.jiemodui.com'
    ARTICLE_URL_TEMPLATE = 'https://www.jiemodui.com/N/{article_id}.html'
    
    def __init__(self, cookie_manager: CookieManager = None, start_article_id: int = 139375):
        super().__init__(cookie_manager)
        self.source = 'jiemodui'
        self.source_name = '芥末堆'
        # 默认从ID 139375开始
        self.start_article_id = start_article_id
    
    def _get_latest_article_id(self) -> int:
        """获取最新文章的ID"""
        url = f'{self.BASE_URL}/N/index.html'
        response = self.request_with_retry(url, use_cookie_pool=False)
        if response:
            soup = BeautifulSoup(response.text, 'lxml')
            # 查找最新的文章链接
            link = soup.select_one('a[href*="/N/"]')
            if link:
                href = link.get('href', '')
                import re
                match = re.search(r'/N/(\d+)\.html', href)
                if match:
                    return int(match.group(1))
        return 139375  # 默认起始ID
    
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析文章列表 - 芥末堆"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 芥末堆文章列表选择器
        selectors = [
            '.item-box',
            '.news-item',
            '.article-item',
            '.post-item',
            'article',
            '[class*="item"]',
            '[class*="news"]',
            '[class*="article"]'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 1:
                for item in items:
                    try:
                        link_elem = item.select_one('a[href*="/N/"]')
                        title_elem = item.select_one('h2, h3, h4, .title, .tit, [class*="title"]')
                        
                        if not title_elem and link_elem:
                            title = link_elem.get_text(strip=True)
                        elif title_elem:
                            title = title_elem.get_text(strip=True)
                        else:
                            continue
                        
                        if not title or len(title) < 5:
                            continue
                        
                        href = ''
                        if link_elem:
                            href = link_elem.get('href', '')
                            if href and not href.startswith('http'):
                                href = self.BASE_URL + href
                        
                        summary_elem = item.select_one('.summary, .desc, .excerpt, .intro, [class*="summary"], [class*="desc"]')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ''
                        
                        date_elem = item.select_one('.date, .time, .pub-time, [class*="date"], [class*="time"]')
                        date_str = date_elem.get_text(strip=True) if date_elem else None
                        
                        articles.append({
                            'title': title,
                            'url': href,
                            'summary': summary,
                            'publish_date': self._parse_date(date_str),
                            'source': self.source,
                            'source_name': self.source_name
                        })
                    except Exception:
                        continue
                break
        
        return articles
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析芥末堆文章详情
        
        页面结构（Nuxt.js）：
        - 标题: <h1 data-v-15a4ed60="">xxx</h1>
        - 发布时间: #__nuxt > div > div.NItem > div.infoBox > div.time
        - 正文: <article class="content" data-v-15a4ed60="">...</article>
        """
        response = self.request_with_retry(url, use_cookie_pool=False)
        if not response:
            return None
        
        html_text = response.text
        
        # 尝试从 script 标签中提取 JSON 数据（Nuxt.js）
        import re
        title = ''
        author = ''
        date_str = ''
        content = ''
        
        # 尝试从 __NUXT__ 或 window.__NUXT__ 中提取
        nuxt_match = re.search(r'window\.__NUXT__\s*=\s*({.*?})\s*</script>', html_text, re.DOTALL)
        if nuxt_match:
            try:
                import json as json_module
                nuxt_data = json_module.loads(nuxt_match.group(1))
                # 递归查找数据
                def find_in_nuxt(obj, path=''):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            new_path = f'{path}.{key}' if path else key
                            if key in ['title', 'Title'] and isinstance(value, str):
                                return ('title', value)
                            elif key in ['author', 'Author', 'authorName'] and isinstance(value, str):
                                return ('author', value)
                            elif key in ['createdAt', 'publishTime', 'publish_date', 'created_at', 'time'] and isinstance(value, (str, int)):
                                return ('date', str(value))
                            elif key in ['content', 'body', 'html'] and isinstance(value, str):
                                return ('content', value)
                            result = find_in_nuxt(value, new_path)
                            if result:
                                return result
                    elif isinstance(obj, list) and len(obj) > 0:
                        for i, item in enumerate(obj[:3]):
                            result = find_in_nuxt(item, f'{path}[{i}]')
                            if result:
                                return result
                    return None
                
                # 从 Nuxt 数据中提取
                for key in ['data', 'state', 'routeState']:
                    if key in nuxt_data:
                        result = find_in_nuxt(nuxt_data[key])
                        if result:
                            if result[0] == 'title' and not title:
                                title = result[1]
                            elif result[0] == 'author' and not author:
                                author = result[1]
                            elif result[0] == 'date' and not date_str:
                                date_str = result[1]
                            elif result[0] == 'content' and not content:
                                content = result[1]
            except Exception as e:
                print(f"[芥末堆] 解析 Nuxt 数据失败: {e}")
        
        # 从 HTML 中提取
        soup = BeautifulSoup(html_text, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 如果标题未提取到，尝试从 DOM 获取
        if not title:
            title_elem = soup.select_one('h1[data-v-15a4ed60]')
            if not title_elem:
                title_elem = soup.select_one('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        # 如果作者未提取到，尝试从 DOM 获取
        if not author:
            info_box = soup.select_one('.infoBox')
            if info_box:
                author_elem = info_box.select_one('a[data-v-15a4ed60]')
                if author_elem:
                    author = author_elem.get_text(strip=True)
            if not author:
                author_elem = soup.select_one('.author, [class*="author"]')
                if author_elem:
                    author = author_elem.get_text(strip=True)
        
        # 如果时间未提取到，尝试从 DOM 获取
        if not date_str:
            time_elem = soup.select_one('#__nuxt > div > div.NItem > div.infoBox > div.time')
            if not time_elem:
                time_elem = soup.select_one('div.time[data-v-15a4ed60]')
            if time_elem:
                text = time_elem.get_text(strip=True)
                if '发布时间' in text:
                    date_str = text.split('发布时间：')[-1].strip()
                else:
                    date_str = text.strip()
            if not date_str:
                time_elem = soup.select_one('.time, [class*="time"]')
                if time_elem:
                    date_str = time_elem.get_text(strip=True)
        
        # 如果正文未提取到，尝试从 DOM 获取
        if not content:
            content_elem = soup.select_one('article.content[data-v-15a4ed60]')
            if not content_elem:
                content_elem = soup.select_one('article.content')
            if not content_elem:
                content_elem = soup.select_one('#main-content, .article-content, article')
        
        content = ''
        if content_elem:
            # 提取纯文本，保留段落结构
            paragraphs = []
            for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
            content = '\n\n'.join(paragraphs)
        
        publish_date = self._parse_date(date_str) if date_str else None
        
        return {
            'title': title,
            'author': author,
            'content': content,
            'url': url,
            'publish_date': publish_date,
            'publish_date_str': date_str,  # 保留原始时间字符串
            'source': self.source,
            'source_name': self.source_name
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None
        try:
            date_str = date_str.strip()
            if 'T' in date_str:
                # 优先尝试完整 ISO 时间格式（保留时分秒）
                iso_formats = [
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S%z',
                    '%Y-%m-%dT%H:%M',
                ]
                for fmt in iso_formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                # 降级：仅保留日期部分
                date_str = date_str.split('T')[0]
            # 常见格式
            formats = [
                '%m/%d/%Y, %I:%M:%S %p',  # 美式 12小时制: 5/20/2026, 9:01:21 AM
                '%m/%d/%Y, %I:%M %p',     # 美式 12小时制: 5/20/2026, 9:01 AM
                '%m/%d/%Y',               # 美式: 5/20/2026
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%Y年%m月%d日 %H:%M:%S',
                '%Y年%m月%d日 %H:%M',
                '%Y年%m月%d日'
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
    
    def crawl_articles_in_range(self, days: int = None, existing_urls: set = None) -> List[Dict]:
        """从起始ID开始，依次+1采集所有文章
        
        Args:
            days: 保留参数（向后兼容），不再限制天数
            existing_urls: 已存在的URL集合，用于跳过已采集的文章
        
        Returns:
            采集到的文章列表
        """
        if existing_urls is None:
            existing_urls = set()
        
        articles = []
        checked_count = 0
        consecutive_empty = 0
        consecutive_empty_limit = 10  # 连续10个空文章则停止
        
        print(f"[芥末堆] 从ID {self.start_article_id} 开始采集，依次+1遍历所有文章...")
        
        article_id = self.start_article_id
        
        while consecutive_empty < consecutive_empty_limit:
            article_id_str = str(article_id)
            url = self.ARTICLE_URL_TEMPLATE.format(article_id=article_id_str)
            
            # 跳过已存在的文章
            if url in existing_urls:
                consecutive_empty = 0  # 重置（因为这是已知文章）
                article_id += 1
                checked_count += 1
                continue
            
            print(f"[芥末堆] 检查文章 ID: {article_id} ...")
            
            try:
                article_detail = self.parse_article_detail(url)
                
                if article_detail and article_detail.get('title'):
                    publish_date = article_detail.get('publish_date')
                    
                    # 检查正文是否有内容
                    content = article_detail.get('content', '')
                    if content and len(content) > 100:
                        articles.append(article_detail)
                        existing_urls.add(url)
                        consecutive_empty = 0  # 重置
                        date_str = publish_date.strftime('%Y/%m/%d') if publish_date else '未知'
                        print(f"[芥末堆] ✓ 采集成功: {article_detail.get('title')[:50]}... ({date_str})")
                    else:
                        print(f"[芥末堆] 文章正文内容不足或为空，跳过")
                        consecutive_empty += 1
                    
                    # 每采集一篇休息一下
                    time.sleep(random.uniform(1, 2))
                else:
                    # 文章不存在或解析失败
                    print(f"[芥末堆] 文章不存在或解析失败 (ID: {article_id})")
                    consecutive_empty += 1
                    time.sleep(random.uniform(0.5, 1))
            
            except Exception as e:
                print(f"[芥末堆] 采集文章 {article_id} 出错: {e}")
                consecutive_empty += 1
                time.sleep(random.uniform(1, 2))
            
            article_id += 1
            checked_count += 1
            
            # 每100篇输出一次进度
            if checked_count % 100 == 0:
                print(f"[芥末堆] 已检查 {checked_count} 篇，已采集 {len(articles)} 篇，当前ID: {article_id}")
        
        print(f"[芥末堆] 采集完成，共采集 {len(articles)} 篇文章，检查了 {checked_count} 篇")
        return articles
    
    def crawl_education_news(self) -> List[Dict]:
        """爬取芥末堆所有文章"""
        return self.crawl_articles_in_range()


class DuozhiScraper(BaseScraper):
    """多知网专用爬虫
    
    URL格式: http://www.duozhi.com/industry/insight/{date}{id}.shtml
    例如: http://www.duozhi.com/industry/insight/2026051418496.shtml
    
    采集策略：
    - 爬取多知网观察栏目页面，使用HTML解析获取文章列表
    - 最多采集10篇文章（默认）
    - 遇到重复文章时跳过
    """
    
    BASE_URL = 'http://www.duozhi.com'
    LIST_URL = 'http://www.duozhi.com/industry/insight/'  # 观察栏目URL
    SOURCE_NAME = 'duozhi'
    
    def __init__(self, cookie_manager: CookieManager = None, max_articles: int = 10):
        super().__init__(cookie_manager)
        self.source = self.SOURCE_NAME
        self.source_name = '多知网'
        self.max_articles = max_articles  # 默认只采集10篇
    
    def _parse_date_from_url(self, url: str) -> str:
        """从URL中提取日期，如 2026051418496 -> 20260514"""
        import re
        match = re.search(r'(\d{8})\d{4}', url)
        return match.group(1) if match else None
    
    def _get_progress(self) -> tuple:
        """获取爬取进度 (last_article_id, last_article_date, last_crawl_date)
        
        从CrawlProgress表中读取进度，如果不存在则返回初始值
        """
        from models import CrawlProgress, db
        progress = CrawlProgress.query.filter_by(source=self.SOURCE_NAME).first()
        if progress:
            return progress.last_article_id, progress.last_article_date, progress.last_crawl_date
        return self.INITIAL_ARTICLE_ID, None, None
    
    def _save_progress(self, last_article_id: int, last_article_date: str):
        """保存爬取进度"""
        from models import CrawlProgress, db
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        progress = CrawlProgress.query.filter_by(source=self.SOURCE_NAME).first()
        if progress:
            progress.last_article_id = last_article_id
            progress.last_article_date = last_article_date
            progress.last_crawl_date = today
        else:
            progress = CrawlProgress(
                source=self.SOURCE_NAME,
                last_article_id=last_article_id,
                last_article_date=last_article_date,
                last_crawl_date=today
            )
            db.session.add(progress)
        db.session.commit()
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析多知网文章详情"""
        response = self.request_with_retry(url, use_cookie_pool=False)
        if not response:
            return None
        
        # 处理编码问题
        html_text = ''
        # 尝试多种编码
        for encoding in ['gb18030', 'gbk', 'gb2312', 'utf-8', 'big5']:
            try:
                html_text = response.content.decode(encoding, errors='strict')
                # 验证是否解码成功（检查是否包含常见中文字符）
                if '的一是了我' in html_text or '的' in html_text or 'html' in html_text.lower():
                    break
            except Exception:
                continue
        
        if not html_text or html_text == '':
            html_text = response.content.decode('utf-8', errors='ignore')
        
        soup = BeautifulSoup(html_text, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 提取标题
        title_elem = soup.select_one('body > div:nth-child(4) > div > div.c2 > div.subject > h1')
        if not title_elem:
            title_elem = soup.select_one('h1')
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # 提取时间和作者信息
        meta_elem = soup.select_one('body > div:nth-child(4) > div > div.c2 > div.subject > div.subject-meta')
        if not meta_elem:
            meta_elem = soup.select_one('[class*="subject-meta"]')
        
        date_str = ''
        author = ''
        if meta_elem:
            meta_text = meta_elem.get_text(strip=True)
            import re
            time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})发布', meta_text)
            if time_match:
                date_str = time_match.group(1)
            
            author_match = re.search(r'作者：(\S+)', meta_text)
            if author_match:
                author = author_match.group(1)
        
        # 提取正文内容
        content_elem = soup.select_one('body > div:nth-child(4) > div > div.c2 > div.subject > div.subject-content')
        if not content_elem:
            content_elem = soup.select_one('[class*="subject-content"]')
        if not content_elem:
            content_elem = soup.select_one('article, .article-content, .content')
        
        content = ''
        if content_elem:
            paragraphs = []
            for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
            content = '\n\n'.join(paragraphs)
        
        publish_date = self._parse_date(date_str) if date_str else None
        
        return {
            'title': title,
            'author': author,
            'content': content,
            'url': url,
            'publish_date': publish_date,
            'publish_date_str': date_str,
            'source': self.source,
            'source_name': self.source_name
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None
        try:
            date_str = date_str.strip()
            formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
    
    def check_url_status(self, url: str) -> tuple:
        """检查URL状态码
        
        Returns:
            tuple: (status_code, response) - 状态码和响应对象
        """
        try:
            import requests
            headers = self.get_headers()
            response = self.session.get(url, headers=headers, timeout=self.request_timeout)
            return response.status_code, response
        except requests.RequestException:
            return None, None
    
    def crawl_articles_in_range(self, existing_urls: set = None, max_articles: int = None) -> List[Dict]:
        """使用HTML解析爬取多知网文章
        
        策略：
        1. 访问多知网观察栏目页面
        2. 从HTML中解析文章列表（.post-main 元素）
        3. 提取文章URL、标题、摘要、日期等信息
        4. 支持分页爬取
        5. 最多采集指定数量文章（默认10篇）
        6. 遇到重复文章时跳过
        
        Args:
            existing_urls: 已存在的URL集合，用于跳过已采集的文章
            max_articles: 最大采集数量，默认从实例属性读取（默认10篇）
        
        Returns:
            采集到的文章列表
        """
        if existing_urls is None:
            existing_urls = set()
        
        # 使用实例属性中的默认值
        if max_articles is None:
            max_articles = self.max_articles
        
        articles = []
        skipped_duplicates = 0  # 跳过的重复文章数
        total_checked = 0  # 总共检查的文章数
        
        print(f"[多知网] 开始采集，最多 {max_articles} 篇")
        
        # 分页爬取列表页
        page = 1
        max_pages = 20  # 最多爬取20页
        
        while page <= max_pages and len(articles) < max_articles:
            # 构建分页URL
            if page == 1:
                list_url = self.LIST_URL
            else:
                list_url = f"{self.LIST_URL}index_{page}.shtml"
            
            print(f"[多知网] 获取列表页第 {page} 页: {list_url}")
            
            try:
                response = self.request_with_retry(list_url, use_cookie_pool=False)
                
                if not response:
                    print(f"[多知网] 第 {page} 页请求失败，停止")
                    break
                
                # 处理编码问题
                html_text = ''
                for encoding in ['utf-8', 'gb18030', 'gbk', 'gb2312']:
                    try:
                        html_text = response.content.decode(encoding, errors='strict')
                        if '多知' in html_text or 'duozhi' in html_text.lower():
                            break
                    except Exception:
                        continue
                
                if not html_text:
                    html_text = response.content.decode('utf-8', errors='ignore')
                
                # 解析文章列表
                page_articles = self._parse_article_list(html_text)
                
                if not page_articles:
                    print(f"[多知网] 第 {page} 页无文章，停止")
                    break
                
                print(f"[多知网] 第 {page} 页解析到 {len(page_articles)} 篇文章")
                
                page_count = 0
                
                for article_data in page_articles:
                    if len(articles) >= max_articles:
                        break
                    
                    url = article_data.get('url', '')
                    if not url:
                        continue
                    
                    total_checked += 1
                    
                    # 跳过已存在的文章
                    if url in existing_urls:
                        skipped_duplicates += 1
                        print(f"[多知网] 跳过重复文章: {article_data.get('title', '')[:30]}...")
                        continue
                    
                    print(f"[多知网] 详情页: {article_data.get('title', '')[:40]}...")
                    
                    # 爬取详情
                    article_detail = self.parse_article_detail(url)
                    
                    if article_detail and article_detail.get('title'):
                        content = article_detail.get('content', '')
                        if content and len(content) > 50:
                            # 合并列表页获取的信息
                            article_detail['summary'] = article_data.get('summary', '') or article_detail.get('summary', '')
                            articles.append(article_detail)
                            existing_urls.add(url)
                            page_count += 1
                            print(f"[多知网] ✓ 采集成功: {article_detail.get('title')[:40]}...")
                        else:
                            print(f"[多知网] 正文内容不足")
                    else:
                        print(f"[多知网] 解析失败")
                    
                    time.sleep(random.uniform(1, 2))
                
                print(f"[多知网] 第 {page} 页完成: 采集{page_count}篇")
                
                # 如果本页采集的文章少于预期，可能没有更多页了
                if len(page_articles) < 10:
                    print(f"[多知网] 文章数量少于10篇，可能已到尾页")
                    break
                
                page += 1
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"[多知网] 第 {page} 页出错: {e}")
                break
        
        print(f"\n[多知网] 采集完成，共采集 {len(articles)} 篇文章（跳过 {skipped_duplicates} 篇重复文章）")
        return articles
    
    def _parse_article_list(self, html: str) -> List[Dict]:
        """解析多知网文章列表
        
        HTML结构:
        <div class="post-main">
            <div class="post-inner">
                <a class="post-title" href="...">文章标题</a>
                <p class="post-desc">描述</p>
                <span class="post-attr">TCOH</span>
                <span class="post-tag"><a class="link-tag" href="...">观察</a></span>
            </div>
            <div class="post-attr">2026-05-19  | by 多知</div>
        </div>
        """
        articles = []
        import re
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 查找所有文章卡片
        post_mains = soup.select('.post-main')
        
        for post in post_mains:
            try:
                # 提取标题和链接
                title_elem = post.select_one('.post-title')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                if not title or not url:
                    continue
                
                # 确保URL是完整的
                if not url.startswith('http'):
                    url = self.BASE_URL + url
                
                # 提取摘要
                desc_elem = post.select_one('.post-desc')
                summary = desc_elem.get_text(strip=True) if desc_elem else ''
                
                # 提取日期
                date_str = ''
                attr_elems = post.select('.post-attr')
                for attr in attr_elems:
                    text = attr.get_text(strip=True)
                    # 匹配日期格式: 2026-05-19  | by 多知
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*\|', text)
                    if date_match:
                        date_str = date_match.group(1)
                        break
                
                # 提取作者/标签
                author = ''
                tag = ''
                for attr in attr_elems:
                    text = attr.get_text(strip=True)
                    if 'by' in text.lower():
                        author_match = re.search(r'by\s*(\S+)', text)
                        if author_match:
                            author = author_match.group(1)
                
                tag_elems = post.select('.post-tag .link-tag')
                if tag_elems:
                    tag = tag_elems[0].get_text(strip=True)
                
                # 解析发布日期
                publish_date = None
                if date_str:
                    try:
                        publish_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        pass
                
                articles.append({
                    'title': title,
                    'url': url,
                    'summary': summary,
                    'author': author,
                    'tag': tag,
                    'publish_date': publish_date,
                    'publish_date_str': date_str,
                    'source': self.source,
                    'source_name': self.source_name
                })
                
            except Exception as e:
                print(f"[多知网] 解析文章卡片出错: {e}")
                continue
        
        return articles
    
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析文章列表 - 多知网"""
        return self._parse_article_list(html)
    
    def crawl(self, url: str = None) -> List[Dict]:
        """执行爬取"""
        return self.crawl_articles_in_range()


class CctvScraper(BaseScraper):
    """央视网教育新闻爬虫
    
    列表页: https://news.cctv.com/edu/
    文章URL格式: https://news.cctv.com/2026/05/18/ARTIVlUU9RU2gar3Ys9qcgPl260518.shtml
    
    策略：从列表页卡片中提取所有文章URL，然后逐个爬取详情
    """
    
    BASE_URL = 'https://news.cctv.com'
    LIST_URL = 'https://news.cctv.com/edu/'
    SOURCE_NAME = 'cctv'
    SOURCE_DISPLAY_NAME = '央视网'
    
    # 默认采集天数
    DEFAULT_DAYS = 30
    
    def __init__(self, cookie_manager: CookieManager = None, days: int = None, max_articles: int = 10):
        super().__init__(cookie_manager)
        self.source = self.SOURCE_NAME
        self.source_name = self.SOURCE_DISPLAY_NAME
        self.days = days or self.DEFAULT_DAYS
        self.max_articles = max_articles  # 默认只采集10篇
    
    def _get_progress(self) -> tuple:
        """获取爬取进度"""
        from models import CrawlProgress, db
        progress = CrawlProgress.query.filter_by(source=self.SOURCE_NAME).first()
        if progress:
            return progress.last_article_id, progress.last_article_date, progress.last_crawl_date
        return None, None, None
    
    def _save_progress(self, last_date: str):
        """保存爬取进度"""
        from models import CrawlProgress, db
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        progress = CrawlProgress.query.filter_by(source=self.SOURCE_NAME).first()
        if progress:
            progress.last_article_date = last_date
            progress.last_crawl_date = today
        else:
            progress = CrawlProgress(
                source=self.SOURCE_NAME,
                last_article_id=0,
                last_article_date=last_date,
                last_crawl_date=today
            )
            db.session.add(progress)
        db.session.commit()
    
    def parse_article_list(self, html: str, date_str: str = None) -> List[Dict]:
        """解析央视网教育新闻列表
        
        支持两种方式：
        1. JSONP API: 从 API 获取文章列表
        2. HTML: 从页面HTML提取文章列表
        """
        import re
        import json
        articles = []
        seen_urls = set()
        
        # 尝试解析JSONP格式的API响应
        # 格式: edu({"data":{"list":[...]}})
        try:
            # 简单匹配: 函数名(...)
            jsonp_match = re.match(r'(\w+)\((\{.*\})\)', html.strip(), re.DOTALL)
            if jsonp_match:
                json_str = jsonp_match.group(2)
                data = json.loads(json_str)
                article_list = data.get('data', {}).get('list', [])
                
                if article_list:
                    print(f"[央视网] API返回 {len(article_list)} 篇文章")
                    
                    for item in article_list:
                        url = item.get('url', '')
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        # 清理URL
                        clean_url = re.split(r'\?', url)[0]
                        
                        # 提取日期
                        focus_date = item.get('focus_date', '')
                        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', focus_date)
                        article_date_str = None
                        if date_match:
                            article_date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                        
                        articles.append({
                            'title': item.get('title', ''),
                            'url': clean_url,
                            'summary': item.get('brief', '')[:200],
                            'publish_date_str': article_date_str,
                            'tags': item.get('keywords', ''),
                            'source': self.source,
                            'source_name': self.source_name
                        })
                    
                    print(f"[央视网] 解析到 {len(articles)} 篇文章")
                    return articles
        except Exception as e:
            print(f"[央视网] JSONP解析失败: {e}")
        
        # 回退到HTML解析
        print("[央视网] 回退到HTML解析模式")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取所有URL
        url_pattern = r'href="(https?://news\.cctv\.com/20\d{2}/\d{2}/\d{2}/ARTI[^"]+\.shtml)'
        all_urls = re.findall(url_pattern, html)
        print(f"[央视网] HTML中找到 {len(all_urls)} 个文章URL")
        
        for href in all_urls:
            try:
                clean_url = re.split(r'\?', href)[0]
                if not clean_url or clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)
                
                # 从URL提取日期
                date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', clean_url)
                article_date_str = None
                if date_match:
                    article_date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                
                # 尝试从父级h3获取标题
                title = ''
                all_links = soup.find_all('a', href=re.compile(re.escape(clean_url).replace(r'\?', r'\?').replace('/', r'\/')))
                
                for link in all_links:
                    parent = link.parent
                    if parent and parent.name == 'h3':
                        title = parent.get_text(strip=True)
                        if title and len(title) > 5:
                            break
                    if parent:
                        grandparent = parent.parent
                        if grandparent and grandparent.name == 'h3':
                            title = grandparent.get_text(strip=True)
                            if title and len(title) > 5:
                                break
                
                if not title or len(title) < 5:
                    continue
                
                articles.append({
                    'title': title,
                    'url': clean_url,
                    'summary': '',
                    'publish_date_str': article_date_str,
                    'tags': '',
                    'source': self.source,
                    'source_name': self.source_name
                })
            except Exception as e:
                continue
        
        print(f"[央视网] 解析到 {len(articles)} 篇文章")
        return articles
    
    def _parse_date_str(self, date_text: str) -> Optional[str]:
        """解析日期文本"""
        if not date_text:
            return None
        import re
        # 匹配 YYYY-MM-DD 格式
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_text)
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return date_text.strip()
    
    def _cctv_request(self, url: str) -> Optional[str]:
        """央视网专用请求方法，完全独立，不使用任何cookie"""
        import requests
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                # 尝试检测编码
                encoding = response.encoding
                # 如果编码检测不对，强制使用UTF-8
                if encoding not in ['utf-8', 'UTF-8', 'utf8']:
                    encoding = 'utf-8'
                return response.content.decode(encoding, errors='ignore')
        except Exception as e:
            print(f"[央视网] 请求失败: {e}")
        return None
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析央视网文章详情
        
        页面结构：
        - 标题: <h1>标题</h1>
        - 来源: <div class="info">来源：<a>来源名</a>  |  2026年05月18日 15:11:43</div>
        - 正文: <div class="content_area" id="content_area">...</div>
        - 正文(备用): <div class="text_area" id="text_area">...</div>
        - 脚本中的内容: var contentdate = '...'
        
        注意：央视网使用UTF-8编码，不需要cookie，使用独立请求
        """
        # 使用独立请求，不使用session/cookie
        html_text = self._cctv_request(url)
        if not html_text:
            return None
        
        soup = BeautifulSoup(html_text, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 提取标题
        title_elem = soup.select_one('#title_area h1, .title_area h1, h1')
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # 提取来源、日期信息
        author = ''
        date_str = ''
        source_name = ''
        
        info_elem = soup.select_one('.info, .info1')
        if info_elem:
            info_text = info_elem.get_text(strip=True)
            import re
            
            # 提取来源
            source_match = re.search(r'来源：([^|<]+)', info_text)
            if source_match:
                source_name = source_match.group(1).strip()
            
            # 提取日期
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})', info_text)
            if date_match:
                year, month, day, hour, minute = date_match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}:00"
            else:
                # 尝试匹配日期
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', info_text)
                if date_match:
                    date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
        
        # 提取正文内容
        content = ''
        
        # 方法1: 从 content_area 提取
        content_elem = soup.select_one('#content_area, .content_area')
        if content_elem:
            paragraphs = []
            for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
            content = '\n\n'.join(paragraphs)
        
        # 方法2: 从 text_area 提取
        if not content:
            content_elem = soup.select_one('#text_area, .text_area')
            if content_elem:
                paragraphs = []
                for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                    text = p.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                content = '\n\n'.join(paragraphs)
        
        # 方法3: 从脚本变量中提取
        if not content:
            import re
            # 匹配 var contentdate 或 var content = '...'
            content_match = re.search(r"var\s+content(date)?\s*=\s*['\"](.+?)['\"]", html_text, re.DOTALL)
            if content_match:
                from html import unescape
                content = unescape(content_match.group(2))
                # 清理HTML标签
                content_soup = BeautifulSoup(content, 'lxml')
                content = content_soup.get_text(separator='\n', strip=True)
        
        # 提取发布作者/来源
        if not author:
            source_elem = soup.select_one('.source, [class*="source"]')
            if source_elem:
                author = source_elem.get_text(strip=True)
        
        publish_date = self._parse_date(date_str) if date_str else None
        
        return {
            'title': title,
            'author': author or source_name,
            'content': content,
            'url': url,
            'publish_date': publish_date,
            'publish_date_str': date_str,
            'source': self.source,
            'source_name': self.source_name
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None
        try:
            date_str = date_str.strip()
            formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y年%m月%d日']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
    
    def _get_page_urls(self) -> List[str]:
        """获取所有列表页URL
        
        央视网可能有分页，需要获取多页
        """
        urls = [self.LIST_URL]
        
        # 尝试获取更多分页
        try:
            response_text = self._cctv_request(self.LIST_URL)
            if response_text:
                soup = BeautifulSoup(response_text, 'lxml')
                
                # 查找分页
                page_links = soup.select('.page a, .pagination a, [class*="page"] a, a.page')
                for link in page_links:
                    href = link.get('href', '')
                    if href and 'news.cctv.com/edu' in href:
                        # 清理URL
                        import re
                        clean_url = re.split(r'\?', href)[0]
                        if clean_url not in urls:
                            urls.append(clean_url)
                
                # 也查找翻页链接 (使用 :-soup-contains 替代已废弃的 :contains)
                next_pages = soup.select('a[href*="index"], a[href*="list"], a:-soup-contains("下一页"), a:-soup-contains("下页")')
                for link in next_pages:
                    href = link.get('href', '')
                    if href and 'news.cctv.com/edu' in href and href not in urls:
                        import re
                        clean_url = re.split(r'\?', href)[0]
                        urls.append(clean_url)
        except Exception as e:
            print(f"[央视网] 获取分页失败: {e}")
        
        return urls
    
    def crawl_articles_in_range(self, existing_urls: set = None, max_articles: int = None) -> List[Dict]:
        """使用JSONP API爬取央视网教育新闻
        
        策略：
        1. 使用央视网JSONP API获取文章列表（支持分页）
        2. 从API响应中解析文章URL和基本信息
        3. 按日期过滤（只采集指定天数内的文章）
        4. 逐个爬取文章详情，遇到重复文章时跳过
        
        Args:
            existing_urls: 已存在的URL集合，用于跳过已采集的文章
            max_articles: 最大采集数量，默认从实例属性读取（默认10篇）
        
        Returns:
            采集到的文章列表
        """
        if existing_urls is None:
            existing_urls = set()
        
        # 使用实例属性中的默认值
        if max_articles is None:
            max_articles = self.max_articles
        
        from datetime import datetime, timedelta
        
        # 计算截止日期
        cutoff_date = datetime.now() - timedelta(days=self.days)
        
        articles = []
        skipped_duplicates = 0  # 跳过的重复文章数
        total_checked = 0  # 总共检查的文章数
        
        print(f"[央视网] 开始采集，最多 {max_articles} 篇")
        
        # 使用JSONP API获取文章列表
        page = 1
        total_pages = 10  # 初始估计
        
        while page <= total_pages and len(articles) < max_articles:
            # 构建API URL
            api_url = f"https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/edu_{page}.jsonp"
            print(f"[央视网] 获取API第 {page} 页: {api_url}")
            
            try:
                api_response = self._cctv_request(api_url)
                
                if not api_response or len(api_response) < 100:
                    print(f"[央视网] API第 {page} 页无数据，停止")
                    break
                
                # 解析API响应
                list_articles = self.parse_article_list(api_response)
                
                if not list_articles:
                    print(f"[央视网] API第 {page} 页解析失败，停止")
                    break
                
                page_count = 0
                
                for article_data in list_articles:
                    if len(articles) >= max_articles:
                        break
                    
                    url = article_data.get('url', '')
                    if not url:
                        continue
                    
                    # 跳过已存在的文章
                    if url in existing_urls:
                        skipped_duplicates += 1
                        print(f"[央视网] 跳过重复文章: {article_data.get('title', '')[:30]}...")
                        continue
                    
                    # 日期过滤
                    publish_date_str = article_data.get('publish_date_str')
                    if publish_date_str:
                        try:
                            article_date = datetime.strptime(publish_date_str, '%Y-%m-%d')
                            if article_date < cutoff_date:
                                print(f"[央视网] 文章日期 {publish_date_str} 早于截止日期，停止采集")
                                # 由于文章按时间排序，遇到早于截止日期的文章可以停止
                                page = total_pages + 1
                                break
                        except:
                            pass
                    
                    print(f"[央视网] 详情页: {article_data.get('title', '')[:40]}...")
                    
                    # 爬取详情
                    article_detail = self.parse_article_detail(url)
                    
                    if article_detail and article_detail.get('title'):
                        content = article_detail.get('content', '')
                        if content and len(content) > 50:
                            articles.append(article_detail)
                            existing_urls.add(url)
                            page_count += 1
                            print(f"[央视网] ✓ 采集成功: {article_detail.get('title')[:40]}...")
                        else:
                            print(f"[央视网] 正文内容不足")
                    else:
                        print(f"[央视网] 解析失败")
                    
                    time.sleep(random.uniform(1, 2))
                
                print(f"[央视网] 第 {page} 页完成: 采集{page_count}篇")
                
                # 尝试从响应中获取总页数
                import re
                total_match = re.search(r'"total"\s*:\s*"?(\d+)"?', api_response)
                if total_match:
                    total = int(total_match.group(1))
                    # 每页约10-15篇，计算总页数
                    total_pages = min((total // 10) + 2, 100)  # 最多100页
                
                page += 1
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"[央视网] API第 {page} 页出错: {e}")
                break
        
        print(f"\n[央视网] 采集完成，共采集 {len(articles)} 篇文章（跳过 {skipped_duplicates} 篇重复文章）")
        return articles

    def crawl(self, url: str = None) -> List[Dict]:
        """执行爬取"""
        return self.crawl_articles_in_range()


class EducationNewsScraper(BaseScraper):
    """教育资讯爬虫（支持多数据源）"""
    
    def __init__(self, source: str = 'jiemodui', cookie_manager: CookieManager = None):
        super().__init__(cookie_manager)
        self.source = source
        self.source_urls = {
            'jiemodui': 'https://www.jiemodui.com/',
            'duozhi': 'https://www.duozhi.com/',
        }
    
    def parse_article_list(self, html: str) -> List[Dict]:
        """解析教育资讯列表"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        base_url = self.source_urls.get(self.source, 'https://www.jiemodui.com')
        
        # 根据不同网站选择器
        if self.source == 'jiemodui':
            selectors = [
                '.item-box',
                '.news-item',
                '.article-item',
                '.post-item',
                '.entry-item',
                'article',
                '[class*="item"]',
                '[class*="news"]'
            ]
        else:  # duozhi
            selectors = [
                '.article-item',
                '.post-item',
                '.news-item',
                '.entry-item',
                'article',
                '[class*="article"]',
                '[class*="post"]'
            ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 1:  # 确保找到多个
                for item in items:
                    try:
                        # 提取标题和链接
                        link_elem = item.select_one('a[href]')
                        title_elem = item.select_one('h2, h3, h4, .title, .tit, [class*="title"]')
                        
                        if not title_elem and link_elem:
                            title = link_elem.get_text(strip=True)
                        elif title_elem:
                            title = title_elem.get_text(strip=True)
                        else:
                            continue
                        
                        if not title or len(title) < 5:
                            continue
                        
                        # 获取链接
                        href = ''
                        if link_elem:
                            href = link_elem.get('href', '')
                            if href and not href.startswith('http'):
                                href = base_url.rstrip('/') + '/' + href.lstrip('/')
                        
                        # 获取摘要
                        summary_elem = item.select_one('.summary, .desc, .excerpt, .intro, [class*="summary"], [class*="desc"]')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ''
                        
                        # 获取日期
                        date_elem = item.select_one('.date, .time, .pub-time, [class*="date"], [class*="time"]')
                        date_str = date_elem.get_text(strip=True) if date_elem else None
                        
                        articles.append({
                            'title': title,
                            'url': href,
                            'summary': summary,
                            'publish_date': self._parse_date(date_str),
                            'source': self.source,
                            'source_name': '芥末堆' if self.source == 'jiemodui' else '多知网'
                        })
                    except Exception as e:
                        continue
                break
        
        return articles
    
    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析文章详情"""
        response = self.request_with_retry(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 移除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        # 提取标题
        title_elem = soup.select_one('h1, .article-title, .post-title, [class*="title"]')
        title = title_elem.get_text(strip=True) if title_elem else ''
        
        # 提取正文
        content_elem = soup.select_one('article, .article-content, .post-content, .entry-content, main, [role="main"], #main-content')
        
        # 提取日期
        date_elem = soup.select_one('.date, .time, .pub-time, [class*="date"], meta[property="article:published_time"]')
        date_str = None
        if date_elem:
            if date_elem.name == 'meta':
                date_str = date_elem.get('content', '')
            else:
                date_str = date_elem.get_text(strip=True)
        
        return {
            'title': title,
            'content': content_elem.get_text(separator='\n', strip=True) if content_elem else '',
            'url': url,
            'publish_date': self._parse_date(date_str) if date_str else datetime.utcnow(),
            'source': self.source
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期"""
        if not date_str:
            return None
        try:
            date_str = date_str.strip()
            # 处理 ISO 格式
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            # 常见格式
            formats = ['%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%Y年%m月%d日', '%Y年%m月%d日 %H:%M']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
    
    def crawl_education_news(self) -> List[Dict]:
        """爬取教育资讯"""
        url = self.source_urls.get(self.source, self.source_urls['jiemodui'])
        return self.crawl(url)


class CrawlScheduler:
    """爬取调度器"""
    
    def __init__(self):
        self.scrapers = {}
    
    def register_scraper(self, name: str, scraper: BaseScraper):
        self.scrapers[name] = scraper
    
    def crawl_all(self, callback: Callable = None) -> Dict[str, List[Dict]]:
        """爬取所有注册的数据源"""
        results = {}
        for name, scraper in self.scrapers.items():
            try:
                articles = scraper.crawl_ai_news() if isinstance(scraper, AINewsScraper) else scraper.crawl('')
                results[name] = articles
                if callback:
                    callback(name, articles)
            except Exception as e:
                results[name] = []
                print(f"爬取 {name} 失败: {str(e)}")
        return results

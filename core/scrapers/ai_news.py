"""
AI资讯爬虫模块
- AINewsScraper: 通用AI资讯爬虫（36kr备用源）
- AIHotSpider: AI HOT API 热点爬虫（优先使用）
"""
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.scrapers.base import BaseScraper
from core.cookie_manager import CookieManager


class AINewsScraper(BaseScraper):
    """AI资讯爬虫（备用源：36kr）"""

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

        selectors = [
            '.article-item', '.news-item',
            '[class*="article"]', '.post-item', '.article-list li'
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

        for script in soup(['script', 'style']):
            script.decompose()

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

            if response.status_code != 200:
                logger.warning(f"[AIHotSpider] 非200状态码: {response.status_code}, 响应: {response.text[:200]}")
                return None

            content = response.text.strip()

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
        """获取AI热点条目"""
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
        """获取日报"""
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
        """关键词搜索"""
        if len(keyword) < 2:
            return []

        params = {"q": keyword, "take": min(take, 100)}
        result = self._request("/api/public/items", params)
        if result and "items" in result:
            return result["items"]
        return []

    def format_item(self, item: Dict) -> Dict:
        """格式化单个条目为标准文章格式"""
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

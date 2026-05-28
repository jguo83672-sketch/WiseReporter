"""
微信公众号文章爬虫
"""
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from core.scrapers.base import BaseScraper
from core.cookie_manager import CookieManager
from core.wechat_scraper import WechatArticleSpider


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

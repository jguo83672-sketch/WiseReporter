"""
投融资/财报新闻爬虫
- 投资界 (pedaily.cn)：使用首页异步加载 + 无限滚动，覆盖教育赛道
"""

import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class PedailyScraper:
    """投资界投融资新闻爬虫（不支持 BaseScraper，独立实现）"""

    BASE_URL = 'https://news.pedaily.cn/'
    LIST_URL = 'https://news.pedaily.cn/'
    SOURCE_NAME = 'pedaily'
    SOURCE_DISPLAY_NAME = '投资界'
    DEFAULT_DAYS = 30
    # 投资界异步加载更多文章的分页接口（不带验证参数，直接 GET）
    MORE_API = 'https://news.pedaily.cn/index/indexmoredata'

    def __init__(self, days: int = None, max_articles: int = 15):
        self.days = days or self.DEFAULT_DAYS
        self.max_articles = max_articles

    def _request(self, url: str, params: dict = None) -> Optional[str]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.BASE_URL,
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                if resp.apparent_encoding:
                    resp.encoding = resp.apparent_encoding
                return resp.text
        except Exception as e:
            print(f"[投资界] 请求失败: {e}")
        return None

    def _resolve_url(self, href: str) -> str:
        if not href:
            return ''
        if href.startswith('http'):
            return href.split('?')[0]
        if href.startswith('//'):
            return 'https:' + href.split('?')[0]
        return urljoin(self.BASE_URL, href).split('?')[0]

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        if not date_text:
            return None
        date_text = date_text.strip()
        try:
            for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def parse_article_list_from_html(self, html: str) -> List[Dict]:
        """从 HTML 中解析 .masonry-list li 文章卡片"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')

        cards = soup.select('.masonry-list li')
        for card in cards:
            try:
                title_elem = card.select_one('.txt h3 a')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                if not href or not title:
                    continue

                url = self._resolve_url(href)

                date_elem = card.select_one('.date')
                date_str = date_elem.get_text(strip=True) if date_elem else ''

                author_elem = card.select_one('.author a')
                author = author_elem.get_text(strip=True) if author_elem else ''
                if not author:
                    author_elem = card.select_one('.author')
                    if author_elem:
                        author = author_elem.get_text(strip=True)

                # 提取封面图
                img_elem = card.select_one('.image img')
                cover = img_elem.get('data-src') or img_elem.get('src', '') if img_elem else ''

                articles.append({
                    'title': title,
                    'url': url,
                    'author': author,
                    'cover_image': cover,
                    'publish_date_str': date_str,
                })
            except Exception:
                continue

        return articles

    def _fetch_ajax_page(self, page: int) -> Optional[str]:
        """通过 AJAX 接口获取更多文章"""
        params = {
            'special': '',
            'channelid': '0',
            'indid': '0',
            'page': page,
        }
        return self._request(self.MORE_API, params=params)

    def collect_article_list(self, max_articles: int) -> List[Dict]:
        """从首页 + AJAX 分页收集文章列表"""
        articles = []
        seen_urls = set()

        # 第 1 步：抓取首页 HTML
        html = self._request(self.LIST_URL)
        if html:
            first_page = self.parse_article_list_from_html(html)
            for item in first_page:
                if item['url'] and item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    articles.append(item)

        # 第 2 步：通过 AJAX 接口加载更多页
        page = 1
        while len(articles) < max_articles and page <= 10:
            time.sleep(random.uniform(0.5, 1.0))
            ajax_html = self._fetch_ajax_page(page)
            if not ajax_html:
                break

            more_articles = self.parse_article_list_from_html(ajax_html)
            if not more_articles:
                break

            for item in more_articles:
                if item['url'] and item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    articles.append(item)

            page += 1
            print(f"[投资界] AJAX 第{page - 1}页获取 {len(more_articles)} 条")

        return articles[:max_articles]

    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析投资界文章详情页"""
        html = self._request(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')
        for tag in soup(['script', 'style']):
            tag.decompose()

        # 标题：优先从 .newsinfo h1 获取
        title = ''
        title_elem = soup.select_one('.newsinfo h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        if not title:
            for selector in ['h1', '.article-title', '.news-title']:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        break
        if not title:
            meta_title = soup.select_one('meta[property="og:title"]')
            if meta_title:
                title = meta_title.get('content', '')

        # 摘要：从 .newsinfo .subject 或 meta description 获取
        summary = ''
        subject_elem = soup.select_one('.newsinfo .subject')
        if subject_elem:
            summary = subject_elem.get_text(strip=True)
        if not summary:
            meta_desc = soup.select_one('meta[property="og:description"], meta[name="description"]')
            if meta_desc:
                summary = meta_desc.get('content', '')

        # 日期 & 作者：从 .newsinfo .info 解析（格式: "2026-05-28 10:51·新周刊朴珍珠"）
        date_str = ''
        author = ''
        source_name = self.SOURCE_DISPLAY_NAME

        # 方式1：从 .newsinfo .info 解析
        info_elem = soup.select_one('.newsinfo .info')
        if info_elem:
            info_text = info_elem.get_text(strip=True)
            # 提取日期时间
            date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}\s*\d{1,2}:\d{1,2})', info_text)
            if date_match:
                date_str = date_match.group(1)
            # 提取作者（· 后面的部分）
            author_match = re.search(r'[·|]\s*(.+)', info_text)
            if author_match:
                author_raw = author_match.group(1).strip()
                # 尝试分离来源和作者（如 "新周刊朴珍珠" -> 来源:新周刊, 作者:朴珍珠）
                source_elem = soup.select_one('.newsinfo .source')
                author_elem = soup.select_one('.newsinfo .author')
                if source_elem and author_elem:
                    source_name = source_elem.get_text(strip=True)
                    author = author_elem.get_text(strip=True)
                else:
                    author = author_raw

        # 方式2：meta 标签兜底
        if not date_str:
            for meta_name in ['article:published_time', 'weibo:article:create_at']:
                meta = soup.select_one(f'meta[name="{meta_name}"], meta[property="{meta_name}"]')
                if meta:
                    content = meta.get('content', '')
                    if content:
                        date_str = content[:19]
                        break

        if not author:
            meta_author = soup.select_one('meta[name="author"], meta[property="article:author"]')
            if meta_author:
                author = meta_author.get('content', '')

        # 正文：从 .news-content 提取
        content = ''
        content_selectors = [
            '.news-content',           # pedaily 主选择器
            '#article-content',
            '.article-content',
            '#content',
            '.article-body',
            '.text',
            '[class*="article-content"]',
        ]

        for sel in content_selectors:
            content_elem = soup.select_one(sel)
            if content_elem:
                # 移除干扰元素
                for bad in content_elem.select('.sharebox, .share, script, style, .ad, .advertisement'):
                    bad.decompose()

                paragraphs = []
                for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:
                        skip_patterns = [
                            '扫码', '扫一扫', '分享到', '微信', '版权声明',
                            '转载', '原文链接', '阅读原文', '点击上方',
                            'END', '加入微信群', '下载App', '推荐阅读'
                        ]
                        if not any(kw in text for kw in skip_patterns):
                            paragraphs.append(text)

                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                    break

        publish_date = self._parse_date(date_str) if date_str else None

        return {
            'title': title,
            'url': url,
            'author': author,
            'summary': summary,
            'content': content,
            'cover_image': '',  # 投融资资讯不需要封面图
            'publish_date': publish_date,
            'publish_date_str': date_str,
            'source_name': source_name,
            'source': self.SOURCE_NAME,
        }

    def crawl(self, existing_urls: set = None) -> List[Dict]:
        """执行爬取：收集列表 → 逐个解析详情"""
        if existing_urls is None:
            existing_urls = set()

        cutoff_date = datetime.now() - timedelta(days=self.days)
        result = []
        skipped = 0

        print(f"[投资界] 开始采集，最近 {self.days} 天，最多 {self.max_articles} 篇")
        list_articles = self.collect_article_list(self.max_articles * 3)  # 多取一些以防过滤
        print(f"[投资界] 列表共获取 {len(list_articles)} 条")

        for item in list_articles:
            if len(result) >= self.max_articles:
                break

            url = item['url']
            if url in existing_urls:
                skipped += 1
                continue

            # 日期过滤
            date_str = item.get('publish_date_str', '')
            if date_str:
                pub_date = self._parse_date(date_str)
                if pub_date and pub_date < cutoff_date:
                    continue

            print(f"[投资界] 详情: {item['title'][:40]}...")
            detail = self.parse_article_detail(url)
            time.sleep(random.uniform(1, 2))

            if detail and detail.get('title'):
                if detail.get('content') and len(detail.get('content', '')) > 50:
                    result.append(detail)
                    existing_urls.add(url)
                    print(f"[投资界] ✓ 采集成功")
                else:
                    # 内容不足，用列表信息
                    detail['content'] = detail.get('content', '') or item.get('title', '')
                    result.append(detail)
                    existing_urls.add(url)
                    print(f"[投资界] △ 内容较短，仍保存")
            else:
                print(f"[投资界] ✗ 详情解析失败")

        print(f"[投资界] 采集完成：{len(result)} 篇（跳过 {skipped} 重复）")
        return result

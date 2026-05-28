"""
教育资讯爬虫模块
- JiemoduiScraper: 芥末堆专用爬虫
- DuozhiScraper: 多知网专用爬虫
- CctvScraper: 央视网教育新闻爬虫
- EolScraper: 教育在线新闻爬虫
- EducationNewsScraper: 通用教育资讯爬虫（扩展入口）
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.scrapers.base import BaseScraper
from core.cookie_manager import CookieManager


# ============================================================
# 芥末堆爬虫
# ============================================================

class JiemoduiScraper(BaseScraper):
    """芥末堆专用爬虫 - 通过文章ID遍历采集"""

    BASE_URL = 'https://www.jiemodui.com'
    ARTICLE_URL_TEMPLATE = 'https://www.jiemodui.com/N/{article_id}.html'

    def __init__(self, cookie_manager: CookieManager = None, start_article_id: int = 139375):
        super().__init__(cookie_manager)
        self.source = 'jiemodui'
        self.source_name = '芥末堆'
        self.start_article_id = start_article_id

    def _get_latest_article_id(self) -> int:
        """获取最新文章的ID"""
        url = f'{self.BASE_URL}/N/index.html'
        response = self.request_with_retry(url, use_cookie_pool=False)
        if response:
            soup = BeautifulSoup(response.text, 'lxml')
            link = soup.select_one('a[href*="/N/"]')
            if link:
                href = link.get('href', '')
                match = re.search(r'/N/(\d+)\.html', href)
                if match:
                    return int(match.group(1))
        return 139375

    def parse_article_list(self, html: str) -> List[Dict]:
        """解析文章列表 - 芥末堆"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')

        for script in soup(['script', 'style']):
            script.decompose()

        selectors = [
            '.item-box', '.news-item', '.article-item',
            '.post-item', 'article', '[class*="item"]',
            '[class*="news"]', '[class*="article"]'
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
        """解析芥末堆文章详情（Nuxt.js页面）"""
        response = self.request_with_retry(url, use_cookie_pool=False)
        if not response:
            return None

        html_text = response.text
        title = ''
        author = ''
        date_str = ''
        content = ''

        # 尝试从 __NUXT__ 中提取
        nuxt_match = re.search(r'window\.__NUXT__\s*=\s*({.*?})\s*</script>', html_text, re.DOTALL)
        if nuxt_match:
            try:
                import json as json_module
                nuxt_data = json_module.loads(nuxt_match.group(1))

                def find_in_nuxt(obj, path=''):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if key in ['title', 'Title'] and isinstance(value, str):
                                return ('title', value)
                            elif key in ['author', 'Author', 'authorName'] and isinstance(value, str):
                                return ('author', value)
                            elif key in ['createdAt', 'publishTime', 'publish_date', 'created_at', 'time'] and isinstance(value, (str, int)):
                                return ('date', str(value))
                            elif key in ['content', 'body', 'html'] and isinstance(value, str):
                                return ('content', value)
                            result = find_in_nuxt(value)
                            if result:
                                return result
                    elif isinstance(obj, list) and len(obj) > 0:
                        for i, item in enumerate(obj[:3]):
                            result = find_in_nuxt(item)
                            if result:
                                return result
                    return None

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
        for script in soup(['script', 'style']):
            script.decompose()

        if not title:
            title_elem = soup.select_one('h1[data-v-15a4ed60]') or soup.select_one('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)

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

        if not content:
            content_elem = soup.select_one('article.content[data-v-15a4ed60]')
            if not content_elem:
                content_elem = soup.select_one('article.content')
            if not content_elem:
                content_elem = soup.select_one('#main-content, .article-content, article')

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
            if 'T' in date_str:
                iso_formats = ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                              '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M']
                for fmt in iso_formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                date_str = date_str.split('T')[0]
            formats = [
                '%m/%d/%Y, %I:%M:%S %p', '%m/%d/%Y, %I:%M %p', '%m/%d/%Y',
                '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d',
                '%Y年%m月%d日 %H:%M:%S', '%Y年%m月%d日 %H:%M', '%Y年%m月%d日'
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
        """从起始ID开始，依次+1采集所有文章"""
        if existing_urls is None:
            existing_urls = set()

        articles = []
        checked_count = 0
        consecutive_empty = 0
        consecutive_empty_limit = 10

        print(f"[芥末堆] 从ID {self.start_article_id} 开始采集，依次+1遍历所有文章...")

        article_id = self.start_article_id

        while consecutive_empty < consecutive_empty_limit:
            url = self.ARTICLE_URL_TEMPLATE.format(article_id=str(article_id))

            if url in existing_urls:
                consecutive_empty = 0
                article_id += 1
                checked_count += 1
                continue

            print(f"[芥末堆] 检查文章 ID: {article_id} ...")

            try:
                article_detail = self.parse_article_detail(url)

                if article_detail and article_detail.get('title'):
                    content = article_detail.get('content', '')
                    if content and len(content) > 100:
                        articles.append(article_detail)
                        existing_urls.add(url)
                        consecutive_empty = 0
                        publish_date = article_detail.get('publish_date')
                        date_str = publish_date.strftime('%Y/%m/%d') if publish_date else '未知'
                        print(f"[芥末堆] ✓ 采集成功: {article_detail.get('title')[:50]}... ({date_str})")
                    else:
                        print(f"[芥末堆] 文章正文内容不足或为空，跳过")
                        consecutive_empty += 1
                    time.sleep(random.uniform(1, 2))
                else:
                    print(f"[芥末堆] 文章不存在或解析失败 (ID: {article_id})")
                    consecutive_empty += 1
                    time.sleep(random.uniform(0.5, 1))
            except Exception as e:
                print(f"[芥末堆] 采集文章 {article_id} 出错: {e}")
                consecutive_empty += 1
                time.sleep(random.uniform(1, 2))

            article_id += 1
            checked_count += 1

            if checked_count % 100 == 0:
                print(f"[芥末堆] 已检查 {checked_count} 篇，已采集 {len(articles)} 篇，当前ID: {article_id}")

        print(f"[芥末堆] 采集完成，共采集 {len(articles)} 篇文章，检查了 {checked_count} 篇")
        return articles

    def crawl_education_news(self) -> List[Dict]:
        """爬取芥末堆所有文章"""
        return self.crawl_articles_in_range()


# ============================================================
# 多知网爬虫
# ============================================================

class DuozhiScraper(BaseScraper):
    """多知网专用爬虫 - 通过HTML解析列表页采集"""

    BASE_URL = 'http://www.duozhi.com'
    LIST_URL = 'http://www.duozhi.com/industry/insight/'
    SOURCE_NAME = 'duozhi'

    def __init__(self, cookie_manager: CookieManager = None, max_articles: int = 10):
        super().__init__(cookie_manager)
        self.source = self.SOURCE_NAME
        self.source_name = '多知网'
        self.max_articles = max_articles

    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析多知网文章详情"""
        response = self.request_with_retry(url, use_cookie_pool=False)
        if not response:
            return None

        # 尝试多种编码
        html_text = ''
        for encoding in ['gb18030', 'gbk', 'gb2312', 'utf-8', 'big5']:
            try:
                html_text = response.content.decode(encoding, errors='strict')
                if '的' in html_text or 'html' in html_text.lower():
                    break
            except Exception:
                continue

        if not html_text:
            html_text = response.content.decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html_text, 'lxml')
        for script in soup(['script', 'style']):
            script.decompose()

        # 提取标题
        title_elem = soup.select_one('body > div:nth-child(4) > div > div.c2 > div.subject > h1') or soup.select_one('h1')
        title = title_elem.get_text(strip=True) if title_elem else ''

        # 提取时间和作者
        meta_elem = soup.select_one('body > div:nth-child(4) > div > div.c2 > div.subject > div.subject-meta')
        if not meta_elem:
            meta_elem = soup.select_one('[class*="subject-meta"]')

        date_str = ''
        author = ''
        if meta_elem:
            meta_text = meta_elem.get_text(strip=True)
            time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})发布', meta_text)
            if time_match:
                date_str = time_match.group(1)
            author_match = re.search(r'作者：(\S+)', meta_text)
            if author_match:
                author = author_match.group(1)

        # 提取正文
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
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def crawl_articles_in_range(self, existing_urls: set = None, max_articles: int = None) -> List[Dict]:
        """使用HTML解析爬取多知网文章"""
        if existing_urls is None:
            existing_urls = set()
        if max_articles is None:
            max_articles = self.max_articles

        articles = []
        skipped_duplicates = 0

        print(f"[多知网] 开始采集，最多 {max_articles} 篇")

        page = 1
        max_pages = 20

        while page <= max_pages and len(articles) < max_articles:
            list_url = self.LIST_URL if page == 1 else f"{self.LIST_URL}index_{page}.shtml"
            print(f"[多知网] 获取列表页第 {page} 页: {list_url}")

            try:
                response = self.request_with_retry(list_url, use_cookie_pool=False)
                if not response:
                    print(f"[多知网] 第 {page} 页请求失败，停止")
                    break

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

                    if url in existing_urls:
                        skipped_duplicates += 1
                        print(f"[多知网] 跳过重复: {article_data.get('title', '')[:30]}...")
                        continue

                    print(f"[多知网] 详情页: {article_data.get('title', '')[:40]}...")
                    article_detail = self.parse_article_detail(url)

                    if article_detail and article_detail.get('title'):
                        content = article_detail.get('content', '')
                        if content and len(content) > 50:
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

                if len(page_articles) < 10:
                    print(f"[多知网] 文章数量少于10篇，可能已到尾页")
                    break

                page += 1
                time.sleep(random.uniform(1, 2))

            except Exception as e:
                print(f"[多知网] 第 {page} 页出错: {e}")
                break

        print(f"\n[多知网] 采集完成，共采集 {len(articles)} 篇文章（跳过 {skipped_duplicates} 篇重复）")
        return articles

    def _parse_article_list(self, html: str) -> List[Dict]:
        """解析多知网文章列表（.post-main 结构）"""
        articles = []
        soup = BeautifulSoup(html, 'lxml')

        for script in soup(['script', 'style']):
            script.decompose()

        post_mains = soup.select('.post-main')

        for post in post_mains:
            try:
                title_elem = post.select_one('.post-title')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')

                if not title or not url:
                    continue

                if not url.startswith('http'):
                    url = self.BASE_URL + url

                desc_elem = post.select_one('.post-desc')
                summary = desc_elem.get_text(strip=True) if desc_elem else ''

                date_str = ''
                author = ''
                attr_elems = post.select('.post-attr')
                for attr in attr_elems:
                    text = attr.get_text(strip=True)
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*\|', text)
                    if date_match:
                        date_str = date_match.group(1)
                    if 'by' in text.lower():
                        author_match = re.search(r'by\s*(\S+)', text)
                        if author_match:
                            author = author_match.group(1)

                tag_elems = post.select('.post-tag .link-tag')
                tag = tag_elems[0].get_text(strip=True) if tag_elems else ''

                publish_date = None
                if date_str:
                    try:
                        publish_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        pass

                articles.append({
                    'title': title, 'url': url,
                    'summary': summary, 'author': author,
                    'tag': tag, 'publish_date': publish_date,
                    'publish_date_str': date_str,
                    'source': self.source, 'source_name': self.source_name
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


# ============================================================
# 央视网教育新闻爬虫
# ============================================================

class CctvScraper(BaseScraper):
    """央视网教育新闻爬虫 - 使用JSONP API"""

    BASE_URL = 'https://news.cctv.com'
    LIST_URL = 'https://news.cctv.com/edu/'
    SOURCE_NAME = 'cctv'
    SOURCE_DISPLAY_NAME = '央视网'
    DEFAULT_DAYS = 30

    def __init__(self, cookie_manager: CookieManager = None, days: int = None, max_articles: int = 10):
        super().__init__(cookie_manager)
        self.source = self.SOURCE_NAME
        self.source_name = self.SOURCE_DISPLAY_NAME
        self.days = days or self.DEFAULT_DAYS
        self.max_articles = max_articles

    def parse_article_list(self, html: str, date_str: str = None) -> List[Dict]:
        """解析央视网教育新闻列表（JSONP格式）"""
        import json as json_module
        articles = []
        seen_urls = set()

        try:
            jsonp_match = re.match(r'(\w+)\((\{.*\})\)', html.strip(), re.DOTALL)
            if jsonp_match:
                json_str = jsonp_match.group(2)
                data = json_module.loads(json_str)
                article_list = data.get('data', {}).get('list', [])

                if article_list:
                    print(f"[央视网] API返回 {len(article_list)} 篇文章")

                    for item in article_list:
                        url = item.get('url', '')
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        clean_url = re.split(r'\?', url)[0]
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
        soup = BeautifulSoup(html, 'html.parser')

        url_pattern = r'href="(https?://news\.cctv\.com/20\d{2}/\d{2}/\d{2}/ARTI[^"]+\.shtml)'
        all_urls = re.findall(url_pattern, html)
        print(f"[央视网] HTML中找到 {len(all_urls)} 个文章URL")

        for href in all_urls:
            try:
                clean_url = re.split(r'\?', href)[0]
                if not clean_url or clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)

                date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', clean_url)
                article_date_str = None
                if date_match:
                    article_date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

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
                    'title': title, 'url': clean_url,
                    'summary': '', 'publish_date_str': article_date_str,
                    'tags': '', 'source': self.source,
                    'source_name': self.source_name
                })
            except Exception:
                continue

        print(f"[央视网] 解析到 {len(articles)} 篇文章")
        return articles

    def _cctv_request(self, url: str) -> Optional[str]:
        """央视网专用请求方法"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                encoding = response.encoding
                if encoding not in ['utf-8', 'UTF-8', 'utf8']:
                    encoding = 'utf-8'
                return response.content.decode(encoding, errors='ignore')
        except Exception as e:
            print(f"[央视网] 请求失败: {e}")
        return None

    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析央视网文章详情"""
        html_text = self._cctv_request(url)
        if not html_text:
            return None

        soup = BeautifulSoup(html_text, 'lxml')
        for script in soup(['script', 'style']):
            script.decompose()

        # 提取标题
        title_elem = soup.select_one('#title_area h1, .title_area h1, h1')
        title = title_elem.get_text(strip=True) if title_elem else ''

        # 提取来源和日期
        author = ''
        date_str = ''
        source_name = ''

        info_elem = soup.select_one('.info, .info1')
        if info_elem:
            info_text = info_elem.get_text(strip=True)
            source_match = re.search(r'来源：([^|<]+)', info_text)
            if source_match:
                source_name = source_match.group(1).strip()
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})', info_text)
            if date_match:
                year, month, day, hour, minute = date_match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}:00"
            else:
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', info_text)
                if date_match:
                    date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

        # 提取正文
        content = ''
        for selector in ['#content_area', '.content_area', '#text_area', '.text_area']:
            content_elem = soup.select_one(selector)
            if content_elem:
                paragraphs = []
                for p in content_elem.find_all(['p', 'h2', 'h3', 'h4']):
                    text = p.get_text(strip=True)
                    if text:
                        paragraphs.append(text)
                content = '\n\n'.join(paragraphs)
                if content:
                    break

        # 从脚本变量中提取
        if not content:
            content_match = re.search(r"var\s+content(date)?\s*=\s*['\"](.+?)['\"]", html_text, re.DOTALL)
            if content_match:
                from html import unescape
                content = unescape(content_match.group(2))
                content_soup = BeautifulSoup(content, 'lxml')
                content = content_soup.get_text(separator='\n', strip=True)

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
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y年%m月%d日']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def crawl_articles_in_range(self, existing_urls: set = None, max_articles: int = None) -> List[Dict]:
        """使用JSONP API爬取央视网教育新闻"""
        if existing_urls is None:
            existing_urls = set()
        if max_articles is None:
            max_articles = self.max_articles

        cutoff_date = datetime.now() - timedelta(days=self.days)
        articles = []
        skipped_duplicates = 0

        print(f"[央视网] 开始采集，最多 {max_articles} 篇")

        page = 1
        total_pages = 10

        while page <= total_pages and len(articles) < max_articles:
            api_url = f"https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/edu_{page}.jsonp"
            print(f"[央视网] 获取API第 {page} 页: {api_url}")

            try:
                api_response = self._cctv_request(api_url)

                if not api_response or len(api_response) < 100:
                    print(f"[央视网] API第 {page} 页无数据，停止")
                    break

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

                    if url in existing_urls:
                        skipped_duplicates += 1
                        print(f"[央视网] 跳过重复: {article_data.get('title', '')[:30]}...")
                        continue

                    pub_date_str = article_data.get('publish_date_str')
                    if pub_date_str:
                        try:
                            article_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
                            if article_date < cutoff_date:
                                print(f"[央视网] 文章日期 {pub_date_str} 早于截止日期，停止")
                                page = total_pages + 1
                                break
                        except:
                            pass

                    print(f"[央视网] 详情页: {article_data.get('title', '')[:40]}...")
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

                total_match = re.search(r'"total"\s*:\s*"?(\d+)"?', api_response)
                if total_match:
                    total = int(total_match.group(1))
                    total_pages = min((total // 10) + 2, 100)

                page += 1
                time.sleep(random.uniform(1, 2))

            except Exception as e:
                print(f"[央视网] API第 {page} 页出错: {e}")
                break

        print(f"\n[央视网] 采集完成，共采集 {len(articles)} 篇文章（跳过 {skipped_duplicates} 篇重复）")
        return articles

    def crawl(self, url: str = None) -> List[Dict]:
        """执行爬取"""
        return self.crawl_articles_in_range()


# ============================================================
# 教育在线爬虫
# ============================================================

class EolScraper(BaseScraper):
    """教育在线教育新闻爬虫（eol.cn）- 仅从首页抓取"""

    BASE_URL = 'https://news.eol.cn'
    LIST_URL = 'https://news.eol.cn/'
    SOURCE_NAME = 'eol'
    SOURCE_DISPLAY_NAME = '教育在线'
    DEFAULT_DAYS = 30

    def __init__(self, cookie_manager: CookieManager = None, days: int = None, max_articles: int = 15):
        super().__init__(cookie_manager)
        self.source = self.SOURCE_NAME
        self.source_name = self.SOURCE_DISPLAY_NAME
        self.days = days or self.DEFAULT_DAYS
        self.max_articles = max_articles

    def _eol_request(self, url: str) -> Optional[str]:
        """教育在线专用请求方法"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                if response.apparent_encoding:
                    response.encoding = response.apparent_encoding
                return response.text
        except Exception as e:
            print(f"[教育在线] 请求失败: {e}")
        return None

    def _resolve_url(self, href: str, base_url: str) -> str:
        """解析相对URL为绝对URL"""
        if not href:
            return ''
        if href.startswith('./'):
            href = href[1:]
        if href.startswith('http'):
            return href.split('?')[0]
        if href.startswith('//'):
            return 'https:' + href.split('?')[0]
        return urljoin(base_url, href).split('?')[0]

    def parse_article_list(self, html: str) -> List[Dict]:
        """解析教育在线首页多个内容区域的文章列表"""
        articles = []
        seen_urls = set()

        soup = BeautifulSoup(html, 'lxml')

        # ── 区域1: 教育头条 (.toutiao 卡片) ──
        toutiao_cards = soup.select('.toutiao')
        print(f"[教育在线] 找到 {len(toutiao_cards)} 条头条")

        for card in toutiao_cards:
            try:
                title_elem = card.select_one('.toutiao-tt a')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                if not href or not title:
                    continue

                url = self._resolve_url(href, self.LIST_URL)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                time_elem = card.select_one('.toutiao-ly .time')
                time_str = time_elem.get_text(strip=True) if time_elem else ''
                source_elem = card.select_one('.toutiao-ly .laiyuan')
                source = source_elem.get_text(strip=True) if source_elem else ''

                articles.append({
                    'title': title, 'url': url,
                    'publish_date_str': self._parse_date_str(time_str),
                    'source_name': source or self.source_name,
                    'source': self.source,
                })
            except Exception:
                continue

        # ── 区域2: 教育头条区底部 .lie 列表 ──
        lie_cards = soup.select('.toutiao .lie')
        print(f"[教育在线] 找到 {len(lie_cards)} 条次级头条")

        for card in lie_cards:
            try:
                title_elem = card.select_one('.linktt a')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                if not href or not title:
                    continue

                url = self._resolve_url(href, self.LIST_URL)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                time_elem = card.select_one('.lie-ly .time')
                time_str = time_elem.get_text(strip=True) if time_elem else ''
                source_elem = card.select_one('.lie-ly .laiyuan')
                source = source_elem.get_text(strip=True) if source_elem else ''

                articles.append({
                    'title': title, 'url': url,
                    'publish_date_str': self._parse_date_str(time_str),
                    'source_name': source or self.source_name,
                    'source': self.source,
                })
            except Exception:
                continue

        # ── 区域3: 最新动态 (.newslist 卡片) ──
        newslist_cards = soup.select('.newslist')
        print(f"[教育在线] 找到 {len(newslist_cards)} 条最新动态")

        for card in newslist_cards:
            try:
                title_elem = card.select_one('.biaoti .title a')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                if not href or not title:
                    continue

                url = self._resolve_url(href, self.LIST_URL)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                time_elem = card.select_one('.xiangguan .time')
                time_str = time_elem.get_text(strip=True) if time_elem else ''
                source_elem = card.select_one('.xiangguan .laiyuan')
                source = source_elem.get_text(strip=True) if source_elem else ''

                articles.append({
                    'title': title, 'url': url,
                    'publish_date_str': self._parse_date_str(time_str),
                    'source_name': source or self.source_name,
                    'source': self.source,
                })
            except Exception:
                continue

        print(f"[教育在线] 列表解析到 {len(articles)} 篇文章")
        return articles

    def _parse_date_str(self, date_text: str) -> Optional[str]:
        """解析日期文本，返回 YYYY-MM-DD 格式"""
        if not date_text:
            return None
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_text)
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return date_text.strip()

    def parse_article_detail(self, url: str) -> Optional[Dict]:
        """解析教育在线文章详情页"""
        html_text = self._eol_request(url)
        if not html_text:
            return None

        soup = BeautifulSoup(html_text, 'lxml')
        for tag in soup(['script', 'style']):
            tag.decompose()

        # 标题
        title = ''
        for selector in ['h1', '.title h1', '.biaoti h1', '.article-title',
                         '.neirong .title', '[class*="title"] h1', '.trs_editor_view h1']:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 5:
                    break

        if not title or len(title) < 5:
            page_title = soup.select_one('title')
            if page_title:
                title_text = page_title.get_text(strip=True)
                for sep in [' - ', '_', ' | ', '—']:
                    if sep in title_text:
                        title = title_text.split(sep)[0].strip()
                        break
                if not title:
                    title = title_text

        # 来源和日期
        author = ''
        date_str = ''
        source_name = ''

        for meta_name in ['author', 'source', 'weibo:article:create_at']:
            meta = soup.select_one(f'meta[name="{meta_name}"], meta[property="{meta_name}"]')
            if meta:
                content = meta.get('content', '')
                if meta_name == 'author':
                    author = content
                elif 'create_at' in meta_name:
                    date_str = content

        info_selectors = ['.xiangguan', '.info', '.article-info', '.source-time',
                          '.laiyuan', '[class*="info"]', '[class*="source"]',
                          '.article-source', '.time-source']
        info_text = ''
        for sel in info_selectors:
            info_elem = soup.select_one(sel)
            if info_elem:
                info_text = info_elem.get_text(strip=True)
                break

        if info_text:
            source_match = re.search(r'来源[：:]\s*([^\s|]+)', info_text)
            if source_match:
                source_name = source_match.group(1).strip()
            time_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(\d{1,2})[:：](\d{1,2})', info_text)
            if time_match:
                y, m, d, h, mi = time_match.groups()
                date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)} {h.zfill(2)}:{mi.zfill(2)}:00"
            else:
                time_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', info_text)
                if time_match:
                    y, m, d = time_match.groups()
                    date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        if not date_str:
            url_date = re.search(r'/(\d{4})(\d{2})/', url)
            if url_date:
                date_str = f"{url_date.group(1)}-{url_date.group(2)}"

        # 正文
        content = ''
        content_selectors = ['.trs_editor_view', '#content', '.content', '.article-content',
                             '.neirong', '#text', '.text', '.article-body',
                             '[class*="content"]', '[class*="article"]']

        for sel in content_selectors:
            content_elem = soup.select_one(sel)
            if content_elem:
                for bad in content_elem.select('.sharebox, .fenxiang, .social-share, script, style'):
                    bad.decompose()

                paragraphs = []
                for p in content_elem.find_all(['p', 'h2', 'h3', 'h4', 'div']):
                    text = p.get_text(strip=True)
                    if text and len(text) > 5:
                        skip_patterns = ['扫码', '扫一扫', '分享到', '微信', '版权声明',
                                       '转载', '原文链接', '阅读原文', '点击上方']
                        if not any(kw in text for kw in skip_patterns):
                            paragraphs.append(text)

                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                    break

        if not content:
            var_match = re.search(r"var\s+content\s*=\s*['\"](.+?)['\"]", html_text, re.DOTALL)
            if var_match:
                from html import unescape
                content = unescape(var_match.group(1))
                content_soup = BeautifulSoup(content, 'lxml')
                content = content_soup.get_text(separator='\n', strip=True)

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
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                       '%Y年%m月%d日', '%Y年%m月%d日 %H:%M']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def crawl_articles_in_range(self, existing_urls: set = None, max_articles: int = None) -> List[Dict]:
        """从首页采集教育在线新闻"""
        if existing_urls is None:
            existing_urls = set()
        if max_articles is None:
            max_articles = self.max_articles

        cutoff_date = datetime.now() - timedelta(days=self.days)
        articles = []
        skipped_duplicates = 0

        print(f"[教育在线] 开始从首页采集，最多 {max_articles} 篇，最近 {self.days} 天")
        print(f"[教育在线] 列表页: {self.LIST_URL}")

        try:
            html_text = self._eol_request(self.LIST_URL)
            if not html_text:
                print("[教育在线] 首页请求失败")
                return articles

            list_articles = self.parse_article_list(html_text)

            for article_data in list_articles:
                if len(articles) >= max_articles:
                    break

                url = article_data.get('url', '')
                if not url:
                    continue

                if url in existing_urls:
                    skipped_duplicates += 1
                    continue

                pub_date_str = article_data.get('publish_date_str')
                if pub_date_str:
                    try:
                        article_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
                        if article_date < cutoff_date:
                            print(f"[教育在线] 文章日期 {pub_date_str} 早于截止日期，跳过")
                            continue
                    except Exception:
                        pass

                print(f"[教育在线] 详情页: {article_data.get('title', '')[:40]}...")
                article_detail = self.parse_article_detail(url)

                if article_detail and article_detail.get('title'):
                    content = article_detail.get('content', '')
                    if content and len(content) > 50:
                        articles.append(article_detail)
                        existing_urls.add(url)
                        print(f"[教育在线] ✓ 采集成功: {article_detail.get('title')[:40]}...")
                    else:
                        print(f"[教育在线] 正文内容不足，仍保存基本信息")
                        articles.append(article_data)
                        existing_urls.add(url)
                else:
                    print(f"[教育在线] 详情解析失败，跳过")

                time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"[教育在线] 首页解析出错: {e}")

        print(f"\n[教育在线] 采集完成，共采集 {len(articles)} 篇文章（跳过 {skipped_duplicates} 篇重复）")
        return articles

    def crawl(self, url: str = None) -> List[Dict]:
        """执行爬取"""
        return self.crawl_articles_in_range()


# ============================================================
# 通用教育资讯爬虫（扩展入口）
# ============================================================

class EducationNewsScraper(BaseScraper):
    """教育资讯爬虫（支持多数据源扩展）"""

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

        for script in soup(['script', 'style']):
            script.decompose()

        base_url = self.source_urls.get(self.source, 'https://www.jiemodui.com')

        if self.source == 'jiemodui':
            selectors = ['.item-box', '.news-item', '.article-item', '.post-item',
                        '.entry-item', 'article', '[class*="item"]', '[class*="news"]']
        else:
            selectors = ['.article-item', '.post-item', '.news-item', '.entry-item',
                        'article', '[class*="article"]', '[class*="post"]']

        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 1:
                for item in items:
                    try:
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

                        href = ''
                        if link_elem:
                            href = link_elem.get('href', '')
                            if href and not href.startswith('http'):
                                href = base_url.rstrip('/') + '/' + href.lstrip('/')

                        summary_elem = item.select_one('.summary, .desc, .excerpt, .intro, [class*="summary"], [class*="desc"]')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ''

                        date_elem = item.select_one('.date, .time, .pub-time, [class*="date"], [class*="time"]')
                        date_str = date_elem.get_text(strip=True) if date_elem else None

                        articles.append({
                            'title': title, 'url': href, 'summary': summary,
                            'publish_date': self._parse_date(date_str),
                            'source': self.source,
                            'source_name': '芥末堆' if self.source == 'jiemodui' else '多知网'
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

        title_elem = soup.select_one('h1, .article-title, .post-title, [class*="title"]')
        title = title_elem.get_text(strip=True) if title_elem else ''

        content_elem = soup.select_one('article, .article-content, .post-content, .entry-content, main, [role="main"], #main-content')

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
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%Y年%m月%d日', '%Y年%m月%d日 %H:%M']:
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

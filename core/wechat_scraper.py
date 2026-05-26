# -*- coding: utf-8 -*-
"""
微信公众号文章爬虫 - 纯标准库版本
使用 urllib 和 re 解析，无需第三方依赖
"""
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from html import unescape


class WechatArticleSpider:
    """微信公众号文章爬虫（纯标准库版本）"""
    
    def __init__(self, cookie_manager=None):
        self.cookie_manager = cookie_manager
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
    
    def _get_cookies(self) -> Dict[str, str]:
        """获取cookies"""
        if self.cookie_manager:
            result = self.cookie_manager.get_cookies()
            if result:
                # get_cookies() 返回 {'cookies': {...}, 'user_agent': ...} 或直接返回 {...}
                if isinstance(result, dict):
                    if 'cookies' in result:
                        return result['cookies']
                    return result
            return {}
        return {}
    
    def _make_request(self, url: str, retry_count: int = 3) -> Optional[str]:
        """发送HTTP请求"""
        for attempt in range(retry_count):
            try:
                cookies = self._get_cookies()
                
                # 构建Cookie头
                cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
                headers = self.headers.copy()
                if cookie_str:
                    headers['Cookie'] = cookie_str
                
                # 构建请求
                req = urllib.request.Request(url)
                for key, value in headers.items():
                    req.add_header(key, value)
                
                # 发送请求
                with urllib.request.urlopen(req, timeout=15) as response:
                    charset = 'utf-8'
                    content_type = response.headers.get('Content-Type', '')
                    if 'charset=' in content_type:
                        charset = content_type.split('charset=')[-1].split(';')[0].strip()
                    
                    html = response.read().decode(charset, errors='replace')
                    return html
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                else:
                    print(f"请求失败: {url}, 错误: {e}")
        
        return None
    
    def parse_article(self, url: str) -> Dict:
        """
        解析微信公众号文章
        
        Args:
            url: 文章URL
            
        Returns:
            包含文章信息的字典
        """
        result = {
            'success': False,
            'title': '',
            'author': '',
            'content': '',
            'summary': '',
            'publish_time': None,
            'images': [],
            'url': url
        }
        
        try:
            html = self._make_request(url)
            if not html:
                return result
            
            # 解析标题 - 标题在 <span class="js_title_inner"> 中
            title_match = re.search(r'<span[^>]*class="js_title_inner"[^>]*>(.*?)</span>', html, re.DOTALL)
            if not title_match:
                title_match = re.search(r'<h1[^>]*class="rich_media_title"[^>]*>\s*<[^>]+>(.*?)</[^>]+>', html, re.DOTALL)
            if not title_match:
                title_match = re.search(r'id="activity-name"[^>]*>(.*?)</[^>]+>', html, re.DOTALL)
            if not title_match:
                # 尝试从og:title获取
                title_match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html)
            if not title_match:
                title_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']', html)
            if title_match:
                result['title'] = self._clean_html(title_match.group(1))
            
            # 解析作者 - 尝试多种方式
            author_match = re.search(r'<span[^>]*class="rich_media_meta rich_media_meta_text"[^>]*>(.*?)</span>', html, re.DOTALL)
            if not author_match:
                author_match = re.search(r'<span[^>]*id="js_name"[^>]*>(.*?)</span>', html, re.DOTALL)
            if not author_match:
                author_match = re.search(r'class="account_nickname"[^>]*>(.*?)</[^>]+>', html, re.DOTALL)
            if not author_match:
                author_match = re.search(r'class="rich_media_meta_nickname"[^>]*>(.*?)</[^>]+>', html, re.DOTALL)
            if author_match:
                result['author'] = self._clean_html(author_match.group(1))
            
            # 解析发布时间
            time_match = re.search(r'publish_time\s*[:=]\s*["\']([^"\']+)["\']', html)
            if not time_match:
                time_match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
            if time_match:
                try:
                    result['publish_time'] = datetime.strptime(time_match.group(1)[:10], '%Y-%m-%d')
                except:
                    result['publish_time'] = datetime.now()
            else:
                result['publish_time'] = datetime.now()
            
            # 解析正文内容
            content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
            if content_match:
                content_html = content_match.group(1)
                result['content'] = self._extract_text_content(content_html)
                result['images'] = self._extract_images(content_html)
            
            # 生成摘要
            if result['content']:
                result['summary'] = result['content'][:200] + '...' if len(result['content']) > 200 else result['content']
            
            result['success'] = bool(result['title'] and result['content'])
            
        except Exception as e:
            print(f"解析文章失败: {e}")
        
        return result
    
    def _clean_html(self, html: str) -> str:
        """清理HTML标签"""
        text = re.sub(r'<[^>]+>', '', html)
        text = unescape(text)
        return text.strip()
    
    def _extract_text_content(self, html: str) -> str:
        """提取纯文本内容"""
        # 移除所有HTML标签
        text = re.sub(r'<[^>]+>', '\n', html)
        # 清理多余空白
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r' +', ' ', text)
        text = unescape(text)
        return text.strip()
    
    def _extract_images(self, html: str) -> List[str]:
        """提取图片URL"""
        images = []
        # 匹配 data-src 和 src 属性中的图片
        img_patterns = [
            r'data-src=["\']([^"\']+)["\']',
            r'src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']'
        ]
        
        for pattern in img_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if match not in images and 'qpic.cn' in match or 'cdn.cn' in match or match.startswith('http'):
                    images.append(match)
        
        return list(set(images))[:10]  # 限制最多10张图片
    
    def fetch_account_articles(self, biz: str, cookie: str = None, count: int = 20) -> List[Dict]:
        """
        获取公众号文章列表（通过 __biz 参数）

        Args:
            biz: 公众号biz标识（完整格式如：MzA5ODEzMjIyMA==）
            cookie: 访问cookie字符串（可选，但建议提供）
            count: 每次请求获取的文章数量，默认20

        Returns:
            文章列表
        """
        # 优先使用 profile_ext 接口获取文章列表
        return self.fetch_articles_by_biz(biz, cookie, count)
    
    def fetch_articles_by_sogou(self, account_name: str, count: int = 20) -> List[Dict]:
        """
        使用搜狗搜索获取公众号文章列表（推荐方案）
        
        Args:
            account_name: 公众号名称（如：AI科技评论）
            count: 最大获取文章数，默认20
            
        Returns:
            文章列表
        """
        articles = []
        
        try:
            print(f"[WechatArticleSpider] 使用搜狗搜索获取公众号: {account_name}")
            
            # 构造搜狗搜索URL
            search_url = f"https://weixin.sogou.com/weixin?type=1&s_from=input&query={urllib.parse.quote(account_name)}&ie=utf8&_sug_=n&_sug_type_="
            
            headers = self.headers.copy()
            headers['Referer'] = 'https://weixin.sogou.com/'
            
            req = urllib.request.Request(search_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='replace')
                
                print(f"[WechatArticleSpider] 搜狗搜索响应长度: {len(html)} 字符")
                
                # 解析搜索结果，找到第一个匹配的公众号
                # 搜狗搜索返回的HTML格式
                account_pattern = r'<div class="img-box">(.*?)</div>\s*<div class="account">(.*?)</div>'
                matches = re.findall(account_pattern, html, re.DOTALL)
                
                if not matches:
                    # 尝试另一种解析方式
                    account_pattern2 = r'<p class="tit"[^>]*>.*?<strong>(.*?)</strong>.*?</p>.*?<a[^>]*href="([^"]*)"[^>]*class="account"[^>]*>(.*?)</a>'
                    matches = re.findall(account_pattern2, html, re.DOTALL)
                
                # 提取文章列表（通过公众号主页）
                # 首先找到公众号的URL
                account_url_match = re.search(r'href="(https?://[^"]*weixin[^"]*account[^"]*)"', html)
                if not account_url_match:
                    account_url_match = re.search(r'href="(https?://[^"]*mp\.weixin[^"]*)"', html)
                
                if account_url_match:
                    account_url = account_url_match.group(1)
                    print(f"[WechatArticleSpider] 找到公众号URL: {account_url}")
                    
                    # 访问公众号页面获取文章列表
                    articles = self._fetch_articles_from_account_page(account_url, count)
                else:
                    print(f"[WechatArticleSpider] 未找到公众号链接，尝试直接搜索文章...")
                    # 如果找不到公众号，直接搜索文章
                    articles = self._search_articles_by_sogou(account_name, count)
                    
        except Exception as e:
            import traceback
            print(f"[WechatArticleSpider] 搜狗搜索失败: {e}")
            traceback.print_exc()
        
        return articles
    
    def _fetch_articles_from_account_page(self, account_url: str, count: int = 20) -> List[Dict]:
        """从公众号页面获取文章列表"""
        articles = []
        
        try:
            print(f"[WechatArticleSpider] 访问公众号页面: {account_url}")
            
            headers = self.headers.copy()
            headers['Referer'] = 'https://weixin.sogou.com/'
            
            req = urllib.request.Request(account_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='replace')
                
                # 解析文章列表
                # 微信文章链接格式：https://mp.weixin.qq.com/s/xxxxx
                article_pattern = r'<div[^>]*class="[^"]*weui-article[^"]*"[^>]*>.*?<a[^>]*href="(https://mp\.weixin\.qq\.com/s/[^"]+)"[^>]*>(.*?)</a>.*?<span[^>]*class="[^"]*date[^"]*"[^>]*>(.*?)</span>'
                
                matches = re.findall(article_pattern, html, re.DOTALL)
                
                for match in matches[:count]:
                    url, title, date = match
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    articles.append({
                        'title': title,
                        'url': url,
                        'date': date.strip()
                    })
                
                if not articles:
                    # 尝试另一种解析模式
                    article_pattern2 = r'<a[^>]*href="(https://mp\.weixin\.qq\.com/s/[^"]+)"[^>]*>\s*<strong[^>]*>(.*?)</strong>'
                    matches2 = re.findall(article_pattern2, html, re.DOTALL)
                    
                    for url, title in matches2[:count]:
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        articles.append({
                            'title': title,
                            'url': url,
                            'date': None
                        })
                
                print(f"[WechatArticleSpider] 从公众号页面解析到 {len(articles)} 篇文章")
                
        except Exception as e:
            print(f"[WechatArticleSpider] 获取公众号页面失败: {e}")
        
        return articles
    
    def _search_articles_by_sogou(self, account_name: str, count: int = 20) -> List[Dict]:
        """使用搜狗搜索文章"""
        articles = []
        
        try:
            print(f"[WechatArticleSpider] 搜索公众号文章: {account_name}")
            
            # 搜索文章
            search_url = f"https://weixin.sogou.com/weixin?type=2&s_from=input&query={urllib.parse.quote(account_name)}&ie=utf8&_sug_=n&_sug_type_="
            
            headers = self.headers.copy()
            headers['Referer'] = 'https://weixin.sogou.com/'
            
            req = urllib.request.Request(search_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='replace')
                
                # 解析搜索结果
                # 搜狗文章格式
                article_pattern = r'<div[^>]*class="[^"]*txt-box[^"]*"[^>]*>.*?<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>.*?<span[^>]*class="[^"]*s2[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>'
                
                matches = re.findall(article_pattern, html, re.DOTALL)
                
                for url, title, source in matches[:count]:
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    articles.append({
                        'title': title,
                        'url': url,
                        'source': source.strip()
                    })
                
                if not articles:
                    # 尝试更通用的解析
                    article_pattern2 = r'<a[^>]*href="(https://mp\.weixin\.qq\.com/s/[^"]+)"[^>]*class="[^"]*tit[^"]*"[^>]*>(.*?)</a>'
                    matches2 = re.findall(article_pattern2, html, re.DOTALL)
                    
                    for url, title in matches2[:count]:
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        articles.append({
                            'title': title,
                            'url': url,
                            'source': account_name
                        })
                
                print(f"[WechatArticleSpider] 搜狗搜索解析到 {len(articles)} 篇文章")
                
        except Exception as e:
            print(f"[WechatArticleSpider] 搜狗文章搜索失败: {e}")
        
        return articles


    def fetch_articles_by_biz(self, biz: str, cookie: str = None, count: int = 20) -> List[Dict]:
        """
        通过 __biz 参数获取公众号文章列表（推荐方案）

        Args:
            biz: 公众号biz标识（完整格式如：MzA5ODEzMjIyMA==）
            cookie: 访问cookie字符串（可选，但建议提供以获取更完整的数据）
            count: 最大获取文章数，默认20

        Returns:
            文章列表，每篇包含 title, url, digest, author, publish_time 等字段
        """
        articles = []

        try:
            print(f"[WechatArticleSpider] 通过biz获取公众号文章: {biz}")

            # 构造 profile_ext 接口URL
            url = f"https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={biz}&scene=124#wechat_redirect"

            headers = self.headers.copy()
            headers['Referer'] = 'https://mp.weixin.qq.com/'
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'

            # 如果提供了cookie，添加到请求头
            if cookie:
                headers['Cookie'] = cookie

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='replace')

                print(f"[WechatArticleSpider] profile_ext 响应长度: {len(html)} 字符")

                # 检查是否需要验证（登录跳转）
                if 'verify_qrcode' in html or '登录' in html[:2000]:
                    print(f"[WechatArticleSpider] 需要登录验证，请检查Cookie是否有效")
                    return []

                # 方法1：尝试从HTML中提取JSON数据
                # 微信会在script标签中嵌入JSON数据
                json_pattern = r'var appmsgList\s*=\s*(\{.*?\});'
                match = re.search(json_pattern, html, re.DOTALL)

                if match:
                    try:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        articles = self._parse_appmsg_list(data.get('app_msg_list', []))
                        print(f"[WechatArticleSpider] 从appmsgList解析到 {len(articles)} 篇文章")
                        return articles[:count]
                    except json.JSONDecodeError as e:
                        print(f"[WechatArticleSpider] JSON解析失败: {e}")

                # 方法2：尝试从HTML源码中提取文章数据（另一种格式）
                # 微信有时会将数据存储在 data-src 属性中
                article_urls = re.findall(r'content_url\s*:\s*["\']([^"\']+)["\']', html)
                article_titles = re.findall(r'"title"\s*:\s*"([^"]+)"', html)
                article_digests = re.findall(r'"digest"\s*:\s*"([^"]+)"', html)
                article_authors = re.findall(r'"author"\s*:\s*"([^"]+)"', html)
                article_times = re.findall(r'"cdate"\s*:\s*(\d+)', html)

                print(f"[WechatArticleSpider] 找到文章URL数量: {len(article_urls)}")

                for i, content_url in enumerate(article_urls[:count]):
                    # 修复URL中的转义字符
                    content_url = content_url.replace('&amp;', '&')

                    # 构建完整的文章URL
                    if not content_url.startswith('http'):
                        content_url = 'https://mp.weixin.qq.com' + content_url

                    article = {
                        'title': article_titles[i] if i < len(article_titles) else '',
                        'url': content_url,
                        'digest': article_digests[i] if i < len(article_digests) else '',
                        'author': article_authors[i] if i < len(article_authors) else '',
                    }

                    # 解析时间戳
                    if i < len(article_times):
                        try:
                            article['publish_time'] = datetime.fromtimestamp(int(article_times[i]))
                        except:
                            article['publish_time'] = None
                    else:
                        article['publish_time'] = None

                    articles.append(article)

                # 如果仍然没有找到，尝试解析 HTML 中的文章链接
                if not articles:
                    print(f"[WechatArticleSpider] 尝试解析HTML中的文章链接...")

                    # 微信文章的URL格式
                    link_pattern = r'https?://mp\.weixin\.qq\.com/s/[a-zA-Z0-9_-]+'
                    links = re.findall(link_pattern, html)
                    links = list(dict.fromkeys(links))  # 去重

                    for url in links[:count]:
                        articles.append({
                            'title': '',
                            'url': url,
                            'digest': '',
                            'author': '',
                            'publish_time': None
                        })

                print(f"[WechatArticleSpider] 最终解析到 {len(articles)} 篇文章")

        except Exception as e:
            import traceback
            print(f"[WechatArticleSpider] 通过biz获取文章失败: {e}")
            traceback.print_exc()

        return articles[:count]

    def fetch_articles_batch(self, biz_list: List[str], cookie: str = None, count_per_account: int = 10) -> Dict[str, List[Dict]]:
        """
        批量获取多个公众号的文章列表

        Args:
            biz_list: biz标识列表
            cookie: 访问cookie字符串
            count_per_account: 每个公众号获取的文章数量

        Returns:
            字典，键为biz，值为文章列表
        """
        results = {}
        total_accounts = len(biz_list)

        print(f"[WechatArticleSpider] 开始批量采集 {total_accounts} 个公众号...")

        for i, biz in enumerate(biz_list):
            print(f"[WechatArticleSpider] 采集进度: {i+1}/{total_accounts} - {biz}")
            try:
                articles = self.fetch_articles_by_biz(biz, cookie, count_per_account)
                results[biz] = articles
                print(f"[WechatArticleSpider] {biz} 获取到 {len(articles)} 篇文章")
            except Exception as e:
                print(f"[WechatArticleSpider] {biz} 采集失败: {e}")
                results[biz] = []

            # 避免请求过快
            if i < total_accounts - 1:
                time.sleep(2)

        print(f"[WechatArticleSpider] 批量采集完成，共 {total_accounts} 个公众号")
        return results

    def _parse_appmsg_list(self, appmsg_list: List) -> List[Dict]:
        """解析 appmsg_list 数据"""
        articles = []

        for item in appmsg_list:
            article = {
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'digest': item.get('digest', ''),
                'author': item.get('author', ''),
                'cover': item.get('cover', ''),
            }

            # 解析时间
            if 'ct' in item:
                try:
                    article['publish_time'] = datetime.fromtimestamp(int(item['ct']))
                except:
                    article['publish_time'] = None
            else:
                article['publish_time'] = None

            articles.append(article)

        return articles

# 独立测试
if __name__ == '__main__':
    spider = WechatArticleSpider()

    # 测试解析文章
    test_url = input("请输入微信公众号文章URL: ").strip()
    if test_url:
        result = spider.parse_article(test_url)
        print(f"\n标题: {result['title']}")
        print(f"作者: {result['author']}")
        print(f"发布时间: {result['publish_time']}")
        print(f"摘要: {result['summary'][:100]}...")
        print(f"图片数量: {len(result['images'])}")
        print(f"解析成功: {result['success']}")

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
    
    def fetch_account_articles(self, biz: str, cookie: str = None) -> List[Dict]:
        """
        获取公众号文章列表
        
        Args:
            biz: 公众号biz标识
            cookie: 访问cookie
            
        Returns:
            文章列表
        """
        articles = []
        
        try:
            # 构造请求URL
            url = f"https://mp.weixin.qq.com/cgi-bin/appmsg?action=list_ex&begin=0&count=5&fakeid={biz}&type=9&lang=zh_CN&f=json&ajax=1"
            
            cookies = {}
            if cookie:
                for item in cookie.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookies[key] = value
            
            headers = self.headers.copy()
            headers['Cookie'] = cookie or ''
            headers['Referer'] = 'https://mp.weixin.qq.com/'
            
            req = urllib.request.Request(url)
            for key, value in headers.items():
                req.add_header(key, value)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get('app_msg_list'):
                    for item in data['app_msg_list']:
                        articles.append({
                            'title': item.get('title', ''),
                            'url': item.get('link', ''),
                            'digest': item.get('digest', ''),
                            'create_time': datetime.fromtimestamp(item.get('create_time', 0))
                        })
                        
        except Exception as e:
            print(f"获取文章列表失败: {e}")
        
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

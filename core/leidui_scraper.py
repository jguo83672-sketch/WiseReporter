"""
雷递网爬虫 - 通过文章ID遍历爬取
网址: https://www.leinews.com/
"""
import requests
import json
import time
from datetime import datetime
import re


class LeinewsSpider:
    """雷递网爬虫 - 通过API获取文章详情"""
    
    BASE_URL = 'https://www.leinews.com'
    API_URL = 'https://www.leinews.com/Common/YiAPP.ashx'
    MAX_ARTICLES = 10  # 每次最多采集10篇
    MAX_EMPTY = 5  # 连续空值超过此数量时停止
    START_ID = 33701  # 起始文章ID
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.leinews.com/',
        'Origin': 'https://www.leinews.com',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def _fetch_article_detail(self, article_id):
        """通过API获取文章详情"""
        try:
            # 先访问主页获取必要的cookie
            self.session.get(self.BASE_URL, timeout=10)
            
            # URL查询参数 (根据detail.js)
            url_params = {
                'YiAPP_Method': 'uNews.PC_GetNewsInfo',
                'YiAPP_Action': 'YiAPP.APP.SHOP',
                'YiAPP_SIKW': 'true'
            }
            
            # 原始数据
            data = {
                'NewsCode': str(article_id)
            }
            
            # 构建加密参数 (根据 yiapp-ajax.js 的加密逻辑)
            import urllib.parse
            
            # 1. 构建 MethodName: "Action|Method"
            method_name = f"YiAPP.APP.SHOP|YiAPP.APP.SHOP.uNews.PC_GetNewsInfo"
            
            # 2. 构建 queryparams: URI编码的JSON字符串
            json_parts = []
            for key, value in data.items():
                json_parts.append(f'"{key}":"{urllib.parse.quote(str(value))}"')
            json_str = '{' + ','.join(json_parts) + '}'
            queryparams = urllib.parse.quote(json_str)
            
            # 3. flag: 时间戳
            import time
            flag = str(int(time.time() * 1000))
            
            # 4. sikw: 1 (因为 YiAPP_SIKW=true)
            sikw = '1'
            
            # Form数据
            form_data = {
                'flag': flag,
                'MethodName': method_name,
                'queryparams': queryparams,
                'sikw': sikw
            }
            
            response = self.session.post(
                self.API_URL, 
                params=url_params,
                data=form_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                print(f"[雷递网] HTTP错误: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[雷递网] API请求失败: {e}")
            return None
    
    def crawl(self, existing_urls=None, start_id=None, last_id=None):
        """爬取雷递网最新文章"""
        articles = []
        seen_urls = set(existing_urls) if existing_urls else set()
        
        if last_id:
            current_id = last_id + 1
        elif start_id:
            current_id = start_id
        else:
            current_id = self.START_ID
        
        empty_count = 0
        last_success_id = last_id if last_id else 0
        
        print(f"[雷递网] 开始采集雷递网资讯，从ID {current_id} 开始...")
        
        while len(articles) < self.MAX_ARTICLES:
            if empty_count >= self.MAX_EMPTY:
                print(f"[雷递网] 连续 {empty_count} 篇空值，停止")
                break
            
            article_url = f"{self.BASE_URL}/n{current_id}/detail.html"
            print(f"[雷递网] 尝试 ID: {current_id}")
            
            try:
                # 使用API获取文章详情
                result = self._fetch_article_detail(current_id)
                
                if not result:
                    print(f"[雷递网] ID {current_id} API请求失败")
                    empty_count += 1
                    current_id += 1
                    continue
                
                # 检查API返回状态
                if result.get('status') != 200:
                    msg = result.get('message', '')
                    print(f"[雷递网] ID {current_id} API错误: {msg}")
                    empty_count += 1
                    current_id += 1
                    continue
                
                # 解析数据
                data = result.get('data', {})
                if not data:
                    print(f"[雷递网] ID {current_id} 无数据")
                    empty_count += 1
                    current_id += 1
                    continue
                
                article = self._parse_article_data(data, current_id, article_url)
                
                if not article:
                    print(f"[雷递网] ID {current_id} 解析失败")
                    empty_count += 1
                    current_id += 1
                    continue
                
                # 检查是否重复
                if article['url'] in seen_urls:
                    print(f"[雷递网] ID {current_id} 重复: {article['title'][:30]}...")
                    break
                
                empty_count = 0
                last_success_id = current_id
                seen_urls.add(article['url'])
                articles.append(article)
                
                print(f"[雷递网] 采集成功: {article['title'][:40]}...")
                
            except Exception as e:
                print(f"[雷递网] ID {current_id} 异常: {e}")
                import traceback
                traceback.print_exc()
                empty_count += 1
                current_id += 1
                continue
            
            current_id += 1
        
        print(f"[雷递网] 本次共采集 {len(articles)} 篇文章，最后ID: {last_success_id}")
        return articles, last_success_id
    
    def _parse_article_data(self, data, article_id, article_url):
        """解析API返回的文章数据"""
        try:
            title = data.get('NewsTitle', '')
            if not title:
                return None
            
            # 获取文章内容
            content = data.get('NewsContent', '')
            # 内容是HTML格式
            content_html = content
            
            # 获取纯文本摘要
            if content:
                # 简单提取纯文本
                import re
                text = re.sub(r'<[^>]+>', '', content)
                text = text.strip()
                summary = text[:200] + '...' if len(text) > 200 else text
            else:
                summary = ''
            
            # 获取封面图
            cover_image = data.get('NewsImage', '')
            
            # 获取作者
            author = data.get('N_Author', '雷递网')
            
            # 获取发布时间
            create_date = data.get('CreateDate', '')
            
            # 获取分类/标签
            tag = data.get('NT_Name', '')
            
            return {
                'title': title,
                'url': article_url,
                'summary': summary,
                'content': content,  # HTML内容
                'content_html': content_html,
                'cover_image': cover_image,
                'author': author,
                'publish_date': self._parse_time_string(create_date),
                'tag': tag,
                'source_id': article_id,
            }
            
        except Exception as e:
            print(f"[雷递网] 解析数据异常: {e}")
            return None
    
    def _parse_time_string(self, time_str):
        """解析时间字符串"""
        if not time_str:
            return None
        
        time_str = str(time_str).strip()
        
        # 解析 ISO 格式时间
        if 'T' in time_str:
            try:
                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            except:
                pass
        
        # 解析中文时间格式
        patterns = [
            (r'(\d+)分钟前', lambda m: datetime.now().replace(second=0, microsecond=0)),
            (r'(\d+)小时前', lambda m: datetime.now().replace(minute=0, second=0, microsecond=0)),
            (r'(\d+)天前', lambda m: datetime.now()),
            (r'今天', lambda m: datetime.now()),
            (r'昨天', lambda m: datetime.now()),
        ]
        
        for pattern, handler in patterns:
            match = re.search(pattern, time_str)
            if match:
                return handler(match)
        
        # 尝试解析标准日期格式
        try:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                try:
                    return datetime.strptime(time_str[:19], fmt)
                except:
                    continue
        except:
            pass
        
        return None


if __name__ == '__main__':
    spider = LeinewsSpider()
    articles, last_id = spider.crawl()
    print(f"\n获取到 {len(articles)} 篇文章，最后ID: {last_id}")
    for i, a in enumerate(articles[:5], 1):
        print(f"\n--- 文章 {i} ---")
        print(f"标题: {a.get('title')}")
        print(f"链接: {a.get('url')}")
        print(f"摘要: {a.get('summary', '')[:50]}...")

"""
爬虫基类模块
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import time
import random

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import Config
from core.cookie_manager import CookieManager


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

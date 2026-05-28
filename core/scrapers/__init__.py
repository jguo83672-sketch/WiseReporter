"""
爬虫模块
按类型归类：基础、微信、AI资讯、教育资讯
"""
from core.scrapers.base import BaseScraper
from core.scrapers.wechat import WechatScraper
from core.scrapers.ai_news import AINewsScraper, AIHotSpider
from core.scrapers.education import (
    JiemoduiScraper,
    DuozhiScraper,
    CctvScraper,
    EolScraper,
    EducationNewsScraper,
)

__all__ = [
    'BaseScraper',
    'WechatScraper',
    'AINewsScraper',
    'AIHotSpider',
    'JiemoduiScraper',
    'DuozhiScraper',
    'CctvScraper',
    'EolScraper',
    'EducationNewsScraper',
]

"""
数据采集核心模块 - 向后兼容重导出

爬虫按类型归类在 core/scrapers/ 子包中：
- core/scrapers/base.py      → BaseScraper
- core/scrapers/wechat.py    → WechatScraper
- core/scrapers/ai_news.py   → AINewsScraper, AIHotSpider
- core/scrapers/education.py → JiemoduiScraper, DuozhiScraper, CctvScraper, EolScraper, EducationNewsScraper

本文件保留原有导入路径以保持向后兼容。
"""
from core.scrapers.base import BaseScraper
from core.scrapers.wechat import WechatScraper
from core.scrapers.ai_news import AINewsScraper, AIHotSpider
from core.scrapers.education import JiemoduiScraper, DuozhiScraper, CctvScraper, EolScraper, EducationNewsScraper

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

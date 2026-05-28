"""
周报生成模块
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import pytz
from models import db, Article, AIContent, EducationContent, LeiduiContent, FinanceContent, WeeklyReport, OfficialAccount, WechatContent

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


# 全球知名教育公司名称列表（约100家，用于投融资/财报筛选）
# 数据来源：CompaniesMarketCap上市教育公司排名、TIME 2025 EdTech 榜单、HolonIQ独角兽榜单
EDUCATION_COMPANIES = [
    # ===== 全球上市教育公司（按营收/市值排名） =====
    'Pearson', '培生', '皮尔逊',
    'New Oriental', '新东方',
    'Bright Horizons',
    'TAL Education', '好未来', '学而思',
    'KinderCare Learning Companies', 'KinderCare',
    'Stride', 'K12 Inc',
    'Vtech', '伟易达',
    'Adtalem', 'Adtalem Global Education',
    'Laureate Education',
    'John Wiley & Sons', 'Wiley',
    'Scholastic',
    'Barnes & Noble Education',
    'Strategic Education',
    'Grand Canyon Education',
    'Duolingo', '多邻国',
    'Phoenix Education Partners',
    'Universal Technical Institute',
    'Perdoceo Education',
    'Gaotu Techedu', '高途',
    'Udemy',
    'Coursera',
    'Afya',
    'American Public Education',
    'G8 Education',
    'IDP Education',
    'Lincoln Educational Services',
    'Skillsoft',
    'Chegg',
    'Vitru',
    'Proeduca Altus',
    'Offcn Education', '中公教育',
    'Vasta Platform',
    'Docebo',
    'D2L',
    'Nerdy',
    'iHuman', '洪恩',
    'Tribal Group',
    '3P Learning',
    'Leifras',
    'Aptech',
    'ATA Creativity Global',
    'Kuke Music Holding', '库克音乐',
    'Genius Group',
    # ===== 全球知名教育科技独角兽/私有公司 =====
    'BYJU', 'BYJU\'S',
    'BetterUp',
    'Synthesia',
    'Handshake',
    'Go1',
    'Emeritus',
    'Age of Learning',
    'upGrad',
    'Multiverse',
    'Kajabi',
    'Degreed',
    'Guild Education',
    'Preply',
    'Speak',
    'ApplyBoard',
    'PhysicsWallah',
    'Unacademy',
    'Simplilearn',
    'Vedantu',
    'Lead School',
    'MasterClass',
    'Outschool',
    'Articulate',
    'GoStudent',
    'Domestika',
    'Newsela',
    'Course Hero',
    'ClassDojo',
    'Quizlet',
    'Kahoot',
    'GoGuardian',
    'Paper',
    'Udacity',
    'Pluralsight',
    'Babbel',
    'Busuu',
    'Lingoda',
    'iTalki',
    'Cambium Learning',
    'Renaissance Learning',
    'PowerSchool',
    'Discovery Education',
    'Dreambox Learning',
    'IXL Learning',
    'Curriculum Associates', 'i-Ready',
    'BrainPOP',
    'Prodigy Education',
    'Ellucian',
    'Cengage',
    'McGraw Hill', '麦格劳-希尔',
    'Houghton Mifflin Harcourt', 'HMH',
    'Instructure', 'Canvas',
    'Turnitin',
    '2U', 'edX',
    'Kaplan', '卡普兰',
    'EF Education First', '英孚教育',
    'Rosetta Stone',
    'Khan Academy', '可汗学院',
    'College Board',
    'ACT',
    'Sylvan Learning',
    'Kumon', '公文式',
    'Mathnasium',
    'Navitas',
    'StudyGroup',
    'Benesse Holdings',
    'Springer Nature',
    'Anthology', 'Blackboard',
    # ===== 中国教育科技公司 =====
    '编程猫', 'Codemao',
    '网易有道', 'Youdao',
    '猿辅导', '猿力科技', 'Yuanfudao',
    '作业帮', 'Zuoyebang',
    'VIPKID',
    '51Talk', '无忧英语',
    '火花思维',
    '小盒科技',
    '美术宝',
    '爱学习',
    '粉笔', 'Fenbi',
    '华图教育',
    '科大讯飞', 'iFlytek',
    '尚德机构', 'Sunlands',
    '学堂在线',
    '阿卡索',
    '伴鱼',
    '云学堂',
    'iTutorGroup', '平安好学',
    '一起教育',
    '读书郎',
    '鸿合科技',
    '视源股份', '希沃',
    '佳发教育',
    '全通教育',
    '立思辰',
    '中文在线',
    '传智教育',
]


# 缓存：避免每次匹配都查数据库
_edu_companies_cache = None
_cache_timestamp = None
_CACHE_TTL_SECONDS = 300  # 缓存5分钟


def _get_education_company_keywords() -> list:
    """获取教育公司关键词列表（优先数据库，兜底硬编码）"""
    global _edu_companies_cache, _cache_timestamp
    import time as _time
    now = _time.time()
    if _edu_companies_cache is not None and _cache_timestamp and (now - _cache_timestamp) < _CACHE_TTL_SECONDS:
        return _edu_companies_cache

    try:
        from models import EducationCompany
        keywords = [ec.keyword for ec in EducationCompany.query.order_by(EducationCompany.keyword).all()]
        if keywords:
            _edu_companies_cache = keywords
            _cache_timestamp = now
            return keywords
    except Exception:
        pass

    # 兜底：使用硬编码列表（同时写入数据库以初始化）
    return list(EDUCATION_COMPANIES)


def invalidate_edu_companies_cache():
    """使教育公司关键词缓存失效（关键词变更后调用）"""
    global _edu_companies_cache, _cache_timestamp
    _edu_companies_cache = None
    _cache_timestamp = None


def _is_english_keyword(keyword: str) -> bool:
    """判断关键词是否包含英文字母（需要单词边界匹配避免误匹配）"""
    return bool(re.search(r'[a-zA-Z]', keyword))


def _match_keyword(keyword: str, text: str) -> bool:
    """检查关键词是否在文本中出现。
    - 英文关键词：使用单词边界 \b 防止 ACT 误匹配 impact、Paper 误匹配 newspaper
    - 中文关键词：使用子串匹配（中文天然有分词边界）
    """
    if not text or not keyword:
        return False
    if _is_english_keyword(keyword):
        # 单词边界匹配：\b 在 ASCII 单词和非 ASCII（如中文）之间也视为边界
        pattern = r'(?<![a-zA-Z])' + re.escape(keyword) + r'(?![a-zA-Z])'
        return bool(re.search(pattern, text, re.IGNORECASE))
    else:
        return keyword.lower() in text.lower()


def _find_matched_keyword_in_text(keywords: list, text: str) -> str:
    """在文本中查找第一个匹配的关键词，返回关键词文本。"""
    if not text:
        return ''
    for company in keywords:
        if _match_keyword(company, text):
            return company
    return ''


def contains_education_company(text: str) -> bool:
    """检查文本是否包含全球知名教育公司名称（模块级函数，供多处复用）"""
    if not text:
        return False
    keywords = _get_education_company_keywords()
    return bool(_find_matched_keyword_in_text(keywords, text))


def find_matching_education_company(*texts: str) -> str:
    """在给定文本中查找匹配的教育公司关键词，返回匹配到的第一个关键词。
    未匹配到时返回空字符串。
    
    Args:
        *texts: 待检查的文本（title, summary, content 等）
    """
    if not texts:
        return ''
    combined = ' '.join(t for t in texts if t)
    if not combined:
        return ''
    keywords = _get_education_company_keywords()
    return _find_matched_keyword_in_text(keywords, combined)


class WeeklyReportGenerator:
    """周报生成器"""
    
    def __init__(self):
        self.report_date = None
        self.period_start = None
        self.period_end = None
    
    def generate_report(self, start_date: datetime = None, 
                        end_date: datetime = None) -> WeeklyReport:
        """生成周报
        
        Args:
            start_date: 周报开始日期，默认为本周一
            end_date: 周报结束日期，默认为本周日
        """
        # 计算本周周期（周一到周日，使用北京时间）
        today = datetime.now(BEIJING_TZ).date()
        
        if end_date is None:
            # 默认结束日期为本周日
            end_date = datetime.combine(today + timedelta(days=(6 - today.weekday())), datetime.max.time())
        else:
            end_date = datetime.combine(end_date, datetime.max.time())
        
        if start_date is None:
            # 默认开始日期为本周一
            start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
        else:
            start_date = datetime.combine(start_date, datetime.min.time())
        
        self.period_start = start_date
        self.period_end = end_date
        self.report_date = today
        
        # 收集数据
        articles = self._collect_articles(start_date, end_date)
        ai_news = self._collect_ai_news(start_date, end_date)
        edu_news = self._collect_edu_news(start_date, end_date)
        leidui_news = self._collect_leidui_news(start_date, end_date)
        finance_news = self._collect_finance_news(start_date, end_date)
        
        # 生成内容
        content = self._generate_content(articles, ai_news, edu_news, leidui_news, finance_news)
        
        # 生成标题
        title = f"教育行业周报 {start_date.strftime('%Y年%m月%d日')} - {end_date.strftime('%Y年%m月%d日')}"
        
        # 创建周报记录
        report = WeeklyReport(
            title=title,
            content=content,
            report_date=self.report_date,
            period_start=start_date.date(),
            period_end=end_date.date(),
            article_count=len(articles),
            ai_news_count=len(ai_news),
            status='draft'
        )
        
        db.session.add(report)
        db.session.commit()
        
        return report
    
    def _unify_article(self, article: Article) -> dict:
        """将 Article 对象转为统一格式"""
        return {
            'title': article.title,
            'url': article.url,
            'author': article.author or '',
            'summary': article.summary or '',
            'publish_date': article.publish_date,
            'account_name': article.account.name if article.account else '未知来源',
            'is_important': getattr(article, 'is_important', False),
        }
    
    def _unify_wechat(self, wechat: WechatContent) -> dict:
        """将 WechatContent 对象转为统一格式"""
        return {
            'title': wechat.title,
            'url': wechat.url,
            'author': wechat.author or '',
            'summary': wechat.summary or '',
            'publish_date': wechat.publish_date,
            'account_name': wechat.account_name or '未知来源',
            'is_important': getattr(wechat, 'is_favorite', False),
        }
    
    def _collect_articles(self, start_date: datetime, 
                         end_date: datetime) -> List[dict]:
        """收集周期内的公众号文章（按发布时间筛选，同时收集Article和WechatContent）"""
        result = []
        
        # 收集 Article 表（关联 OfficialAccount 的文章）
        article_records = Article.query.filter(
            Article.publish_date >= start_date,
            Article.publish_date <= end_date
        ).order_by(Article.publish_date.desc()).all()
        
        for a in article_records:
            result.append(self._unify_article(a))
        
        # 收集 WechatContent 表（独立爬取的公众号文章）
        wechat_records = WechatContent.query.filter(
            WechatContent.publish_date >= start_date,
            WechatContent.publish_date <= end_date
        ).order_by(WechatContent.publish_date.desc()).all()
        
        for w in wechat_records:
            result.append(self._unify_wechat(w))
        
        # 按发布日期排序（最新在前，无日期的排在最后）
        result.sort(key=lambda x: x['publish_date'] or datetime(1900, 1, 1), reverse=True)
        
        return result
    
    def _contains_education_company(self, text: str) -> bool:
        """检查文本是否包含教育公司名称"""
        return contains_education_company(text)
    
    def _filter_education_company_articles(self, articles: List[dict]) -> List[dict]:
        """筛选包含教育公司的文章"""
        filtered = []
        for article in articles:
            title = article.get('title', '')
            summary = article.get('summary', '')
            # 检查标题
            if self._contains_education_company(title):
                filtered.append(article)
                continue
            # 检查摘要
            if self._contains_education_company(summary):
                filtered.append(article)
                continue
            # 统一格式没有content字段（WechatContent可能有但Article不一定），按标题和摘要判断即可
        return filtered
    
    def _collect_ai_news(self, start_date: datetime, 
                         end_date: datetime) -> List[AIContent]:
        """收集周期内的AI资讯（按发布时间筛选，仅筛选产品发布/更新、模型发布/更新）"""
        # 目标分类
        target_categories = ['产品发布/更新', '模型发布/更新']
        
        # 收集周期内所有AI资讯（按发布时间筛选）
        all_news = AIContent.query.filter(
            AIContent.publish_date >= start_date,
            AIContent.publish_date <= end_date
        ).order_by(AIContent.publish_date.desc()).all()
        
        # 按分类筛选
        filtered_news = [
            news for news in all_news
            if news.category in target_categories
        ]
        
        return filtered_news
    
    def _collect_edu_news(self, start_date: datetime,
                          end_date: datetime) -> List[EducationContent]:
        """收集周期内的教育资讯（仅收藏的文章，芥末堆、多知网、央视网）"""
        return EducationContent.query.filter(
            EducationContent.publish_date >= start_date,
            EducationContent.publish_date <= end_date,
            EducationContent.is_favorite == True
        ).order_by(EducationContent.publish_date.desc()).all()
    
    def _collect_leidui_news(self, start_date: datetime,
                              end_date: datetime) -> List[LeiduiContent]:
        """收集周期内已被收藏的雷递网投融资/财报资讯（仅知名教育公司）"""
        return LeiduiContent.query.filter(
            LeiduiContent.publish_date >= start_date,
            LeiduiContent.publish_date <= end_date,
            LeiduiContent.is_favorite == True
        ).order_by(LeiduiContent.publish_date.desc()).all()

    def _collect_finance_news(self, start_date: datetime,
                               end_date: datetime) -> List[FinanceContent]:
        """收集周期内已被收藏的投融资/财报资讯（投资界等）"""
        return FinanceContent.query.filter(
            FinanceContent.publish_date >= start_date,
            FinanceContent.publish_date <= end_date,
            FinanceContent.is_favorite == True
        ).order_by(FinanceContent.publish_date.desc()).all()
    
    def _collect_important_titles(self, articles: List[dict],
                                   ai_news: List[AIContent],
                                   edu_news: List[EducationContent],
                                   leidui_news: List[LeiduiContent],
                                   finance_news: List[FinanceContent] = None) -> List[dict]:
        """收集最重要的资讯标题（筛选过的核心内容）"""
        result = []

        if finance_news is None:
            finance_news = []

        # 教育资讯：收藏的文章都是重点，全部列出（最多6条）
        for news in edu_news[:6]:
            result.append({
                'title': news.title,
                'url': news.url or '#',
                'source': news.source_name or news.source or '教育资讯',
            })

        # AI资讯：产品/模型发布（最多4条）
        for news in ai_news[:4]:
            result.append({
                'title': news.title,
                'url': news.url or '#',
                'source': 'AI前沿',
            })

        # 投融资：合并雷递网 + 投资界（最多5条）
        all_finance = list(leidui_news) + list(finance_news)
        all_finance.sort(key=lambda x: x.publish_date or datetime(1900, 1, 1), reverse=True)
        for news in all_finance[:5]:
            result.append({
                'title': news.title,
                'url': news.url or '#',
                'source': '投融资',
            })

        # 公众号：重点推荐（最多3条）
        important_articles = [a for a in articles if a.get('is_important')]
        for article in important_articles[:3]:
            result.append({
                'title': article.get('title', ''),
                'url': article.get('url', '#'),
                'source': article.get('account_name', '公众号'),
            })

        # 去重（按标题相似度），保留总数不超过20条
        seen_titles = set()
        unique_result = []
        for item in result:
            key = item['title'][:30].strip()
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique_result.append(item)

        return unique_result[:15]
    
    def _generate_weekly_overview(self, articles: List[dict],
                                   ai_news: List[AIContent],
                                   edu_news: List[EducationContent],
                                   leidui_news: List[LeiduiContent],
                                   finance_news: List[FinanceContent] = None) -> str:
        """使用AI生成周报摘要"""
        # 收集关键信息用于生成摘要
        context_parts = []

        if finance_news is None:
            finance_news = []
        
        # 教育资讯
        if edu_news:
            edu_titles = [f"· {n.title}" for n in edu_news[:10]]
            context_parts.append(f"本周教育领域重点资讯：\n" + "\n".join(edu_titles))
        
        # 投融资（合并雷递网 + 投资界）
        all_finance = list(leidui_news) + list(finance_news)
        if all_finance:
            lei_titles = [f"· {n.title}" for n in all_finance[:8]]
            context_parts.append(f"投融资/财报动态：\n" + "\n".join(lei_titles))
        
        # AI资讯
        if ai_news:
            ai_titles = [f"· {n.title}" for n in ai_news[:5]]
            context_parts.append(f"AI前沿资讯：\n" + "\n".join(ai_titles))
        
        if not context_parts:
            return ''
        
        context_text = "\n\n".join(context_parts)
        
        # 截取合适长度
        if len(context_text) > 3000:
            context_text = context_text[:3000] + '…'
        
        prompt = f"""你是一个教育行业资深分析师，请根据以下本周教育行业资讯，生成一段简洁的周报摘要（150-250字）。

要求：
1. 概括本周教育行业的核心动态和趋势
2. 突出最重要的信息（如重大投融资、政策变化、重要产品发布等）
3. 语言专业、客观、简练
4. 只输出摘要内容，不要多余的开场白或结束语
5. 使用中文

本周资讯概览：
{context_text}

周报摘要："""
        
        try:
            # 通过 Flask config 获取配置；如果不在应用上下文中则直接尝试读取配置
            from flask import current_app
            api_key = current_app.config.get('OPENROUTER_API_KEY', '')
            base_url = current_app.config.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
            models = current_app.config.get('AI_SUMMARY_MODELS', ['qwen/qwen3-next-80b-a3b-instruct:free'])
        except RuntimeError:
            # 兜底：尝试从 config 模块读取
            try:
                from config import Config
                api_key = Config.OPENROUTER_API_KEY or ''
                base_url = getattr(Config, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
                models = getattr(Config, 'AI_SUMMARY_MODELS', ['qwen/qwen3-next-80b-a3b-instruct:free'])
            except:
                api_key = ''
                base_url = 'https://openrouter.ai/api/v1'
                models = ['qwen/qwen3-next-80b-a3b-instruct:free']
        
        if not api_key:
            return ''
        
        import time as _time
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        for i, m in enumerate(models):
            try:
                response = client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=800,
                )
                summary = response.choices[0].message.content
                if summary and summary.strip():
                    if i > 0:
                        print(f"[周报摘要] 降级后使用模型 {m} 成功")
                    return summary.strip()
                print(f"[周报摘要] 模型 {m} 返回空内容")
            except Exception as e:
                if i < len(models) - 1:
                    print(f"[周报摘要] 模型 {m} 失败，尝试下一个: {e}")
                    _time.sleep(1)
                else:
                    print(f"[周报摘要] 所有模型均失败，最后一个错误: {e}")
        return ''
    
    def _format_date(self, dt) -> str:
        """安全格式化日期"""
        if dt is None:
            return ''
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M')
        return str(dt)
    
    def _format_date_short(self, dt) -> str:
        """安全格式化日期（仅日期）"""
        if dt is None:
            return ''
        if isinstance(dt, datetime):
            return dt.strftime('%m-%d')
        return str(dt)[:10]
    
    def _generate_content(self, articles: List[dict], 
                         ai_news: List[AIContent],
                         edu_news: List[EducationContent],
                         leidui_news: List[LeiduiContent],
                         finance_news: List[FinanceContent] = None) -> str:
        """生成周报内容（HTML格式）"""
        if finance_news is None:
            finance_news = []

        period_str = f"{self.period_start.strftime('%Y.%m.%d')} - {self.period_end.strftime('%Y.%m.%d')}"
        
        # 收集重要资讯标题
        important_titles = self._collect_important_titles(articles, ai_news, edu_news, leidui_news, finance_news)
        
        # 生成AI周报摘要
        weekly_summary = self._generate_weekly_overview(articles, ai_news, edu_news, leidui_news, finance_news)
        
        # 构建重点关注标题列表HTML
        highlights_html = ''
        if important_titles:
            titles_html = ''
            for item in important_titles:
                titles_html += f'                <li><a href="{item["url"]}" target="_blank" rel="noopener">{item["title"]}</a><span class="wr-highlight-source">{item["source"]}</span></li>\n'
            highlights_html = f'''
        <div class="wr-hero-highlights">
            <h3 class="wr-highlights-title">重点关注</h3>
            <ul class="wr-highlights-list">
{titles_html}            </ul>
        </div>'''
        
        # 构建AI摘要HTML
        summary_html = ''
        if weekly_summary:
            summary_html = f'''
        <div class="wr-hero-summary">
            <h3 class="wr-summary-title">本周摘要</h3>
            <p class="wr-summary-text">{weekly_summary}</p>
        </div>'''
        
        html = f'''<!-- WiseReporter Weekly Report -->
<div class="wr-weekly-report">
    <!-- 头部 Hero -->
    <div class="wr-hero">
        <div class="wr-hero-badge">WEEKLY REPORT</div>
        <h1 class="wr-hero-title">教育行业周报</h1>
        <p class="wr-hero-period">{period_str}</p>
        {summary_html}
        {highlights_html}
        <div class="wr-hero-stats">
            <div class="wr-stat-item">
                <span class="wr-stat-num">{len(ai_news)}</span>
                <span class="wr-stat-label">AI前沿</span>
            </div>
            <div class="wr-stat-divider"></div>
            <div class="wr-stat-item">
                <span class="wr-stat-num">{len(edu_news)}</span>
                <span class="wr-stat-label">教育资讯</span>
            </div>
            <div class="wr-stat-divider"></div>
            <div class="wr-stat-item">
                <span class="wr-stat-num">{len(leidui_news) + len(finance_news)}</span>
                <span class="wr-stat-label">投融资</span>
            </div>
            <div class="wr-stat-divider"></div>
            <div class="wr-stat-item">
                <span class="wr-stat-num">{len(articles)}</span>
                <span class="wr-stat-label">公众号</span>
            </div>
        </div>
        <p class="wr-hero-time">生成时间：{datetime.now(BEIJING_TZ).strftime('%Y年%m月%d日 %H:%M')}（北京时间）</p>
    </div>
'''
        
        # === 教育资讯 ===
        if edu_news:
            html += f'''
    <div class="wr-section">
        <div class="wr-section-header">
            <span class="wr-section-num">01</span>
            <h2 class="wr-section-title">教育资讯</h2>
            <span class="wr-section-count">{len(edu_news)} 条</span>
        </div>
        <div class="wr-article-list">
'''
            # 按来源分组
            edu_by_source = {}
            for news in edu_news:
                source = news.source_name or news.source or '其他'
                if source not in edu_by_source:
                    edu_by_source[source] = []
                edu_by_source[source].append(news)
            
            for source_name, news_list in edu_by_source.items():
                html += f'''
            <div class="wr-subsection">
                <h3 class="wr-subsection-title">{source_name}</h3>
'''
                for news in news_list[:15]:
                    html += self._render_article_card(
                        title=news.title,
                        url=news.url,
                        summary=news.summary,
                        ai_summary=getattr(news, 'ai_summary', ''),
                        publish_date=news.publish_date,
                        source=source_name,
                        source_type='edu'
                    )
                html += '''
            </div>
'''
            html += '''
        </div>
    </div>
'''
        
        # === AI前沿资讯 ===
        if ai_news:
            html += f'''
    <div class="wr-section">
        <div class="wr-section-header">
            <span class="wr-section-num">02</span>
            <h2 class="wr-section-title">AI 前沿资讯</h2>
            <span class="wr-section-count">{len(ai_news)} 条</span>
        </div>
        <div class="wr-article-list">
'''
            # 按分类分组
            ai_by_category = {}
            for news in ai_news:
                cat = news.category or '其他'
                if cat not in ai_by_category:
                    ai_by_category[cat] = []
                ai_by_category[cat].append(news)
            
            for cat_name, news_list in ai_by_category.items():
                html += f'''
            <div class="wr-subsection">
                <h3 class="wr-subsection-title">{cat_name}</h3>
'''
                for news in news_list[:15]:
                    html += self._render_article_card(
                        title=news.title,
                        url=news.url,
                        summary=news.summary,
                        publish_date=news.publish_date,
                        source=news.source or 'AI资讯',
                        source_type='ai'
                    )
                html += '''
            </div>
'''
            html += '''
        </div>
    </div>
'''
        
        # === 投融资/财报 ===
        # 合并雷递网 + 投资界数据，按发布时间排序
        all_finance = list(leidui_news)
        for fn in finance_news:
            all_finance.append(fn)
        all_finance.sort(key=lambda x: x.publish_date or datetime(1900, 1, 1), reverse=True)

        if all_finance:
            html += f'''
    <div class="wr-section">
        <div class="wr-section-header">
            <span class="wr-section-num">03</span>
            <h2 class="wr-section-title">投融资 / 财报动态</h2>
            <span class="wr-section-count">{len(all_finance)} 条</span>
        </div>
        <div class="wr-article-list">
'''
            # 按来源分组
            finance_by_source = {}
            for news in all_finance:
                sname = getattr(news, 'source_name', '') or getattr(news, 'source', '') or '其他'
                if sname not in finance_by_source:
                    finance_by_source[sname] = []
                finance_by_source[sname].append(news)

            for sname, news_list in finance_by_source.items():
                html += f'''
            <div class="wr-subsection">
                <h3 class="wr-subsection-title">{sname}</h3>
'''
                for news in news_list[:15]:
                    html += self._render_article_card(
                        title=news.title,
                        url=news.url,
                        summary=getattr(news, 'summary', ''),
                        publish_date=news.publish_date,
                        source=sname,
                        source_type='leidui'
                    )
                html += '''
            </div>
'''
            html += '''
        </div>
    </div>
'''
        
        # === 公众号动态 ===
        if articles:
            # 按公众号分组（统一格式使用 account_name 字段）
            account_articles = {}
            for article in articles:
                account_name = article['account_name'] or '未知来源'
                if account_name not in account_articles:
                    account_articles[account_name] = []
                account_articles[account_name].append(article)
            
            html += f'''
    <div class="wr-section">
        <div class="wr-section-header">
            <span class="wr-section-num">04</span>
            <h2 class="wr-section-title">公众号动态</h2>
            <span class="wr-section-count">{len(articles)} 篇</span>
        </div>
        <div class="wr-article-list">
'''
            # 重点文章优先
            important_articles = [a for a in articles if a.get('is_important')]
            if important_articles:
                html += '''
            <div class="wr-subsection">
                <h3 class="wr-subsection-title wr-important">重点推荐</h3>
'''
                for article in important_articles[:10]:
                    html += self._render_account_article_card(article)
                html += '''
            </div>
'''
            
            for account_name, account_article_list in account_articles.items():
                html += f'''
            <div class="wr-subsection">
                <h3 class="wr-subsection-title">{account_name}</h3>
'''
                for article in account_article_list[:10]:
                    html += self._render_account_article_card(article)
                html += '''
            </div>
'''
            html += '''
        </div>
    </div>
'''
        
        # 页脚
        html += f'''
    <div class="wr-footer">
        <p>本报告由 <strong>WiseReporter</strong> 自动生成 · {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')}（北京时间）</p>
    </div>
</div>'''
        
        return html
    
    def _render_article_card(self, title: str, url: str, summary: str, 
                             publish_date, source: str, source_type: str = 'default',
                             ai_summary: str = '') -> str:
        """渲染单篇文章卡片（通用）"""
        date_str = self._format_date(publish_date) if publish_date else ''
        date_short = self._format_date_short(publish_date) if publish_date else ''
        
        # AI摘要
        ai_summary_html = ''
        if ai_summary:
            ai_summary_html = f'<p class="wr-card-ai-summary"><strong>AI摘要：</strong>{ai_summary}</p>'
        
        # 原文摘要截取
        summary_text = ''
        if summary:
            summary_text = summary[:200].strip()
            if len(summary) > 200:
                summary_text += '…'
        
        source_class = f'wr-source-{source_type}'
        
        return f'''
                <div class="wr-article-card">
                    <div class="wr-card-left">
                        <h4 class="wr-card-title">
                            <a href="{url}" target="_blank" rel="noopener">{title}</a>
                        </h4>
                        {ai_summary_html}
                        {f'<p class="wr-card-summary">{summary_text}</p>' if summary_text else ''}
                    </div>
                    <div class="wr-card-right">
                        <span class="wr-source-badge {source_class}">{source}</span>
                        {f'<span class="wr-card-date">{date_short}</span>' if date_short else ''}
                    </div>
                </div>'''
    
    def _render_account_article_card(self, article: dict) -> str:
        """渲染公众号文章卡片（接受统一格式dict）"""
        pub_date = article.get('publish_date')
        date_str = self._format_date(pub_date) if pub_date else ''
        date_short = self._format_date_short(pub_date) if pub_date else ''
        
        summary = article.get('summary', '')
        summary_text = ''
        if summary:
            summary_text = summary[:200].strip()
            if len(summary) > 200:
                summary_text += '…'
        
        account_name = article.get('account_name', '未知来源')
        url = article.get('url', '#')
        title = article.get('title', '')
        
        return f'''
                <div class="wr-article-card">
                    <div class="wr-card-left">
                        <h4 class="wr-card-title">
                            <a href="{url}" target="_blank" rel="noopener">{title}</a>
                        </h4>
                        {f'<p class="wr-card-summary">{summary_text}</p>' if summary_text else ''}
                    </div>
                    <div class="wr-card-right">
                        <span class="wr-source-badge wr-source-wechat">{account_name}</span>
                        {f'<span class="wr-card-date">{date_short}</span>' if date_short else ''}
                    </div>
                </div>'''
    
    @staticmethod
    def convert_to_markdown(content: str) -> str:
        """将HTML内容转换为纯文本摘要（用于Markdown导出）"""
        # 简单的HTML转文本
        text = re.sub(r'<[^>]+>', '', content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    @staticmethod
    def publish_report(report_id: int) -> Optional[WeeklyReport]:
        """发布周报"""
        report = WeeklyReport.query.get(report_id)
        if report:
            report.status = 'published'
            db.session.commit()
        return report
    
    @staticmethod
    def get_reports(limit: int = 10) -> List[WeeklyReport]:
        """获取周报列表"""
        return WeeklyReport.query.order_by(
            WeeklyReport.report_date.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_current_week_range() -> tuple:
        """获取本周日期范围（周一到周日）
        
        Returns:
            tuple: (start_date, end_date) - datetime对象
        """
        today = datetime.now(BEIJING_TZ).date()
        start_of_week = today - timedelta(days=today.weekday())  # 周一
        end_of_week = start_of_week + timedelta(days=6)  # 周日
        return (
            datetime.combine(start_of_week, datetime.min.time()),
            datetime.combine(end_of_week, datetime.max.time())
        )

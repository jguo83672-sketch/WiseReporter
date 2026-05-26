"""
周报生成模块
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import pytz
from models import db, Article, AIContent, EducationContent, LeiduiContent, WeeklyReport, OfficialAccount, WechatContent

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


# 教育公司名称列表（用于投融资/财报筛选）
EDUCATION_COMPANIES = [
    # 英文公司
    'Pearson', '皮尔逊', 'McGraw Hill', '麦格劳-希尔', 'Cengage', 'Coursera', 'Udemy',
    'Duolingo', '2U', 'Udacity', 'Khan Academy', '可汗学院', 'Quizlet', 'Chegg',
    'Blackboard', 'Instructure', 'Canvas', 'Pluralsight', 'Skillsoft', 'Docebo', 'D2L',
    'Kaplan', '卡普兰', 'Princeton Review', '普林斯顿评论', 'Apollo Education Group',
    'Covista', 'Adtalem', 'Grand Canyon Education', 'Stride', 'K12 Inc', 'MagicSchool AI',
    'Turnitin', 'College Board', 'ACT', 'Houghton Mifflin Harcourt', 'Nelnet', 'Remind',
    'Outschool', 'OpenText', 'ApplyBoard', 'Pearson Vue', 'Cambridge Assessment',
    'Oxford University Press', '牛津大学出版社', 'Cambridge University Press', '剑桥大学出版社',
    'FutureLearn', 'Pearson Education', 'Languagenut', 'Reed Elsevier', 'Pearson English',
    'Georg Von Holtzbrinck', 'Springer Nature', 'Bettermarks', 'Babbel', 'Deutsche Telekom Education',
    'Kahoot', '挪威', 'EF Education First', '瑞士', 'Rosetta Stone', '卢森堡',
    'Efekta Education', '瑞典', 'Lingopie', '西班牙', 'Busuu', 'Lingoda', 'Preply',
    'iTalki', 'Studocu', '荷兰',
    # 中文公司
    '新东方', '好未来', '学而思', '网易有道', '编程猫', '猿辅导', '作业帮', '高途',
    'VIPKID', '51Talk', '中公教育', '粉笔', '华图教育', '科大讯飞', '小盒科技',
    '美术宝', '爱学习', '阿卡索', '伴鱼', '学堂在线', '尚德机构',
    # 国外教育公司中文名
    'BYJU', 'Unacademy', 'PhysicsWallah', 'upGrad', 'Simplilearn',
    'Benesse Holdings', 'Sega Sammy Holdings', 'YBM Sisa', 'Cermati', 'Edukasyon',
    'Navitas', 'IDP Education', 'Open Universities Australia', 'StudyGroup',
    'Laureate Education', 'Sylvan Learning', 'Kumon', '公文式', 'Mathnasium',
    'TAL Education', 'iTutorGroup'
]


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
        
        # 生成内容
        content = self._generate_content(articles, ai_news, edu_news, leidui_news)
        
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
        if not text:
            return False
        text_lower = text.lower()
        for company in EDUCATION_COMPANIES:
            if company.lower() in text_lower:
                return True
        return False
    
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
        """收集周期内的教育资讯（按发布时间筛选，芥末堆、多知网、央视网）"""
        return EducationContent.query.filter(
            EducationContent.publish_date >= start_date,
            EducationContent.publish_date <= end_date
        ).order_by(EducationContent.publish_date.desc()).all()
    
    def _collect_leidui_news(self, start_date: datetime,
                              end_date: datetime) -> List[LeiduiContent]:
        """收集周期内的雷递网投融资/财报资讯"""
        return LeiduiContent.query.filter(
            LeiduiContent.publish_date >= start_date,
            LeiduiContent.publish_date <= end_date
        ).order_by(LeiduiContent.publish_date.desc()).all()
    
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
                         leidui_news: List[LeiduiContent]) -> str:
        """生成周报内容（HTML格式）"""
        total_count = len(articles) + len(ai_news) + len(edu_news) + len(leidui_news)
        period_str = f"{self.period_start.strftime('%Y.%m.%d')} - {self.period_end.strftime('%Y.%m.%d')}"
        
        html = f'''<!-- WiseReporter Weekly Report -->
<div class="wr-weekly-report">
    <!-- 头部 Hero -->
    <div class="wr-hero">
        <div class="wr-hero-badge">WEEKLY REPORT</div>
        <h1 class="wr-hero-title">教育行业周报</h1>
        <p class="wr-hero-period">{period_str}</p>
        <div class="wr-hero-stats">
            <div class="wr-stat-item">
                <span class="wr-stat-num">{total_count}</span>
                <span class="wr-stat-label">总资讯</span>
            </div>
            <div class="wr-stat-divider"></div>
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
                <span class="wr-stat-num">{len(leidui_news)}</span>
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
        if leidui_news:
            html += f'''
    <div class="wr-section">
        <div class="wr-section-header">
            <span class="wr-section-num">03</span>
            <h2 class="wr-section-title">投融资 / 财报动态</h2>
            <span class="wr-section-count">{len(leidui_news)} 条</span>
        </div>
        <div class="wr-article-list">
'''
            # 按分类分组
            lei_by_category = {}
            for news in leidui_news:
                cat = news.category or '行业动态'
                if cat not in lei_by_category:
                    lei_by_category[cat] = []
                lei_by_category[cat].append(news)
            
            for cat_name, news_list in lei_by_category.items():
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
                        source=news.source_name or '雷递网',
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
                             publish_date, source: str, source_type: str = 'default') -> str:
        """渲染单篇文章卡片（通用）"""
        date_str = self._format_date(publish_date) if publish_date else ''
        date_short = self._format_date_short(publish_date) if publish_date else ''
        
        # 摘要截取
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
    def convert_to_html(content: str) -> str:
        """将周报内容转换为完整HTML页面（用于导出）"""
        # content已经是HTML格式，直接包裹
        return content
    
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
    def get_latest_report() -> Optional[WeeklyReport]:
        """获取最新周报"""
        return WeeklyReport.query.order_by(
            WeeklyReport.report_date.desc()
        ).first()
    
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

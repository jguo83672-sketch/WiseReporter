"""
周报生成模块
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import markdown
from models import db, Article, AIContent, EducationContent, WeeklyReport, OfficialAccount

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
        # 计算本周周期（周一到周日）
        today = datetime.utcnow().date()
        
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
        
        # 生成内容
        content = self._generate_content(articles, ai_news, edu_news)
        
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
    
    def _collect_articles(self, start_date: datetime, 
                         end_date: datetime) -> List[Article]:
        """收集周期内的公众号文章"""
        return Article.query.filter(
            Article.created_at >= start_date,
            Article.created_at <= end_date
        ).order_by(Article.created_at.desc()).all()
    
    def _collect_ai_news(self, start_date: datetime, 
                         end_date: datetime) -> List[AIContent]:
        """收集周期内的AI资讯"""
        return AIContent.query.filter(
            AIContent.created_at >= start_date,
            AIContent.created_at <= end_date
        ).order_by(AIContent.created_at.desc()).all()
    
    def _collect_edu_news(self, start_date: datetime,
                          end_date: datetime) -> List[EducationContent]:
        """收集周期内的教育资讯（芥末堆、多知网、央视网）"""
        return EducationContent.query.filter(
            EducationContent.created_at >= start_date,
            EducationContent.created_at <= end_date
        ).order_by(EducationContent.created_at.desc()).all()
    
    def _generate_content(self, articles: List[Article], 
                         ai_news: List[AIContent],
                         edu_news: List[EducationContent]) -> str:
        """生成周报内容（Markdown格式）"""
        md = []
        
        # 标题
        md.append(f"# 教育行业周报\n")
        md.append(f"**周期**: {self.period_start.strftime('%Y年%m月%d日')} - {self.period_end.strftime('%Y年%m月%d日')}\n")
        md.append(f"**生成时间**: {datetime.utcnow().strftime('%Y年%m月%d日 %H:%M')}\n")
        md.append("---\n")
        
        # 统计概览
        md.append("## 数据概览\n")
        md.append(f"- 公众号文章: **{len(articles)}篇**\n")
        md.append(f"- AI前沿资讯: **{len(ai_news)}条**\n")
        md.append(f"- 教育资讯: **{len(edu_news)}条**\n")
        
        # 按来源分组教育资讯
        if edu_news:
            md.append("\n## 教育资讯\n")
            
            # 按来源分组
            edu_by_source = {}
            for news in edu_news:
                source = news.source_name or news.source or '其他'
                if source not in edu_by_source:
                    edu_by_source[source] = []
                edu_by_source[source].append(news)
            
            for source_name, news_list in edu_by_source.items():
                md.append(f"### {source_name}\n")
                for news in news_list[:10]:
                    publish_date = ''
                    if news.publish_date:
                        publish_date = news.publish_date.strftime('%Y-%m-%d')
                    elif news.publish_date_str:
                        publish_date = news.publish_date_str[:10] if len(news.publish_date_str) >= 10 else news.publish_date_str
                    
                    md.append(f"**{news.title}**\n")
                    if publish_date:
                        md.append(f"- 日期: {publish_date}\n")
                    if news.summary:
                        md.append(f"- 摘要: {news.summary[:150]}...\n")
                    md.append(f"- 链接: [查看原文]({news.url})\n")
                    md.append("\n")
                md.append("\n")
        
        # 按公众号分组
        account_articles = {}
        for article in articles:
            account_name = article.account.name if article.account else '未知来源'
            if account_name not in account_articles:
                account_articles[account_name] = []
            account_articles[account_name].append(article)
        
        # 重点文章
        important_articles = [a for a in articles if a.is_important]
        if important_articles:
            md.append("\n## 重点文章\n")
            for article in important_articles[:10]:
                md.append(self._format_article(article))
        
        # 按公众号分类
        if account_articles:
            md.append("\n## 公众号动态\n")
            for account_name, account_article_list in account_articles.items():
                md.append(f"### {account_name}\n")
                for article in account_article_list[:5]:
                    md.append(self._format_article(article))
                md.append("\n")
        
        # AI前沿资讯
        if ai_news:
            md.append("\n## AI前沿资讯\n")
            for news in ai_news[:15]:
                md.append(f"### {news.title}\n")
                md.append(f"- 来源: {news.source or '未知'}\n")
                md.append(f"- 时间: {news.publish_date.strftime('%Y-%m-%d') if news.publish_date else '未知'}\n")
                if news.summary:
                    md.append(f"- 摘要: {news.summary[:200]}...\n")
                md.append(f"- 链接: [查看原文]({news.url})\n")
                md.append("\n")
        
        # 投融资动态
        investment_keywords = ['融资', '投资', '收购', '上市', 'IPO', '轮']
        investment_articles = [a for a in articles 
                              if any(kw in a.title for kw in investment_keywords)]
        if investment_articles:
            md.append("\n## 投融资动态\n")
            for article in investment_articles:
                md.append(self._format_article(article))
        
        # 产品动态
        product_keywords = ['发布', '上线', '新品', '产品', '功能', '更新']
        product_articles = [a for a in articles 
                          if any(kw in a.title for kw in product_keywords)]
        if product_articles:
            md.append("\n## 产品动态\n")
            for article in product_articles:
                md.append(self._format_article(article))
        
        # 教育公司财报
        financial_keywords = ['财报', '营收', '利润', '业绩', '收入', '亏损']
        financial_articles = [a for a in articles 
                              if any(kw in a.title for kw in financial_keywords)]
        if financial_articles:
            md.append("\n## 公司财报\n")
            for article in financial_articles:
                md.append(self._format_article(article))
        
        # 页脚
        md.append("\n---\n")
        md.append(f"*本报告由 WiseReporter 自动生成*\n")
        
        return ''.join(md)
    
    def _format_article(self, article: Article) -> str:
        """格式化文章为Markdown"""
        lines = []
        lines.append(f"### {article.title}\n")
        if article.account:
            lines.append(f"- 来源: {article.account.name}\n")
        if article.publish_date:
            lines.append(f"- 时间: {article.publish_date.strftime('%Y-%m-%d')}\n")
        if article.summary:
            lines.append(f"- 摘要: {article.summary[:150]}...\n")
        lines.append(f"- 链接: [查看原文]({article.url})\n")
        lines.append("\n")
        return ''.join(lines)
    
    @staticmethod
    def convert_to_html(content: str) -> str:
        """将Markdown转换为HTML"""
        return markdown.markdown(content, extensions=['extra', 'tables'])
    
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
        today = datetime.utcnow().date()
        start_of_week = today - timedelta(days=today.weekday())  # 周一
        end_of_week = start_of_week + timedelta(days=6)  # 周日
        return (
            datetime.combine(start_of_week, datetime.min.time()),
            datetime.combine(end_of_week, datetime.max.time())
        )

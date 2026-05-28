#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, OfficialAccount, CookiePool, NewsSource, FinanceContent
from werkzeug.security import generate_password_hash
from datetime import datetime

def init_database():
    """初始化数据库"""
    app = create_app()
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("[OK] Database tables created")
        
        # 创建默认账号
        # 超级管理员
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@wisereporter.com',
                password_hash=generate_password_hash('admin123'),
                role='super_admin'
            )
            db.session.add(admin)
            print("[OK] Super admin created (admin/admin123)")
        else:
            # 确保现有admin账号是超级管理员
            existing_admin = User.query.filter_by(username='admin').first()
            if existing_admin and existing_admin.role != 'super_admin':
                existing_admin.role = 'super_admin'
                print("[OK] Upgraded existing admin to super_admin")
        
        # 管理员1
        if not User.query.filter_by(username='admin01').first():
            admin01 = User(
                username='admin01',
                email='admin01@wisereporter.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin01)
            print("[OK] Admin01 created (admin01/admin123)")
        
        # 管理员2
        if not User.query.filter_by(username='admin02').first():
            admin02 = User(
                username='admin02',
                email='admin02@wisereporter.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin02)
            print("[OK] Admin02 created (admin02/admin123)")
        
        # 创建示例公众号
        sample_accounts = [
            {'name': '多鲸资本', 'account_id': 'duojingcapital', 'category': '投融资', 'description': '教育行业投融资资讯'},
            {'name': '芥末堆', 'account_id': 'jiemoedu', 'category': '行业动态', 'description': '教育行业观察'},
            {'name': '黑板洞察', 'account_id': 'heibandongcha', 'category': '行业动态', 'description': '教育行业深度报道'},
            {'name': '睿艺', 'account_id': 'ruiyijk', 'category': '产品动态', 'description': '素质教育资讯'},
            {'name': '教培江湖', 'account_id': 'jiaopeijianghu', 'category': '公司动态', 'description': '教培行业动态'},
        ]
        
        for account_data in sample_accounts:
            if not OfficialAccount.query.filter_by(account_id=account_data['account_id']).first():
                account = OfficialAccount(**account_data)
                db.session.add(account)
        
        print(f"[OK] Sample accounts added ({len(sample_accounts)})")
        
        # 创建示例新闻源
        sample_sources = [
            {'name': 'ai_qianxun', 'url': 'https://aihot.virxact.com/', 'source_type': 'ai_news', 'category': 'AI'},
            {'name': '36kr', 'url': 'https://36kr.com/information/ai/', 'source_type': 'ai_news', 'category': 'AI'},
            {'name': 'jiqizhixin', 'url': 'https://www.jiqizhixin.com/AI-news', 'source_type': 'ai_news', 'category': 'AI'},
            # 教育资讯源
            {'name': 'edu_jiemodui', 'url': 'https://www.jiemodui.com/', 'source_type': 'education', 'category': '教育'},
            {'name': 'edu_duozhi', 'url': 'https://www.duozhi.com/', 'source_type': 'education', 'category': '教育'},
            # 投融资源
            {'name': 'pedaily', 'url': 'https://news.pedaily.cn/', 'source_type': 'finance', 'category': '投融资'},
            {'name': 'leinews', 'url': 'https://www.leinews.com/', 'source_type': 'finance', 'category': '投融资'},
        ]
        
        for source_data in sample_sources:
            if not NewsSource.query.filter_by(name=source_data['name']).first():
                source = NewsSource(**source_data)
                db.session.add(source)
        
        print(f"[OK] Sample news sources added ({len(sample_sources)})")
        
        # 创建示例Cookie（占位符）
        if CookiePool.query.count() == 0:
            placeholder_cookie = CookiePool(
                name='placeholder',
                cookie_data='{}',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                is_available=False
            )
            db.session.add(placeholder_cookie)
            print("[WARNING] Please add real WeChat cookies in Cookie Pool")
        
        db.session.commit()
        print("\n[OK] Database initialization complete!")
        print("\n=== 账号信息 ===")
        print("超级管理员: admin / admin123 (可管理所有权限)")
        print("管理员1:    admin01 / admin123 (除权限管理外的全功能)")
        print("管理员2:    admin02 / admin123 (除权限管理外的全功能)")
        print("\n普通用户请由超级管理员在「权限管理」页面创建。")
        print("访问地址: http://localhost:5000/auth/login")

if __name__ == '__main__':
    init_database()

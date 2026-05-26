#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
迁移：为 User 表添加 role 和 permissions 字段
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
import sqlite3

def migrate():
    app = create_app()
    
    with app.app_context():
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            # SQLite relative path — Flask-SQLAlchemy stores in instance/ folder
            db_path = os.path.join(app.instance_path, db_path)
        
        print(f"[INFO] Database path: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查现有列
        cursor.execute("PRAGMA table_info(user)")
        columns = {col[1] for col in cursor.fetchall()}
        
        if 'role' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
            print("[OK] Added 'role' column to user table")
        else:
            print("[SKIP] 'role' column already exists")
        
        if 'permissions' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN permissions TEXT DEFAULT '[]'")
            print("[OK] Added 'permissions' column to user table")
        else:
            print("[SKIP] 'permissions' column already exists")
        
        conn.commit()
        
        # 升级现有 admin 用户为超级管理员
        cursor.execute("UPDATE user SET role = 'super_admin' WHERE username = 'admin' AND (role IS NULL OR role = 'user' OR role = '')")
        if cursor.rowcount > 0:
            print(f"[OK] Upgraded admin to super_admin")
        
        conn.commit()
        conn.close()
        
        print("\n[OK] Migration complete!")

if __name__ == '__main__':
    migrate()

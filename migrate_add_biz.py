# -*- coding: utf-8 -*-
"""数据库迁移脚本 - 添加biz列"""
import sys
sys.path.insert(0, '.')

from app import create_app, db

def migrate():
    app = create_app()
    with app.app_context():
        # 检查 official_account 表是否有 biz 列
        try:
            result = db.session.execute(db.text('SELECT biz FROM official_account LIMIT 1'))
            print('biz 列已存在')
        except Exception:
            print('正在添加 biz 列...')
            try:
                db.session.execute(db.text('ALTER TABLE official_account ADD COLUMN biz VARCHAR(100)'))
                db.session.commit()
                print('biz 列添加成功')
            except Exception as e:
                print(f'添加 biz 列失败: {e}')
                db.session.rollback()

        # 创建 WechatCredential 表
        try:
            db.create_all()
            print('数据库表已同步')
        except Exception as e:
            print(f'同步数据库表: {e}')

        print('迁移完成!')

if __name__ == '__main__':
    migrate()

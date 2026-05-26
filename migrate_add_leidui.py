"""
迁移脚本：添加雷递网内容表
"""
from app import create_app
from models import db, LeiduiContent

def migrate():
    app = create_app()
    with app.app_context():
        # 创建表
        db.create_all()
        print("LeiduiContent 表创建成功！")

if __name__ == '__main__':
    migrate()

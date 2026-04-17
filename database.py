"""
データベース初期化
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """テーブル作成"""
    from models import User, Seminar, Attendance, Purchase, Material, Video
    with app.app_context():
        db.create_all()

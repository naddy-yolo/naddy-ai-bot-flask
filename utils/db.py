from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 環境変数からPostgreSQL接続URL取得
DATABASE_URL = os.environ.get("POSTGRES_URL")

# エンジン・セッション初期化
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# ベースクラス定義
Base = declarative_base()

# テーブル定義
class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    message = Column(Text)
    timestamp = Column(String)
    request_type = Column(String)
    status = Column(String, default="未返信")
    advice_text = Column(Text)  # ← 必要に応じて追加済み想定

# テーブル初期化関数
def init_db():
    Base.metadata.create_all(bind=engine)

# データ保存
def save_request(data: dict):
    session = SessionLocal()
    try:
        request = Request(
            user_id=data.get("user_id"),
            message=data.get("message"),
            timestamp=data.get("timestamp"),
            request_type=data.get("request_type"),
            status=data.get("status", "未返信")
        )
        session.add(request)
        session.commit()
    finally:
        session.close()

# 🔍 未返信リクエストを取得
def get_unreplied_requests():
    """
    status = '未返信' かつ advice_text がNULLのリクエストを全件取得
    """
    session = SessionLocal()
    try:
        return session.query(Request)\
            .filter(Request.status == "未返信")\
            .filter(Request.advice_text == None)\
            .all()
    finally:
        session.close()

# ✅ アドバイス文をDBに保存
def update_advice_text(user_id: str, timestamp: str, advice_text: str):
    """
    指定ユーザー＆日時のリクエストに advice_text を追記（PostgreSQL更新）
    """
    session = SessionLocal()
    try:
        request = session.query(Request)\
            .filter(Request.user_id == user_id)\
            .filter(Request.timestamp == timestamp)\
            .first()
        if request:
            request.advice_text = advice_text
            session.commit()
            print(f"✅ advice_text 更新完了: {user_id} @ {timestamp}")
        else:
            print("⚠️ 該当レコードが見つかりませんでした")
    finally:
        session.close()

from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

# 環境変数からPostgreSQL接続URL取得
DATABASE_URL = os.environ.get("POSTGRES_URL")

# エンジン・セッション初期化
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# ベースクラス定義
Base = declarative_base()

# =========================
# リクエストテーブル定義
# =========================
class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    message = Column(Text)
    timestamp = Column(String)
    request_type = Column(String)
    status = Column(String, default="未返信")
    advice_text = Column(Text)  # アドバイス文（任意）


# =========================
# トークンテーブル定義
# =========================
class Token(Base):
    __tablename__ = "tokens"

    user_id = Column(String, primary_key=True)           # LINEユーザーIDなど
    access_token = Column(Text, nullable=False)          # Calomeal APIアクセストークン
    refresh_token = Column(Text, nullable=False)         # Calomeal APIリフレッシュトークン
    expires_at = Column(TIMESTAMP, nullable=False)       # アクセストークンの有効期限


# =========================
# テーブル初期化関数
# =========================
def init_db():
    Base.metadata.create_all(bind=engine)


# =========================
# requests テーブル用関数
# =========================
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


def get_unreplied_requests():
    """status='未返信' かつ advice_text がNULLのリクエストを全件取得"""
    session = SessionLocal()
    try:
        return session.query(Request)\
            .filter(Request.status == "未返信")\
            .filter(Request.advice_text == None)\
            .all()
    finally:
        session.close()


def update_advice_text(user_id: str, timestamp: str, advice_text: str):
    """指定ユーザー＆日時のリクエストに advice_text を追記"""
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


# =========================
# tokens テーブル用関数
# =========================
def get_tokens(user_id: str):
    """指定ユーザーのトークン情報を取得"""
    session = SessionLocal()
    try:
        return session.query(Token).filter(Token.user_id == user_id).first()
    finally:
        session.close()


def save_tokens(user_id: str, access_token: str, refresh_token: str, expires_at: datetime):
    """新規ユーザーのトークンを保存（存在しなければ追加）"""
    session = SessionLocal()
    try:
        token = Token(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        session.add(token)
        session.commit()
    finally:
        session.close()


def update_tokens(user_id: str, access_token: str, refresh_token: str, expires_at: datetime):
    """既存ユーザーのトークンを更新"""
    session = SessionLocal()
    try:
        token = session.query(Token).filter(Token.user_id == user_id).first()
        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
            session.commit()
        else:
            # 存在しない場合は新規作成
            save_tokens(user_id, access_token, refresh_token, expires_at)
    finally:
        session.close()

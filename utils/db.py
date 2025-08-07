from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# ✅ POSTGRES_URL に統一して読み込む
from utils.env_utils import POSTGRES_URL

# ✅ SQLAlchemy エンジン・セッション初期化
engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# =========================
# requests テーブル定義
# =========================
class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    message = Column(Text)
    timestamp = Column(String)
    request_type = Column(String)
    status = Column(String, default="未返信")
    advice_text = Column(Text)

# =========================
# tokens テーブル定義
# =========================
class Token(Base):
    __tablename__ = "tokens"

    user_id = Column(String, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)

# =========================
# 初期化関数
# =========================
def init_db():
    Base.metadata.create_all(bind=engine)

# =========================
# requests 関連関数
# =========================
def save_request(data: dict) -> int:
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
        session.refresh(request)
        return request.id
    finally:
        session.close()

def get_unreplied_requests():
    session = SessionLocal()
    try:
        return session.query(Request)\
            .filter(Request.status == "未返信")\
            .filter(Request.advice_text == None)\
            .all()
    finally:
        session.close()

def update_advice_text(user_id: str, timestamp: str, advice_text: str):
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

def update_request_with_advice(request_id: int, advice_text: str, status: str = "未返信"):
    session = SessionLocal()
    try:
        request = session.query(Request).filter(Request.id == request_id).first()
        if request:
            request.advice_text = advice_text
            request.status = status
            session.commit()
            print(f"✅ Request更新完了: id={request_id}, status={status}")
        else:
            print(f"⚠️ 該当リクエストが見つかりませんでした: id={request_id}")
    finally:
        session.close()

# =========================
# tokens 関連関数
# =========================
def get_tokens(user_id: str):
    session = SessionLocal()
    try:
        return session.query(Token).filter(Token.user_id == user_id).first()
    finally:
        session.close()

def save_tokens(user_id: str, access_token: str, refresh_token: str, expires_at: datetime):
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
    session = SessionLocal()
    try:
        token = session.query(Token).filter(Token.user_id == user_id).first()
        if token:
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
            session.commit()
        else:
            save_tokens(user_id, access_token, refresh_token, expires_at)
    finally:
        session.close()

# utils/db.py
from datetime import datetime, timezone, date
from typing import List, Dict, Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy import Date, Numeric
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import func, or_, ARRAY

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
# user_profile モデル
# =========================
class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id      = Column(String(64), primary_key=True)
    name         = Column(Text, nullable=False)
    photo_url    = Column(Text, nullable=True)
    last_contact = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at   = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    goals_json   = Column(JSONB, nullable=True)
    tags         = Column(ARRAY(Text), nullable=True)  # ← DBの text[] に合わせる

# =========================
# 日次体組成
# =========================
class UserMetricsDaily(Base):
    __tablename__ = "user_metrics_daily"

    user_id     = Column(String(64), primary_key=True)
    date        = Column(Date, primary_key=True)
    weight_kg   = Column(Numeric(5, 2))
    body_fat_pc = Column(Numeric(5, 2))
    created_at  = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

# =========================
# 日次栄養
# =========================
class UserNutritionDaily(Base):
    __tablename__ = "user_nutrition_daily"

    user_id       = Column(String(64), primary_key=True)
    date          = Column(Date, primary_key=True)
    calorie_kcal  = Column(Numeric(7, 1))
    protein_g     = Column(Numeric(6, 1))
    fat_g         = Column(Numeric(6, 1))
    carb_g        = Column(Numeric(6, 1))
    created_at    = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

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
        return (
            session.query(Request)
            .filter(Request.status == "未返信")
            .filter(Request.advice_text == None)
            .all()
        )
    finally:
        session.close()

def update_advice_text(user_id: str, timestamp: str, advice_text: str):
    session = SessionLocal()
    try:
        request = (
            session.query(Request)
            .filter(Request.user_id == user_id)
            .filter(Request.timestamp == timestamp)
            .first()
        )
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

# -------------------------
# ユーザーマスター UPSERT
# -------------------------
def ensure_user_profile(
    user_id: str,
    name: Optional[str] = None,
    photo_url: Optional[str] = None,
    last_contact: Optional[datetime] = None,
) -> None:
    if not user_id:
        return
    now = datetime.now(timezone.utc)
    lc = last_contact or now

    session = SessionLocal()
    try:
        stmt = pg_insert(UserProfile).values(
            user_id=user_id,
            name=name or user_id,
            photo_url=photo_url,
            last_contact=lc,
            created_at=now,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=[UserProfile.user_id],
            set_={
                "name": (name if name else UserProfile.name),
                "photo_url": (photo_url if photo_url is not None else UserProfile.photo_url),
                "last_contact": lc,
                "updated_at": now,
            }
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()

# -------------------------
# 日次体組成 UPSERT
# -------------------------
def upsert_metrics_daily(user_id: str, d: date, weight_kg: Optional[float], body_fat_pc: Optional[float]) -> None:
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(UserMetricsDaily).values(
            user_id=user_id, date=d,
            weight_kg=weight_kg, body_fat_pc=body_fat_pc,
            created_at=now, updated_at=now
        ).on_conflict_do_update(
            index_elements=[UserMetricsDaily.user_id, UserMetricsDaily.date],
            set_={"weight_kg": weight_kg, "body_fat_pc": body_fat_pc, "updated_at": now}
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()

# -------------------------
# 日次栄養 UPSERT
# -------------------------
def upsert_nutrition_daily(
    user_id: str, d: date,
    calorie_kcal: Optional[float], protein_g: Optional[float], fat_g: Optional[float], carb_g: Optional[float]
) -> None:
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(UserNutritionDaily).values(
            user_id=user_id, date=d,
            calorie_kcal=calorie_kcal, protein_g=protein_g, fat_g=fat_g, carb_g=carb_g,
            created_at=now, updated_at=now
        ).on_conflict_do_update(
            index_elements=[UserNutritionDaily.user_id, UserNutritionDaily.date],
            set_={
                "calorie_kcal": calorie_kcal, "protein_g": protein_g,
                "fat_g": fat_g, "carb_g": carb_g, "updated_at": now
            }
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()

# -------------------------
# /users 用 検索（部分一致・小文字無視）
# -------------------------
def search_users(q: str, limit: int = 20, offset: int = 0) -> List[Dict]:
    session = SessionLocal()
    try:
        _q = (q or "").strip()
        qry = session.query(UserProfile.user_id, UserProfile.name, UserProfile.photo_url, UserProfile.last_contact)
        if _q:
            like = f"%{_q}%"
            qry = qry.filter(
                or_(
                    func.lower(UserProfile.name).like(func.lower(like)),
                    func.lower(UserProfile.user_id).like(func.lower(like)),
                )
            )
        rows = qry.order_by(UserProfile.name.asc()).limit(limit).offset(offset).all()
        return [
            {
                "user_id": r.user_id,
                "name": r.name,
                "photo_url": r.photo_url,
                "last_contact": r.last_contact.isoformat() if r.last_contact else None
            } for r in rows
        ]
    finally:
        session.close()

# -------------------------
# 1件取得（プロフィール）
# -------------------------
def get_user_profile_one(user_id: str) -> Optional[Dict]:
    session = SessionLocal()
    try:
        r = session.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not r:
            return None
        return {
            "user_id": r.user_id,
            "name": r.name,
            "photo_url": r.photo_url,
            "last_contact": r.last_contact.isoformat() if r.last_contact else None,
            "goals_json": r.goals_json,
            "tags": r.tags,
        }
    finally:
        session.close()

# -------------------------
# 期間取得（体重）
# -------------------------
def get_user_weights(user_id: str, start: date, end: date) -> List[Dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(UserMetricsDaily)
            .filter(UserMetricsDaily.user_id == user_id)
            .filter(UserMetricsDaily.date >= start)
            .filter(UserMetricsDaily.date <= end)
            .order_by(UserMetricsDaily.date.asc())
            .all()
        )
        return [
            {
                "date": r.date.isoformat(),
                "weight_kg": float(r.weight_kg) if r.weight_kg is not None else None,
                "body_fat_pc": float(r.body_fat_pc) if r.body_fat_pc is not None else None,
            }
            for r in rows
        ]
    finally:
        session.close()

# -------------------------
# 期間取得（栄養）
# -------------------------
def get_user_intake(user_id: str, start: date, end: date) -> List[Dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(UserNutritionDaily)
            .filter(UserNutritionDaily.user_id == user_id)
            .filter(UserNutritionDaily.date >= start)
            .filter(UserNutritionDaily.date <= end)
            .order_by(UserNutritionDaily.date.asc())
            .all()
        )
        to_float = lambda x: float(x) if x is not None else None
        return [
            {
                "date": r.date.isoformat(),
                "calorie_kcal": to_float(r.calorie_kcal),
                "protein_g": to_float(r.protein_g),
                "fat_g": to_float(r.fat_g),
                "carb_g": to_float(r.carb_g),
            }
            for r in rows
        ]
    finally:
        session.close()

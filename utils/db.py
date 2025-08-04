# utils/db.py

import sqlite3
from pathlib import Path

DB_PATH = "requests.db"

def init_db():
    """SQLite データベースとテーブルを初期化する"""
    Path(DB_PATH).touch(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            message TEXT,
            timestamp TEXT,
            request_type TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_request(data: dict):
    """受信リクエストを SQLite に保存する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    data.setdefault("status", "未返信")

    cursor.execute("""
        INSERT INTO requests (user_id, message, timestamp, request_type, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("user_id"),
        data.get("message"),
        data.get("timestamp"),
        data.get("request_type"),
        data.get("status")
    ))

    conn.commit()
    conn.close()

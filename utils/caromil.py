# utils/caromil.py

import requests
from datetime import datetime, timedelta
from dateutil import parser  # pip install python-dateutil

from utils.db import get_tokens, update_tokens
from utils.env_utils import CALOMEAL_CLIENT_ID, CALOMEAL_CLIENT_SECRET

# カロミルAPIエンドポイント
TOKEN_URL = "https://test-connect.calomeal.com/auth/accesstoken"
ANTHRO_URL = "https://test-connect.calomeal.com/api/anthropometric"
MEAL_BASIS_URL = "https://test-connect.calomeal.com/api/meal_with_basis"
USER_INFO_URL = "https://test-connect.calomeal.com/api/user_info"


def to_slash_date(date_str: str) -> str:
    """YYYY-MM-DD → YYYY/MM/DD に変換（Calomeal要件）"""
    return date_str.replace("-", "/") if date_str and "-" in date_str else date_str


def get_access_token(user_id: str) -> str:
    """DBから有効なアクセストークンを取得（期限切れならrefresh_tokenで更新）"""
    token_data = get_tokens(user_id)
    if not token_data:
        raise RuntimeError(f"ユーザー {user_id} のトークンがDBに存在しません")

    expires_at = token_data.expires_at
    if isinstance(expires_at, str):
        expires_at = parser.parse(expires_at)

    # 期限-1分を切っていたら更新
    if datetime.utcnow() < (expires_at - timedelta(minutes=1)):
        return token_data.access_token

    # refresh_tokenで更新
    data = {
        "grant_type": "refresh_token",
        "client_id": CALOMEAL_CLIENT_ID,
        "client_secret": CALOMEAL_CLIENT_SECRET,
        "refresh_token": token_data.refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    print("🔁 トークンリフレッシュ開始")
    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"トークン更新失敗: {resp.status_code} - {resp.text}")

    tokens = resp.json()
    new_access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token", token_data.refresh_token)
    new_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 86400))

    update_tokens(user_id, new_access_token, new_refresh_token, new_expires_at)
    print("✅ アクセストークン更新成功")
    return new_access_token


def get_anthropometric_data(user_id: str, start_date: str, end_date: str, unit: str = "day"):
    """カロミルAPIから体重・体脂肪データを取得"""
    access_token = get_access_token(user_id)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Bearer {access_token}"
    }
    data = {
        "start_date": to_slash_date(start_date),
        "end_date": to_slash_date(end_date),
        "unit": unit
    }

    print("📤 anthropometric 送信:", data)
    resp = requests.post(ANTHRO_URL, headers=headers, data=data, timeout=30)

    if resp.status_code == 200:
        print("✅ anthropometric 取得成功")
        return resp.json()
    if resp.status_code == 401:
        print("⚠️ トークン期限切れ。再取得して再試行")
        access_token = get_access_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        retry = requests.post(ANTHRO_URL, headers=headers, data=data, timeout=30)
        if retry.status_code == 200:
            print("✅ 再試行成功")
            return retry.json()
        raise RuntimeError(f"anthropometric retry failed: {retry.status_code} - {retry.text}")
    raise RuntimeError(f"anthropometric error: {resp.status_code} - {resp.text}")


def get_meal_with_basis(user_id: str, start_date: str, end_date: str):
    """カロミルAPIからPFC・カロリー等（日別合計）を取得"""
    access_token = get_access_token(user_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "start_date": to_slash_date(start_date),
        "end_date": to_slash_date(end_date)
    }

    print("📤 meal_with_basis 送信:", data)
    resp = requests.post(MEAL_BASIS_URL, headers=headers, data=data, timeout=30)

    if resp.status_code == 200:
        print("✅ meal_with_basis 取得成功")
        return resp.json()
    if resp.status_code == 401:
        print("⚠️ トークン期限切れ。再取得して再試行")
        access_token = get_access_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        retry = requests.post(MEAL_BASIS_URL, headers=headers, data=data, timeout=30)
        if retry.status_code == 200:
            print("✅ 再試行成功")
            return retry.json()
        raise RuntimeError(f"meal_with_basis retry failed: {retry.status_code} - {retry.text}")
    raise RuntimeError(f"meal_with_basis error: {resp.status_code} - {resp.text}")


def get_user_info(user_id: str) -> dict:
    """Calomealのユーザー情報（現在の目標を含む）を取得"""
    access_token = get_access_token(user_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(USER_INFO_URL, headers=headers, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 401:
        # リフレッシュして1回だけ再試行
        access_token = get_access_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        retry = requests.post(USER_INFO_URL, headers=headers, timeout=30)
        if retry.status_code == 200:
            return retry.json()
        raise RuntimeError(f"user_info retry failed: {retry.status_code} - {retry.text}")
    raise RuntimeError(f"user_info error: {resp.status_code} - {resp.text}")

# utils/caromil.py

import json
import requests
from datetime import datetime, timedelta, date as date_cls
from dateutil import parser  # pip install python-dateutil

from utils.db import (
    get_tokens, update_tokens,
    upsert_nutrition_daily,
)
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
    """カロミルAPIからPFC・カロリー等（breakdown含む）を取得"""
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


# ============================================================
# ここから：breakdown 抽出＆保存ユーティリティ
# ============================================================

def _to_float(x):
    try:
        if x in (None, "", "-"):
            return None
        return float(x)
    except Exception:
        return None

def _pick(lst_json: dict) -> list:
    """Calomeal/テストエンドポイント双方の形式差を吸収して配列を取り出す"""
    # 例1: {"meal_with_basis": [ {...}, ... ]}
    if isinstance(lst_json, dict) and "meal_with_basis" in lst_json:
        return lst_json.get("meal_with_basis") or []
    # 例2: {"result": {"meal_with_basis": [ {...} ]}}
    if isinstance(lst_json, dict) and "result" in lst_json:
        res = lst_json.get("result") or {}
        return res.get("meal_with_basis") or []
    # その他
    return []

def _extract_breakdown(day_obj: dict) -> dict | None:
    """
    Calomealの1日分オブジェクトから「朝/昼/夜/間食」のカロリー・PFC内訳を抽出。
    優先: meal_histories_summary → 無ければ basis.meal_histories_summary
    ※欠損は None
    """
    src = day_obj.get("meal_histories_summary") \
          or (day_obj.get("basis", {}) or {}).get("meal_histories_summary")

    if not isinstance(src, dict):
        return None

    slots = ["morning", "noon", "snack", "night"]
    keys  = ["calorie", "protein", "fat", "carb"]
    out = {}
    for s in slots:
        if s in src and isinstance(src[s], dict):
            out[s] = {k: _to_float(src[s].get(k)) for k in keys}
    return out or None

def _extract_totals(day_obj: dict, breakdown: dict | None) -> dict:
    """
    1日分の合計（kcal/P/F/C）を返す。
    1) day_obj に total系があればそれを採用
    2) なければ breakdown の合計で算出
    3) どちらも無ければ None
    """
    # パターンA: day_obj 内に "total" 風がある場合（保険）
    possible_total_keys = [
        ("calorie_kcal", "protein_g", "fat_g", "carb_g"),
        ("calorie", "protein", "fat", "carb"),
        ("kcal", "p", "f", "c"),
    ]
    for tkeys in possible_total_keys:
        a, p, f, c = tkeys
        if all(k in day_obj for k in tkeys):
            return {
                "calorie_kcal": _to_float(day_obj.get(a)),
                "protein_g": _to_float(day_obj.get(p)),
                "fat_g": _to_float(day_obj.get(f)),
                "carb_g": _to_float(day_obj.get(c)),
            }

    # パターンB: breakdown 合計で算出
    if breakdown:
        slots = ["morning", "noon", "snack", "night"]
        total = {"calorie_kcal": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carb_g": 0.0}
        any_val = False
        for s in slots:
            v = breakdown.get(s) or {}
            if v:
                any_val = True
            if isinstance(v.get("calorie"), (int, float)):
                total["calorie_kcal"] += float(v["calorie"])
            if isinstance(v.get("protein"), (int, float)):
                total["protein_g"]   += float(v["protein"])
            if isinstance(v.get("fat"), (int, float)):
                total["fat_g"]       += float(v["fat"])
            if isinstance(v.get("carb"), (int, float)):
                total["carb_g"]      += float(v["carb"])

        if any_val:
            # 1桁小数で丸め（DB型に合わせて見栄え）
            for k in total:
                total[k] = round(total[k], 1)
            return total

    # パターンC: 何も取れない
    return {
        "calorie_kcal": None,
        "protein_g": None,
        "fat_g": None,
        "carb_g": None,
    }

def _parse_date(dstr: str) -> date_cls | None:
    """Calomealは 'YYYY/MM/DD' 想定。安全に date へ"""
    if not dstr:
        return None
    try:
        # "2025/08/08" or "2025-08-08"
        dstr = dstr.replace("-", "/")
        return parser.parse(dstr).date()
    except Exception:
        return None

def save_intake_breakdown(user_id: str, start_date: str, end_date: str) -> dict:
    """
    Calomeal meal_with_basis を取得し、日合計＋meals_breakdown を user_nutrition_daily に保存する。
    返り値: {"written": n, "empty": m}
    """
    payload = get_meal_with_basis(user_id, start_date, end_date)
    days = _pick(payload)
    if not days:
        return {"written": 0, "empty": 0}

    written, empty = 0, 0
    for day_obj in days:
        d = _parse_date(day_obj.get("date") or day_obj.get("day") or day_obj.get("dt"))
        if not d:
            empty += 1
            continue

        breakdown = _extract_breakdown(day_obj)
        totals = _extract_totals(day_obj, breakdown)

        upsert_nutrition_daily(
            user_id=user_id,
            d=d,
            calorie_kcal=totals.get("calorie_kcal"),
            protein_g=totals.get("protein_g"),
            fat_g=totals.get("fat_g"),
            carb_g=totals.get("carb_g"),
            meals_breakdown=breakdown  # ★ JSONB で保存
        )
        written += 1

    return {"written": written, "empty": empty}

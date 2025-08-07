import requests
from datetime import datetime, timedelta
from dateutil import parser  # pip install python-dateutil
import pytz  # pip install pytz

from utils.db import get_tokens, update_tokens
from utils.env_utils import CALOMEAL_CLIENT_ID, CALOMEAL_CLIENT_SECRET

# カロミルAPIエンドポイント
TOKEN_URL = "https://test-connect.calomeal.com/auth/accesstoken"
ANTHRO_URL = "https://test-connect.calomeal.com/api/anthropometric"
MEAL_BASIS_URL = "https://test-connect.calomeal.com/api/meal_with_basis"


def to_slash_date(date_str: str) -> str:
    return date_str.replace("-", "/") if "-" in date_str else date_str


def get_access_token(user_id: str) -> str:
    token_data = get_tokens(user_id)
    if not token_data:
        raise ValueError(f"❌ ユーザー {user_id} のトークンがDBに存在しません")

    expires_at = token_data.expires_at
    if isinstance(expires_at, str):
        expires_at = parser.parse(expires_at)

    if datetime.utcnow() < (expires_at - timedelta(minutes=1)):
        return token_data.access_token

    data = {
        "grant_type": "refresh_token",
        "client_id": CALOMEAL_CLIENT_ID,
        "client_secret": CALOMEAL_CLIENT_SECRET,
        "refresh_token": token_data.refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    print("🔁 トークンリフレッシュ開始")
    response = requests.post(TOKEN_URL, headers=headers, data=data)
    if response.status_code != 200:
        raise RuntimeError(f"❌ トークン更新失敗: {response.status_code} - {response.text}")

    tokens = response.json()
    new_access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token", token_data.refresh_token)
    new_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 86400))

    update_tokens(user_id, new_access_token, new_refresh_token, new_expires_at)
    print("✅ アクセストークン更新成功")
    return new_access_token


def get_anthropometric_data(user_id: str, start_date: str, end_date: str, unit: str = "day"):
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

    print("📤 カロミルAPIへ送信するdata:", data)
    response = requests.post(ANTHRO_URL, headers=headers, data=data)

    if response.status_code == 200:
        print("✅ データ取得成功")
        return response.json()
    elif response.status_code == 401:
        print("⚠️ トークン期限切れ。更新を試みます")
        access_token = get_access_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        retry_response = requests.post(ANTHRO_URL, headers=headers, data=data)
        if retry_response.status_code == 200:
            print("✅ トークン更新後の再取得成功")
            return retry_response.json()
        else:
            raise Exception(f"再試行失敗: {retry_response.status_code} - {retry_response.text}")
    else:
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")


def get_meal_with_basis(user_id: str, start_date: str, end_date: str):
    access_token = get_access_token(user_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "start_date": to_slash_date(start_date),
        "end_date": to_slash_date(end_date)
    }

    print("📤 meal_with_basis APIへ送信:", data)
    response = requests.post(MEAL_BASIS_URL, headers=headers, data=data)

    if response.status_code == 200:
        print("✅ meal_with_basis データ取得成功")
        full_data = response.json()

        # meal_with_basisのうち、最初の1日分のみ使用
        meal_list = full_data.get("result", [])
        if not meal_list:
            raise ValueError("❌ meal_with_basis に日別データが含まれていません")

        meal = meal_list[0]  # 最初の1日分を使用
        actual = meal.get("meal_histories_summary", {}).get("all", {})
        target = meal.get("basis", {}).get("all", {})

        # PFCとカロリーだけ抽出
        keys = ["calorie", "protein", "lipid", "carbohydrate"]
        actual_clean = {k: actual.get(k) for k in keys}
        target_clean = {k: target.get(k) for k in keys}

        return {
            "date": meal.get("date"),
            "actual": actual_clean,
            "target": target_clean
        }

    elif response.status_code == 401:
        print("⚠️ アクセストークン期限切れ、更新します")
        access_token = get_access_token(user_id)
        headers["Authorization"] = f"Bearer {access_token}"
        retry_response = requests.post(MEAL_BASIS_URL, headers=headers, data=data)
        if retry_response.status_code == 200:
            print("✅ トークン更新後の再取得成功")
            return retry_response.json()
        else:
            raise Exception(f"再試行失敗: {retry_response.status_code} - {retry_response.text}")
    else:
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")

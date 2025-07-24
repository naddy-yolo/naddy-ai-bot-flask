import os
import requests
from dotenv import load_dotenv

# ローカル用（Renderでは不要）
load_dotenv()

def refresh_access_token():
    """
    refresh_token を使用して新しい access_token を取得
    """
    url = "https://test-connect.calomeal.com/auth/accesstoken"
    data = {
        "grant_type": "refresh_token",
        "client_id": os.getenv("CAROMIL_CLIENT_ID"),
        "client_secret": os.getenv("CAROMIL_CLIENT_SECRET"),
        "refresh_token": os.getenv("CAROMIL_REFRESH_TOKEN"),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    print("🔁 トークンリフレッシュ開始")
    print("🔐 client_id:", os.getenv("CAROMIL_CLIENT_ID"))
    print("🔐 client_secret:", os.getenv("CAROMIL_CLIENT_SECRET")[:6], "...")
    print("🔐 refresh_token:", os.getenv("CAROMIL_REFRESH_TOKEN")[:12], "...")

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        tokens = response.json()
        access_token = tokens.get("access_token")
        print("✅ アクセストークン更新成功")
        os.environ["CAROMIL_ACCESS_TOKEN"] = access_token
        return access_token
    else:
        print("❌ トークン更新失敗:", response.status_code, response.text)
        raise Exception(f"トークンの更新に失敗しました: {response.status_code} - {response.text}")


def get_anthropometric_data(access_token: str, start_date: str, end_date: str, unit: str = "day"):
    """
    カロミルAPIから体重・体脂肪データを取得
    ※ Calomeal APIは start_date, end_date を YYYY/MM/DD 形式で送る必要あり
    """
    url = "https://test-connect.calomeal.com/api/anthropometric"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    body = {
        "start_date": start_date,
        "end_date": end_date,
        "unit": unit
    }

    print("📤 カロミルAPIへ送信するbody:", body)

    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        print("✅ データ取得成功")
        return response.json().get("result")
    elif response.status_code == 401:
        print("⚠️ トークン期限切れ。更新を試みます")
        new_token = refresh_access_token()
        headers["Authorization"] = f"Bearer {new_token}"
        retry_response = requests.post(url, headers=headers, json=body)
        if retry_response.status_code == 200:
            print("✅ トークン更新後の再取得成功")
            return retry_response.json().get("result")
        else:
            raise Exception(f"再試行失敗: {retry_response.status_code} - {retry_response.text}")
    else:
        print("❌ APIエラー:", response.status_code, response.text)
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")

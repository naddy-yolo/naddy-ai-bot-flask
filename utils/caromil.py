import os
import requests
from dotenv import load_dotenv

# ローカル環境用
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


def get_anthropometric_data_v2(access_token: str, start_date: str, end_date: str):
    """
    /api/v2/anthropometric エンドポイントで体重データ取得（GET形式）
    """
    url = "https://test-connect.calomeal.com/api/v2/anthropometric"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "from": start_date,
        "to": end_date
    }

    print("📤 GET送信先:", url)
    print("📅 パラメータ:", params)

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        print("✅ データ取得成功")
        return response.json()
    elif response.status_code == 401:
        print("⚠️ トークン無効 → リフレッシュを試みます")
        new_token = refresh_access_token()
        headers["Authorization"] = f"Bearer {new_token}"
        retry_response = requests.get(url, headers=headers, params=params)
        if retry_response.status_code == 200:
            return retry_response.json()
        else:
            raise Exception(f"再試行失敗: {retry_response.status_code} - {retry_response.text}")
    else:
        raise Exception(f"APIエラー: {response.status_code} - {res_

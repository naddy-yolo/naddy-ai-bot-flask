import os
import requests
from dotenv import load_dotenv

# .env を読み込む（ローカル実行時のみ必要）
load_dotenv()

def refresh_access_token():
    """
    refresh_token を使用して新しい access_token を取得
    """
    url = "https://connect.calomeal.com/auth/accesstoken"
    data = {
        "grant_type": "refresh_token",
        "client_id": os.getenv("CAROMIL_CLIENT_ID"),
        "client_secret": os.getenv("CAROMIL_CLIENT_SECRET"),
        "refresh_token": os.getenv("CAROMIL_REFRESH_TOKEN"),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        tokens = response.json()
        print("✅ アクセストークンを更新しました")
        # 一時的に環境変数を上書き（必要に応じて保存処理に変更可）
        os.environ["CAROMIL_ACCESS_TOKEN"] = tokens.get("access_token")
        return tokens.get("access_token")
    else:
        raise Exception(f"トークンの更新に失敗しました: {response.status_code} - {response.text}")


def get_anthropometric_data(access_token: str, start_date: str, end_date: str):
    """
    カロミルAPIから体重・体脂肪データを取得。
    トークンが期限切れの場合は自動でリフレッシュして再試行。
    """
    url = "https://connect.calomeal.com/api/anthropometric"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    body = {
        "start_date": start_date,
        "end_date": end_date,
        "unit": "day"
    }

    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        return response.json()["result"]
    elif response.status_code == 401:
        print("⚠️ アクセストークンが無効です。再取得を試みます...")
        new_token = refresh_access_token()
        headers["Authorization"] = f"Bearer {new_token}"
        retry_response = requests.post(url, headers=headers, json=body)
        if retry_response.status_code == 200:
            return retry_response.json()["result"]
        else:
            raise Exception(f"再試行でもエラー: {retry_response.status_code} - {retry_response.text}")
    else:
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")

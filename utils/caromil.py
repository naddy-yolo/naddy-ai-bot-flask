import requests
import os

def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    url = "https://connect.calomeal.com/auth/accesstoken"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"トークンリフレッシュ失敗: {response.status_code} - {response.text}")

def get_anthropometric_data(access_token: str, start_date: str, end_date: str):
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
        print("🔄 アクセストークン期限切れ。リフレッシュを実行します...")
        # 環境変数から必要情報取得
        refresh_token = os.getenv("CAROMIL_REFRESH_TOKEN")
        client_id = os.getenv("CAROMIL_CLIENT_ID")
        client_secret = os.getenv("CAROMIL_CLIENT_SECRET")

        tokens = refresh_access_token(refresh_token, client_id, client_secret)
        new_access_token = tokens["access_token"]
        os.environ["CAROMIL_ACCESS_TOKEN"] = new_access_token  # メモリ上で更新

        # 🔁 リトライ
        headers["Authorization"] = f"Bearer {new_access_token}"
        retry = requests.post(url, headers=headers, json=body)

        if retry.status_code == 200:
            return retry.json()["result"]
        else:
            raise Exception(f"リトライ失敗: {retry.status_code} - {retry.text}")
    else:
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")

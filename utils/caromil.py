import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_anthropometric_data(start_date, end_date, unit):
    access_token = os.getenv("CALOMEAL_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("アクセストークンが設定されていません")

    url = "https://public-api.calomeal.com/api/anthropometric"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "unit": unit,
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"APIリクエスト失敗: {response.status_code}, {response.text}")

    return response.json()

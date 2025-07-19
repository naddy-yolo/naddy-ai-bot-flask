import requests
import os

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
    else:
        raise Exception(f"APIエラー: {response.status_code} - {response.text}")

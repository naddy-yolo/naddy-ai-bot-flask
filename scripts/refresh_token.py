import requests
import os
from dotenv import load_dotenv
from utils.env_utils import update_env_variable

# === 📂 .env 読み込み ===
load_dotenv()

# === 🔑 各種情報は .env から取得 ===
client_id = os.getenv("CAROMIL_CLIENT_ID")
client_secret = os.getenv("CAROMIL_CLIENT_SECRET")
refresh_token = os.getenv("CAROMIL_REFRESH_TOKEN")
env_path = ".env"

# === 🔁 トークン再発行エンドポイント ===
url = "https://test-connect.calomeal.com/auth/accesstoken"

# === 🔧 リクエストデータ ===
data = {
    "grant_type": "refresh_token",
    "client_id": client_id,
    "client_secret": client_secret,
    "refresh_token": refresh_token
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# === 🚀 リクエスト送信 ===
response = requests.post(url, headers=headers, data=data)

# === 📦 レスポンス処理 ===
print("ステータスコード:", response.status_code)
try:
    tokens = response.json()
    new_access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token")

    print("✅ 新しいアクセストークン:", new_access_token)
    print("✅ 新しいリフレッシュトークン:", new_refresh_token)

    # === 📝 .env ファイルを更新 ===
    update_env_variable(env_path, "CAROMIL_ACCESS_TOKEN", new_access_token)
    update_env_variable(env_path, "CAROMIL_REFRESH_TOKEN", new_refresh_token)
    print("✅ .envファイルを更新しました")

except Exception as e:
    print("❌ レスポンスがJSON形式ではありません")
    print(response.text)

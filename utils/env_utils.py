import os
from dotenv import load_dotenv

# ✅ .env を読み込む（ローカル開発時に必須）
load_dotenv()

# ✅ 環境変数を取得
POSTGRES_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CALOMEAL_CLIENT_ID = os.getenv("CALOMEAL_CLIENT_ID")
CALOMEAL_CLIENT_SECRET = os.getenv("CALOMEAL_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# ✅ PostgreSQL URLの存在確認
if POSTGRES_URL is None:
    raise ValueError("❌ POSTGRES_URL が環境変数に設定されていません。")

# ✅ 別ファイル用の書き換え関数（必要なら）
def update_env_variable(file_path: str, key: str, new_value: str):
    lines = []
    key_found = False

    with open(file_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={new_value}\n")
                key_found = True
            else:
                lines.append(line)

    if not key_found:
        lines.append(f"{key}={new_value}\n")

    with open(file_path, "w") as f:
        f.writelines(lines)

import os
import json

# 保存先ファイル（プロジェクトルートに作成されます）
DATA_FILE = 'requests.json'

def save_request(data: dict):
    """
    リクエストデータをJSONファイルに追記保存する（配列構造）
    将来的にSQLiteに切り替え可能なように構造を分離しておく
    """
    data['status'] = 'unprocessed'

    # 既存データを読み込み
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = []
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    # 新しいリクエストを追加
    existing_data.append(data)

    # 上書き保存
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

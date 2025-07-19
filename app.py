from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from datetime import date, timedelta
from utils.caromil import get_anthropometric_data

# .envファイル読み込み（ローカル用）
load_dotenv()

app = Flask(__name__)

# 動作確認用ルート
@app.route("/", methods=["GET"])
def index():
    return "✅ ナディ式AI Bot Flask サーバー稼働中", 200

# Webhook受信用ルート
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # JSONを取得
        data = request.get_json(force=True)

        # セキュアログ（user_idのみ）
        user_id = data.get("user_id", "unknown")
        print(f"📩 Webhook受信: user_id={user_id}")

        return jsonify({
            "status": "ok",
            "message": "Webhook受信しました"
        }), 200

    except Exception as e:
        print("❌ エラー:", str(e))
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# テスト用：カロミルの体重・体脂肪データ取得
@app.route("/test-caromil", methods=["GET"])
def test_caromil():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=7)).isoformat()

        result = get_anthropometric_data(access_token, start_date, end_date)

        return jsonify({
            "status": "ok",
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ローカル起動用（Renderでは使われない）
if __name__ == "__main__":
    app.run(debug=True)

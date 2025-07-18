from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv

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
        # force=True でContent-Type判定をスキップしてJSON解析
        data = request.get_json(force=True)

        # セキュアログ出力（user_id のみ）
        user_id = data.get("user_id", "unknown")
        print(f"📩 Webhook受信: user_id={user_id}")

        # 仮レスポンス（後ほどGPTやAPI処理をここに入れる）
        return jsonify({"status": "ok", "message": "Webhook受信しました"}), 200

    except Exception as e:
        # エラーハンドリング
        print("❌ エラー:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

# ローカル開発用サーバー起動（Renderでは無視される）
if __name__ == "__main__":
    app.run(debug=True)

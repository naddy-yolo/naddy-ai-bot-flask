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

        # 受信したJSONをログ出力
        print("📩 Webhook受信データ:", data)

        # 仮レスポンス（後ほどGPTやAPI処理をここに入れる）
        return jsonify({"status": "ok", "message": "Webhook受信しました"}), 200

    except Exception as e:
        # エラーハンドリング
        print("❌ エラー:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

# ローカル開発用サーバー起動
if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, jsonify, request
import os
import requests
from datetime import datetime
from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis
)
from utils.storage import save_request
from utils.gpt_utils import classify_request_type

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask app is running!"

# ✅ 体重・体脂肪データ取得（POST）
@app.route('/test-caromil', methods=["POST"])
def test_caromil():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        if not access_token:
            raise Exception("CAROMIL_ACCESS_TOKEN が設定されていません")

        data = request.get_json(force=True)
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        unit = data.get("unit", "day")

        if not start_date or not end_date:
            raise Exception("start_date, end_date は必須です")

        print(f"📅 Fetching data from {start_date} to {end_date} with unit '{unit}'")

        result = get_anthropometric_data(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            unit=unit
        )

        return jsonify({"status": "ok", "result": result})

    except Exception as e:
        print("❌ Error in /test-caromil:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 400

# ✅ ユーザー基本情報取得（GET）
@app.route("/test-userinfo", methods=["GET"])
def test_userinfo():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        if not access_token:
            raise Exception("CAROMIL_ACCESS_TOKEN が設定されていません")

        url = "https://test-connect.calomeal.com/api/user_info"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            return jsonify({"status": "ok", "result": response.json()})
        else:
            return jsonify({
                "status": "error",
                "message": f"ユーザー情報取得失敗: {response.status_code}",
                "response": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ✅ PFC・カロリー・目標量などを取得（POST）
@app.route('/test-meal-basis', methods=["POST"])
def test_meal_basis():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        if not access_token:
            raise Exception("CAROMIL_ACCESS_TOKEN が設定されていません")

        data = request.get_json(force=True)
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not start_date or not end_date:
            raise Exception("start_date, end_date は必須です")

        print(f"🍽️ meal_with_basis取得: {start_date}〜{end_date}")

        result = get_meal_with_basis(access_token, start_date, end_date)
        return jsonify({"status": "ok", "result": result})

    except Exception as e:
        print("❌ Error in /test-meal-basis:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 400

# ✅ 認証コード受け取り（Calomeal認証用）
@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if code:
        return f"""
        ✅ 認証コードを取得しました！<br>
        <strong>code:</strong> {code}<br>
        <strong>state:</strong> {state or '（未指定）'}
        """
    else:
        return "❌ 認証コード（code）が見つかりませんでした", 400

# ✅ Webhook受信用エンドポイント（Lステップ連携用）
@app.route('/receive-request', methods=["POST"])
def receive_request():
    try:
        data = request.get_json(force=True)
        print("🔍 受信データ:", data)

        event = data.get("events", [{}])[0]
        event_type = event.get("type")

        # 分析依頼以外のイベント（例: unfollow）は無視
        if event_type not in ["message", "postback"]:
            return jsonify({
                "status": "ignored",
                "message": f"イベントタイプ '{event_type}' は対象外のため無視されました"
            }), 200

        # 仮で message_text を固定（postback or message 内容に応じて調整可能）
        message_text = "分析依頼を送信しました"

        timestamp = event.get("timestamp") or datetime.now().timestamp()
        timestamp_str = datetime.fromtimestamp(timestamp / 1000).isoformat()
        request_type = classify_request_type(message_text)

        request_data = {
            "message_text": message_text,
            "timestamp": timestamp_str,
            "user_id": event.get("source", {}).get("userId"),
            "request_type": request_type
        }

        save_request(request_data)

        return jsonify({
            "status": "success",
            "message": f"Request saved (type: {request_type})"
        }), 200

    except Exception as e:
        print("❌ Error in /receive-request:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

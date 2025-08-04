from flask import Flask, jsonify, request
import os
import requests
from datetime import datetime
from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis
)
from utils.db import save_request, init_db  # ✅ SQLite対応
from utils.gpt_utils import classify_request_type

# ✅ 本番Renderでも確実に初期化されるようにFlaskインスタンス作成前に呼び出す
init_db()

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask app is running!"

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

        result = get_meal_with_basis(access_token, start_date, end_date)
        return jsonify({"status": "ok", "result": result})

    except Exception as e:
        print("❌ Error in /test-meal-basis:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 400

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

@app.route('/receive-request', methods=["POST"])
def receive_request():
    try:
        data = request.get_json(force=True)
        print("🔍 受信データ:", data)

        event = data.get("events", [{}])[0]
        event_type = event.get("type")

        if event_type not in ["message", "postback"]:
            return jsonify({
                "status": "ignored",
                "message": f"イベントタイプ '{event_type}' は対象外のため無視されました"
            }), 200

        message_text = ""
        if event_type == "message":
            message_text = event.get("message", {}).get("text", "")
        elif event_type == "postback":
            message_text = event.get("postback", {}).get("data", "")

        if not message_text:
            return jsonify({
                "status": "ignored",
                "message": "メッセージテキストが取得できませんでした"
            }), 200

        timestamp = event.get("timestamp") or datetime.now().timestamp()
        timestamp_str = datetime.fromtimestamp(timestamp / 1000).isoformat()

        request_type = classify_request_type(message_text)

        request_data = {
            "message": message_text,
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

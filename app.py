from flask import Flask, jsonify, request
import requests
from datetime import datetime
from sqlalchemy import text
from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis_hybrid
)
from utils.db import save_request, update_request_with_advice, init_db, get_db_session
from utils.gpt_utils import (
    classify_request_type,
    generate_meal_advice,
    generate_workout_advice,
    generate_operation_advice,
    generate_other_reply
)

# ✅ 本番Renderでも確実に初期化されるようにFlaskインスタンス作成前に呼び出す
init_db()

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask app is running!"


@app.route('/test-caromil', methods=["POST"])
def test_caromil():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        unit = data.get("unit", "day")

        if not user_id:
            raise Exception("user_id は必須です")
        if not start_date or not end_date:
            raise Exception("start_date, end_date は必須です")

        result = get_anthropometric_data(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            unit=unit
        )
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        print("❌ Error in /test-caromil:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/test-userinfo", methods=["POST"])
def test_userinfo():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        if not user_id:
            raise Exception("user_id は必須です")

        from utils.caromil import get_access_token
        access_token = get_access_token(user_id)

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
        from utils.caromil import get_meal_with_basis
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not user_id:
            raise Exception("user_id は必須です")
        if not start_date or not end_date:
            raise Exception("start_date, end_date は必須です")

        result = get_meal_with_basis(user_id, start_date, end_date)
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
        user_id = event.get("source", {}).get("userId")

        # メッセージ分類
        request_type = classify_request_type(message_text)

        # まずリクエストをDBに保存し、そのIDを取得
        request_id = save_request({
            "message": message_text,
            "timestamp": timestamp_str,
            "user_id": user_id,
            "request_type": request_type
        })

        # タイプ別アドバイス生成
        advice_text = None
        if request_type == "meal_feedback":
            meal_data = get_meal_with_basis_hybrid(user_id)
            body_data = get_anthropometric_data(
                user_id,
                start_date=timestamp_str[:10],
                end_date=timestamp_str[:10]
            )
            advice_text = generate_meal_advice(meal_data, body_data)
        elif request_type == "workout_question":
            advice_text = generate_workout_advice(message_text)
        elif request_type == "system_question":
            advice_text = generate_operation_advice(message_text)
        else:
            advice_text = generate_other_reply(message_text)

        # アドバイスをDBに更新（statusは未返信）
        if advice_text:
            update_request_with_advice(request_id, advice_text, status="未返信")

        return jsonify({
            "status": "success",
            "message": f"Request saved and advice generated (type: {request_type})"
        }), 200

    except Exception as e:
        print("❌ Error in /receive-request:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==============================
# デバッグ用: 最新アドバイス確認
# ==============================
@app.route("/debug-requests", methods=["GET"])
def debug_requests():
    """
    DBに保存されている最新のリクエスト（アドバイス）を確認
    """
    try:
        session = get_db_session()
        rows = session.execute(
            text("SELECT id, user_id, advice_text, status, created_at FROM requests ORDER BY id DESC LIMIT 5")
        ).mappings().all()
        session.close()

        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

# app.py
from flask import Flask, jsonify, request
import requests
import os
from datetime import datetime

from sqlalchemy import text  # JOIN付き生SQLやUPSERTで使用

from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis
)
from utils.db import (
    save_request,
    update_request_with_advice,
    init_db,
    SessionLocal,
    Request
)
from utils.gpt_utils import (
    classify_request_type,
    generate_meal_advice,
    generate_workout_advice,
    generate_operation_advice,
    generate_other_reply
)

from utils.formatting import format_daily_report
from utils.line import (
    send_line_message,
    LineSendError,
    get_line_profile,
    LineProfileError,
)

# ✅ DB初期化
init_db()

app = Flask(__name__)

# ---------------------------
# 管理API 用の簡易認証
# ---------------------------
def _require_admin():
    """
    管理APIの簡易認証。環境変数 ADMIN_TOKEN が設定されている場合のみ有効。
    未設定ならチェックをスキップ（開発用）。
    """
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        return None  # 認証スキップ
    if request.headers.get("X-Admin-Token") != admin_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    return None

@app.route('/')
def index():
    return "Flask app is running!"

# ---------------------------
# users への名前UPSERTヘルパ
# ---------------------------
def upsert_user_name(user_id: str, name: str):
    """
    空文字では上書きしない（既存名を尊重）。
    """
    if not user_id:
        return
    with SessionLocal() as s:
        s.execute(text("""
            INSERT INTO users (user_id, name)
            VALUES (:user_id, :name)
            ON CONFLICT (user_id) DO UPDATE
            SET name = COALESCE(NULLIF(:name, ''), users.name),
                updated_at = NOW();
        """), {"user_id": user_id, "name": name or ""})
        s.commit()

# ---------------------------
# 検証用エンドポイント
# ---------------------------
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

# ---------------------------
# LINE Webhook 受信
# ---------------------------
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

        # ✅ プロフィール同期（表示名をusersへUPSERT）
        if user_id:
            try:
                prof = get_line_profile(user_id)  # LINE APIから取得
                display_name = prof.get("displayName") or ""
                upsert_user_name(user_id, display_name)
            except LineProfileError as e:
                app.logger.warning(f"[profile-sync] {user_id}: {e}")
            except Exception as e:
                app.logger.exception(f"[profile-sync] unexpected error: {e}")

        # メッセージ分類
        request_type = classify_request_type(message_text)

        # リクエスト保存
        request_id = save_request({
            "message": message_text,
            "timestamp": timestamp_str,
            "user_id": user_id,
            "request_type": request_type
        })

        # タイプ別アドバイス生成
        advice_text = None
        if request_type == "meal_feedback":
            meal_data = get_meal_with_basis(user_id, timestamp_str[:10], timestamp_str[:10])
            body_data = get_anthropometric_data(
                user_id,
                start_date=timestamp_str[:10],
                end_date=timestamp_str[:10]
            )
            advice_text = generate_meal_advice(
                meal_data=meal_data,
                body_data=body_data,
                date_str=timestamp_str[:10],
            )
        elif request_type == "workout_question":
            advice_text = generate_workout_advice(message_text)
        elif request_type == "system_question":
            advice_text = generate_operation_advice(message_text)
        else:
            advice_text = generate_other_reply(message_text)

        # アドバイスをDBに更新（★ status を 'pending' に統一）
        if advice_text:
            print("🔍 生成されたアドバイス内容:", advice_text)
            update_request_with_advice(request_id, advice_text, status="pending")

        return jsonify({
            "status": "success",
            "message": f"Request saved and advice generated (type: {request_type})"
        }), 200

    except Exception as e:
        print("❌ Error in /receive-request:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ---------------------------
# Streamlit用：未返信取得（JOINで名前同梱）
# ---------------------------
@app.route("/get-unreplied", methods=["GET"])
def get_unreplied():
    auth = _require_admin()
    if auth:
        return auth

    session = SessionLocal()
    try:
        # users を LEFT JOIN して user_name を同梱
        sql = text("""
            SELECT
                r.id,
                r.user_id,
                COALESCE(u.name, '') AS user_name,
                r.message,
                r.request_type,
                r.timestamp,
                r.advice_text
            FROM requests r
            LEFT JOIN users u ON u.user_id = r.user_id
            WHERE r.status = :status
            ORDER BY r.timestamp DESC
            LIMIT 20
        """)
        # ★ 'pending' だけを返す
        rows = session.execute(sql, {"status": "pending"}).fetchall()

        data = []
        for row in rows:
            rid, user_id, user_name, message, req_type, ts, advice = row
            # timestamp を ISO 文字列に統一
            try:
                ts_val = ts.isoformat()
            except Exception:
                ts_val = str(ts)
            data.append({
                "id": rid,
                "user_id": user_id,
                "user_name": user_name or "",
                "message": message,
                "request_type": req_type,
                "timestamp": ts_val,
                "advice_text": advice,
            })

        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        print("❌ Error in /get-unreplied:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

# ---------------------------
# ★ 新規：整形レポート取得（MVP 1）
# ---------------------------
@app.route("/debug-formatted", methods=["GET"])
def debug_formatted():
    auth = _require_admin()
    if auth:
        return auth
    try:
        user_id = request.args.get("user_id")
        date = request.args.get("date")  # YYYY-MM-DD
        if not user_id or not date:
            return jsonify({"status": "error", "message": "user_id, date は必須です"}), 400

        meal = get_meal_with_basis(user_id, date, date)
        body = get_anthropometric_data(user_id, date, date)
        text = format_daily_report(meal, body, date)
        return jsonify({"status": "ok", "text": text})
    except Exception as e:
        print("❌ Error in /debug-formatted:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------------------
# ★ 新規：返信送信（MVP 2）
# ---------------------------
@app.route("/send-reply", methods=["POST"])
def send_reply():
    auth = _require_admin()
    if auth:
        return auth

    session = SessionLocal()
    try:
        payload = request.get_json(force=True)
        request_id = payload.get("request_id")
        message_text = payload.get("message")

        if not request_id or not message_text:
            return jsonify({"status": "error", "message": "request_id, message は必須です"}), 400

        r = session.query(Request).filter(Request.id == request_id).first()
        if not r:
            return jsonify({"status": "error", "message": f"Request {request_id} が見つかりません"}), 404

        try:
            send_line_message(r.user_id, message_text)
        except LineSendError as e:
            print("❌ LINE送信エラー:", e)
            return jsonify({"status": "error", "message": f"LINE送信失敗: {e}"}), 502

        # ★ 'replied' に統一
        r.status = "replied"
        r.advice_text = message_text
        # r.sent_at = datetime.utcnow()  # もしカラムを追加したら
        session.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        session.rollback()
        print("❌ Error in /send-reply:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

# ---------------------------
# ★ 新規：サマリー＋アドバイス一括送信
# ---------------------------
@app.route("/send-summary-and-advice", methods=["POST"])
def send_summary_and_advice():
    auth = _require_admin()
    if auth:
        return auth

    session = SessionLocal()
    try:
        payload = request.get_json(force=True)
        request_id = payload.get("request_id")
        date_str = payload.get("date")  # YYYY-MM-DD

        if not request_id or not date_str:
            return jsonify({"status": "error", "message": "request_id と date は必須です"}), 400

        r = session.query(Request).filter(Request.id == request_id).first()
        if not r:
            return jsonify({"status": "error", "message": f"Request {request_id} が見つかりません"}), 404
        if not r.user_id:
            return jsonify({"status": "error", "message": "user_id が空のため送信できません"}), 400

        meal = get_meal_with_basis(r.user_id, date_str, date_str)
        body = get_anthropometric_data(r.user_id, date_str, date_str)
        summary_text = format_daily_report(meal, body, date_str)

        advice_text = (r.advice_text or "").strip()
        message_text = (
            f"【今日の食事まとめ】\n{summary_text}\n\n――――――\n【アドバイス】\n"
            f"{advice_text if advice_text else '（未作成）'}"
        )

        try:
            send_line_message(r.user_id, message_text)
        except LineSendError as e:
            print("❌ LINE送信エラー:", e)
            return jsonify({"status": "error", "message": f"LINE送信失敗: {e}"}), 502

        # ★ 'replied' に統一
        r.status = "replied"
        r.advice_text = message_text  # 送信した最終本文で上書き
        session.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        session.rollback()
        print("❌ Error in /send-summary-and-advice:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

# ---------------------------
# ★ 新規：除外API（推奨：/update-status のラッパ）
# ---------------------------
@app.route("/update-status", methods=["POST"])
def update_status():
    auth = _require_admin()
    if auth:
        return auth

    payload = request.get_json(force=True) or {}
    try:
        rid = int(payload.get("request_id", 0))
    except Exception:
        rid = 0
    status = (payload.get("status") or "").strip()

    if not rid or status not in {"pending", "replied", "ignored"}:
        return jsonify({"status": "error", "error": "invalid request"}), 400

    session = SessionLocal()
    try:
        r = session.query(Request).filter(Request.id == rid).first()
        if not r:
            return jsonify({"status": "error", "error": "not found"}), 404

        r.status = status
        session.commit()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        session.rollback()
        print("❌ Error in /update-status:", e)
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        session.close()

@app.route("/discard-request", methods=["POST"])
def discard_request():
    """
    互換エンドポイント。UIがまだ /discard-request を叩く場合のため。
    内部的に 'ignored' へ更新する。
    """
    auth = _require_admin()
    if auth:
        return auth

    payload = request.get_json(force=True) or {}
    try:
        rid = int(payload.get("request_id", 0))
    except Exception:
        rid = 0
    if not rid:
        return jsonify({"status": "error", "error": "invalid request"}), 400

    session = SessionLocal()
    try:
        r = session.query(Request).filter(Request.id == rid).first()
        if not r:
            return jsonify({"status": "error", "error": "not found"}), 404
        r.status = "ignored"
        session.commit()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        session.rollback()
        print("❌ Error in /discard-request:", e)
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        session.close()

if __name__ == '__main__':
    app.run(debug=True)

# app.py
from flask import Flask, jsonify, request
import requests
import os
from datetime import datetime, timezone, timedelta, date as date_cls

from sqlalchemy import text  # JOIN付き生SQLやUPSERTで使用

from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis,
    get_user_info,              # 目標取得
    save_intake_breakdown,      # ★ 合計＋内訳を安全保存（期間一括対応）
)
from utils.db import (
    save_request,
    update_request_with_advice,
    init_db,
    SessionLocal,
    Request,
    ensure_user_profile,
    search_users,
    get_user_profile_one,
    get_user_weights,
    get_user_intake,
    upsert_metrics_daily,       # 体重/体脂肪の日次UPSERT
    upsert_goals_daily_bulk,
    fetch_goals_range,
    set_user_goals_json,
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
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        return None  # 認証スキップ（開発用）
    if request.headers.get("X-Admin-Token") != admin_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    return None

@app.route("/")
def index():
    return "Flask app is running!"

# ===========================
# 日次保存ヘルパ（堅牢な抽出）
# ===========================
def _to_float(v):
    try:
        return float(v) if v is not None and v != "-" else None
    except Exception:
        return None

def _norm_date(s: str) -> str:
    if not s:
        return ""
    s = s.strip().replace("/", "-")
    return s[:10]

def _extract_body_for_day(body_data, yyyy_mm_dd: str):
    if not body_data:
        return None, None

    rows = None
    if isinstance(body_data, dict):
        if isinstance(body_data.get("data"), list):
            rows = body_data["data"]
        elif isinstance(body_data.get("result"), list):
            rows = body_data["result"]
    elif isinstance(body_data, list):
        rows = body_data

    if not isinstance(rows, list):
        return None, None

    want = _norm_date(yyyy_mm_dd)
    for r in rows:
        if not isinstance(r, dict):
            continue
        if _norm_date(r.get("date")) == want:
            w = _to_float(r.get("weight") or r.get("weight_kg"))
            bf = _to_float(r.get("body_fat") or r.get("body_fat_pc") or r.get("fat"))
            return w, bf
    return None, None

def _extract_nutrition_for_day(meal_data, yyyy_mm_dd: str):
    """（検証用）必要に応じて個別日抽出。通常の保存は save_intake_breakdown で行う。"""
    if not meal_data:
        return None, None, None, None

    want = _norm_date(yyyy_mm_dd)

    # E: 直下に meal_with_basis
    if isinstance(meal_data, dict) and isinstance(meal_data.get("meal_with_basis"), list):
        for item in meal_data["meal_with_basis"]:
            if not isinstance(item, dict):
                continue
            if _norm_date(item.get("date")) == want:
                sums = (item.get("meal_histories_summary") or {}).get("all") or {}
                kcal = _to_float(sums.get("calorie") or sums.get("kcal") or sums.get("calories"))
                p = _to_float(sums.get("protein") or sums.get("p") or sums.get("protein_g"))
                f = _to_float(sums.get("fat") or sums.get("lipid") or sums.get("f") or sums.get("fat_g"))
                c = _to_float(sums.get("carbohydrate") or sums.get("carb") or sums.get("c") or sums.get("carbohydrate_g"))
                return kcal, p, f, c

    # D: {"result":{"meal_with_basis":[...]}}
    if isinstance(meal_data, dict):
        result = meal_data.get("result")
        if isinstance(result, dict):
            lst = result.get("meal_with_basis")
            if isinstance(lst, list):
                for item in lst:
                    if not isinstance(item, dict):
                        continue
                    if _norm_date(item.get("date")) == want:
                        sums = (item.get("meal_histories_summary") or {}).get("all") or {}
                        kcal = _to_float(sums.get("calorie") or sums.get("kcal") or sums.get("calories"))
                        p = _to_float(sums.get("protein") or sums.get("p") or sums.get("protein_g"))
                        f = _to_float(sums.get("fat") or sums.get("lipid") or sums.get("f") or sums.get("fat_g"))
                        c = _to_float(sums.get("carbohydrate") or sums.get("carb") or sums.get("c") or sums.get("carbohydrate_g"))
                        return kcal, p, f, c

    # 既存の A/B/C
    if isinstance(meal_data, dict) and isinstance(meal_data.get("summary"), dict):
        s = meal_data["summary"]
        if _norm_date(s.get("date")) == want:
            kcal = _to_float(s.get("calorie") or s.get("calories") or s.get("kcal") or s.get("calorie_kcal"))
            p = _to_float(s.get("protein") or s.get("protein_g"))
            f = _to_float(s.get("fat") or s.get("fat_g") or s.get("lipid"))
            c = _to_float(s.get("carb") or s.get("carb_g") or s.get("carbohydrate") or s.get("carbohydrate_g"))
            return kcal, p, f, c

    if isinstance(meal_data, dict) and isinstance(meal_data.get("days"), list):
        for d in meal_data["days"]:
            if not isinstance(d, dict):
                continue
            if _norm_date(d.get("date")) == want:
                kcal = _to_float(d.get("calorie") or d.get("calories") or d.get("kcal") or d.get("calorie_kcal"))
                p = _to_float(d.get("protein") or d.get("protein_g") or d.get("p"))
                f = _to_float(d.get("fat") or d.get("fat_g") or d.get("lipid") or d.get("f"))
                c = _to_float(d.get("carb") or d.get("carb_g") or d.get("c") or d.get("carbohydrate") or d.get("carbohydrate_g"))
                return kcal, p, f, c

    rows = meal_data if isinstance(meal_data, list) else None
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict):
                continue
            if _norm_date(r.get("date")) == want:
                kcal = _to_float(r.get("calorie_kcal") or r.get("calorie") or r.get("calories") or r.get("kcal"))
                p = _to_float(r.get("protein_g") or r.get("protein") or r.get("p"))
                f = _to_float(r.get("fat_g") or r.get("fat") or r.get("lipid") or r.get("f"))
                c = _to_float(r.get("carb_g") or r.get("carb") or r.get("c") or r.get("carbohydrate") or r.get("carbohydrate_g"))
                return kcal, p, f, c

    return None, None, None, None

# ---------------------------
# 検証用エンドポイント
# ---------------------------
@app.route("/test-caromil", methods=["POST"])
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

        response = requests.post(url, headers=headers, timeout=30)

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

@app.route("/test-meal-basis", methods=["POST"])
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
        print("❌ Error in /test-meal-basis:", e)
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
@app.route("/receive-request", methods=["POST"])
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

        ts_ms = event.get("timestamp") or int(datetime.now().timestamp() * 1000)
        timestamp_str = datetime.fromtimestamp(ts_ms / 1000).isoformat()
        user_id = event.get("source", {}).get("userId")

        # ✅ プロフィール同期
        if user_id:
            display_name = ""
            photo_url = None
            try:
                prof = get_line_profile(user_id)
                display_name = prof.get("displayName") or ""
                photo_url = prof.get("pictureUrl") or None
            except LineProfileError as e:
                app.logger.warning(f"[profile-sync] {user_id}: {e}")
            except Exception as e:
                app.logger.exception(f"[profile-sync] unexpected error: {e}")

            last_contact_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            ensure_user_profile(
                user_id=user_id,
                name=display_name if display_name else None,
                photo_url=photo_url,
                last_contact=last_contact_dt
            )

        request_type = classify_request_type(message_text)

        request_id = save_request({
            "message": message_text,
            "timestamp": timestamp_str,
            "user_id": user_id,
            "request_type": request_type,
            "status": "pending",
        })

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

        if advice_text:
            print("🔍 生成されたアドバイス内容:", advice_text)
            update_request_with_advice(request_id, advice_text, status="pending")

        # ---- 当日分のUPSERT：体組成＋（合計＋内訳） ----
        if user_id:
            day = timestamp_str[:10]  # 'YYYY-MM-DD'
            try:
                body_data = get_anthropometric_data(user_id, start_date=day, end_date=day)
                w, bf = _extract_body_for_day(body_data, day)

                s = SessionLocal()
                try:
                    upsert_metrics_daily(
                        user_id=user_id,
                        d=datetime.fromisoformat(day).date(),
                        weight_kg=w,
                        body_fat_pc=bf,
                        session=s
                    )
                    s.commit()
                except Exception:
                    s.rollback()
                    raise
                finally:
                    s.close()

                # ★ 栄養は save_intake_breakdown で当日分を一括保存（合計＋内訳）
                stat = save_intake_breakdown(user_id, day, day)
                app.logger.info(f"[receive-request] save_intake_breakdown({user_id}, {day}) -> {stat}")

            except Exception as e:
                app.logger.warning(f"[daily-upsert] {user_id} {day}: {e}")
        # ---- ここまで ----

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
            LEFT JOIN user_profile u ON u.user_id = r.user_id
            WHERE r.status = :status
            ORDER BY r.timestamp DESC
            LIMIT 20
        """)
        rows = session.execute(sql, {"status": "pending"}).fetchall()

        data = []
        for row in rows:
            rid, user_id, user_name, message, req_type, ts, advice = row
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

        r.status = "replied"
        r.advice_text = message_text
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

        r.status = "replied"
        r.advice_text = message_text
        session.commit()

        return jsonify({"status": "ok"})
    except Exception as e:
        session.rollback()
        print("❌ Error in /send-summary-and-advice:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()

# ---------------------------
# ★ 新規：除外API
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

# ---------------------------
# ★ /users
# ---------------------------
@app.route("/users", methods=["GET"])
def api_users():
    auth = _require_admin()
    if auth:
        return auth
    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except Exception:
        limit, offset = 20, 0
    rows = search_users(q=q, limit=limit, offset=offset)
    return jsonify({"data": rows}), 200

# ---------------------------
# ★ /user/profile
# ---------------------------
@app.route("/user/profile", methods=["GET"])
def api_user_profile():
    auth = _require_admin()
    if auth:
        return auth
    uid = (request.args.get("user_id") or "").strip()
    if not uid:
        return jsonify({"error": "bad_request"}), 400
    row = get_user_profile_one(uid)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"data": row}), 200

# ---------------------------
# ★ /user/weights
# ---------------------------
@app.route("/user/weights", methods=["GET"])
def api_user_weights():
    auth = _require_admin()
    if auth:
        return auth
    uid = (request.args.get("user_id") or "").strip()
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    if not uid or not start or not end:
        return jsonify({"error": "bad_request"}), 400
    try:
        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
    except Exception:
        return jsonify({"error": "invalid_date"}), 400
    rows = get_user_weights(uid, s, e)
    return jsonify({"data": rows}), 200

# ---------------------------
# ★ /user/intake
# ---------------------------
@app.route("/user/intake", methods=["GET"])
def api_user_intake():
    auth = _require_admin()
    if auth:
        return auth
    uid = (request.args.get("user_id") or "").strip()
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    if not uid or not start or not end:
        return jsonify({"error": "bad_request"}), 400
    try:
        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
    except Exception:
        return jsonify({"error": "invalid_date"}), 400
    rows = get_user_intake(uid, s, e)
    return jsonify({"data": rows}), 200

# ---------------------------
# ★ バックフィル（合計＋内訳を期間一括保存）
# ---------------------------
@app.post("/backfill-daily")
def backfill_daily():
    auth = _require_admin()
    if auth:
        return auth
    try:
        payload = request.get_json(force=True) or {}
        uid = (payload.get("user_id") or "").strip()
        start = (payload.get("start") or "").strip()
        end = (payload.get("end") or "").strip()
        if not uid or not start or not end:
            return jsonify({"error": "bad_request"}), 400

        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
        if e < s:
            return jsonify({"error": "invalid_date_range"}), 400

        CHUNK_DAYS = 7
        rows_written = 0        # 体組成の保存行数
        empty_days = 0          # 体組成が空だった日数
        intake_written = 0      # 栄養（合計＋内訳）の書き込み件数

        dbs = SessionLocal()
        try:
            cur = s
            while cur <= e:
                chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), e)
                sd, ed = cur.isoformat(), chunk_end.isoformat()

                # 1) 体組成はチャンク取得 → 日別UPSERT
                body = None
                try:
                    body = get_anthropometric_data(uid, start_date=sd, end_date=ed)
                except Exception as be:
                    app.logger.warning(f"[backfill-daily] anthropometric chunk fail {uid} {sd}..{ed}: {be}")

                d = cur
                while d <= chunk_end:
                    day = d.isoformat()
                    try:
                        w, bf = _extract_body_for_day(body, day) if body is not None else (None, None)
                        upsert_metrics_daily(uid, d, w, bf, session=dbs)
                        rows_written += 1
                        if w is None:
                            empty_days += 1
                    except Exception as de:
                        app.logger.warning(f"[backfill-daily] save metrics fail {uid} {day}: {de}")
                    d += timedelta(days=1)

                # 2) 栄養は save_intake_breakdown でチャンク一括保存（合計＋内訳）
                try:
                    stat = save_intake_breakdown(uid, sd, ed)
                    intake_written += int(stat.get("written", 0))
                except Exception as me:
                    app.logger.warning(f"[backfill-daily] save_intake_breakdown fail {uid} {sd}..{ed}: {me}")

                cur = chunk_end + timedelta(days=1)

            dbs.commit()
        except Exception:
            dbs.rollback()
            raise
        finally:
            dbs.close()

        return jsonify({
            "status": "ok",
            "user_id": uid,
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "rows_written": rows_written,      # 体組成のUPSERT件数
            "empty_days": empty_days,          # 体組成が空だった日
            "intake_written": intake_written,  # 栄養（日数）書き込み件数（参考）
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "internal_error", "detail": str(e)}), 500

# ---------------------------
# ★ 不足分だけ同期（合計 or 内訳が欠けている日を埋める）
# ---------------------------
@app.post("/backfill-intake-missing")
def backfill_intake_missing():
    """
    表示期間のうち「行が無い / 合計のどれかがNULL / meals_breakdownがNULL/空」の日だけ
    Calomealから取得して user_nutrition_daily を埋める。
    save_intake_breakdown() を使うので合計＋内訳をまとめて保存。
    """
    auth = _require_admin()
    if auth:
        return auth
    try:
        payload = request.get_json(force=True) or {}
        uid = (payload.get("user_id") or "").strip()
        start = (payload.get("start") or "").strip()
        end = (payload.get("end") or "").strip()
        if not uid or not start or not end:
            return jsonify({"status": "error", "message": "bad_request"}), 400

        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
        if e < s:
            return jsonify({"status": "error", "message": "invalid date range"}), 400

        # 1) 期間内の既存行を取得
        ses = SessionLocal()
        try:
            sql = text("""
                SELECT date, calorie_kcal, protein_g, fat_g, carb_g, meals_breakdown
                FROM user_nutrition_daily
                WHERE user_id = :uid AND date BETWEEN :s AND :e
            """)
            rows = ses.execute(sql, {"uid": uid, "s": s, "e": e}).fetchall()
        finally:
            ses.close()

        # 2) 期間全日と突合
        all_days = []
        cur = s
        while cur <= e:
            all_days.append(cur)
            cur += timedelta(days=1)

        by_date = {r[0]: {"k": r[1], "p": r[2], "f": r[3], "c": r[4], "mb": r[5]} for r in rows}

        need_dates = []
        for d in all_days:
            if d not in by_date:
                need_dates.append(d); continue
            rec = by_date[d]
            # 合計のいずれかが None → 要取得（0 は有効値なのでOK）
            if any(v is None for v in [rec["k"], rec["p"], rec["f"], rec["c"]]):
                need_dates.append(d); continue
            # 内訳が NULL/空 → 要取得
            if rec["mb"] in (None, {}, ""):
                need_dates.append(d); continue

        # 3) 連続区間にまとめて API 呼び出し回数を減らす
        def _group_ranges(dates: list[date_cls]) -> list[tuple[date_cls, date_cls]]:
            if not dates:
                return []
            dates = sorted(dates)
            groups = []
            start_d = prev = dates[0]
            for d in dates[1:]:
                if (d - prev).days == 1:
                    prev = d
                else:
                    groups.append((start_d, prev))
                    start_d = prev = d
            groups.append((start_d, prev))
            return groups

        ranges = _group_ranges(need_dates)
        total_written = 0
        for (d1, d2) in ranges:
            stat = save_intake_breakdown(uid, d1.isoformat(), d2.isoformat())
            total_written += int(stat.get("written", 0))

        return jsonify({
            "status": "ok",
            "user_id": uid,
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "need_days": len(need_dates),
            "written": total_written,
            "ranges": [{"start": a.isoformat(), "end": b.isoformat()} for (a, b) in ranges],
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------------------
# ★ 期間目標バックフィル
# ---------------------------
@app.post("/sync-goals-range")
def sync_goals_range():
    auth = _require_admin()
    if auth:
        return auth
    try:
        payload = request.get_json(force=True) or {}
        uid = (payload.get("user_id") or "").strip()
        start = (payload.get("start") or "").strip()
        end = (payload.get("end") or "").strip()
        if not uid or not start or not end:
            return jsonify({"status": "error", "message": "user_id, start, end are required (YYYY-MM-DD)"}), 400

        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
        if e < s:
            return jsonify({"status": "error", "message": "invalid date range"}), 400

        ui = get_user_info(uid) or {}
        raw_goal = (
            (ui.get("result") or {}).get("goal")
            or ui.get("goal")
            or ui
            or {}
        )

        def _safe_num(v):
            try:
                return float(v)
            except Exception:
                return None

        kcal = _safe_num(raw_goal.get("calorie") or raw_goal.get("kcal") or raw_goal.get("calories"))
        p    = _safe_num(raw_goal.get("protein") or raw_goal.get("protein_g"))
        f    = _safe_num(raw_goal.get("lipid")   or raw_goal.get("fat") or raw_goal.get("fat_g"))
        c    = _safe_num(raw_goal.get("carbohydrate") or raw_goal.get("carb") or raw_goal.get("carb_g"))

        rows = []
        cur = s
        while cur <= e:
            rows.append({"date": cur, "kcal": kcal, "p": p, "f": f, "c": c})
            cur += timedelta(days=1)

        stat = upsert_goals_daily_bulk(uid, rows)

        set_user_goals_json(uid, {
            "calorie": kcal,
            "protein": p,
            "lipid": f,
            "carbohydrate": c,
            "source": "calomeal_user_info",
            "synced_at": datetime.now(timezone.utc).isoformat()
        })

        return jsonify({
            "status": "ok",
            "user_id": uid,
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "rows_written": stat["written"],
            "empty_days": stat["empty"],
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------------------------
# ★ 期間目標取得
# ---------------------------
@app.get("/user/goals-range")
def user_goals_range():
    auth = _require_admin()
    if auth:
        return auth
    try:
        uid = (request.args.get("user_id") or "").strip()
        start = (request.args.get("start") or "").strip()
        end = (request.args.get("end") or "").strip()
        if not uid or not start or not end:
            return jsonify({"status": "error", "message": "user_id, start, end are required (YYYY-MM-DD)"}), 400

        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
        rows = fetch_goals_range(uid, s, e)
        return jsonify({"status": "ok", "data": rows})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

# app.py
from flask import Flask, jsonify, request
import requests
import os
from datetime import datetime, timezone

from sqlalchemy import text  # JOIN付き生SQLやUPSERTで使用

from utils.caromil import (
    get_anthropometric_data,
    get_meal_with_basis
)
from utils.db import (
    # 既存
    save_request,
    update_request_with_advice,
    init_db,
    SessionLocal,
    Request,
    # 追加（Step2Aで実装）
    ensure_user_profile,
    search_users,
    get_user_profile_one,
    get_user_weights,
    get_user_intake,
    # ★ 追加：日次UPSERT用
    upsert_metrics_daily,
    upsert_nutrition_daily,
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
    """'2025/08/12' も '2025-08-12' に正規化して比較"""
    if not s:
        return ""
    s = s.strip().replace("/", "-")
    return s[:10]

def _extract_body_for_day(body_data, yyyy_mm_dd: str):
    """
    get_anthropometric_data の返り値から、その日の weight, body_fat を抜き出す。
    対応フォーマット:
      1) {"data":[{"date":"2025-08-01","weight":65.2,"body_fat":18.4}, ...]}
      2) [{"date":"2025-08-01","weight_kg":65.2,"body_fat_pc":18.4}, ...]
      3) {"result":[{"date":"2025/08/12","weight":64.7,"fat":15}, ...]}  ←今回の例
    """
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
    """
    get_meal_with_basis の返り値から、その日の kcal/P/F/C 合計を抜き出す。
    対応フォーマット:
      A) {"summary":{"date":"2025-08-01","calorie":..., "protein":..., "fat":..., "carb":...}}
      B) {"days":[{"date":"2025-08-01","kcal":..., "p":..., "f":..., "c":...}, ...]}
      C) [{"date":"2025-08-01","calorie_kcal":..., "protein_g":..., "fat_g":..., "carb_g":...}]
      D) {"result":{"meal_with_basis":[{"date":"2025/08/12","meal_histories_summary":{"all":{...}}}]}}
      E) {"meal_with_basis":[{"date":"2025/08/12","meal_histories_summary":{"all":{...}}}]} ←今回の可能性
    """
    if not meal_data:
        return None, None, None, None

    want = _norm_date(yyyy_mm_dd)

    # 直下に meal_with_basis があるパターン（E）
    if isinstance(meal_data, dict) and isinstance(meal_data.get("meal_with_basis"), list):
        for item in meal_data["meal_with_basis"]:
            if not isinstance(item, dict):
                continue
            if _norm_date(item.get("date")) == want:
                sums = (item.get("meal_histories_summary") or {}).get("all") or {}
                kcal = _to_float(sums.get("calorie") or sums.get("kcal") or sums.get("calories"))
                p = _to_float(sums.get("protein") or sums.get("p") or sums.get("protein_g"))
                f = _to_float(sums.get("fat") or sums.get("lipid") or sums.get("f") or sums.get("fat_g"))
                c = _to_float(sums.get("carbohydrate") or sums.get("carb") or sums.get("c") or sums.get("carb_g"))
                return kcal, p, f, c

    # {"result":{"meal_with_basis":[...]}} のパターン（D）
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
                        c = _to_float(sums.get("carbohydrate") or sums.get("carb") or sums.get("c") or sums.get("carb_g"))
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

        # イベントのタイムスタンプ（ミリ秒）→ ISO 文字列
        timestamp = event.get("timestamp") or datetime.now().timestamp()
        timestamp_str = datetime.fromtimestamp(timestamp / 1000).isoformat()
        user_id = event.get("source", {}).get("userId")

        # ✅ プロフィール同期（表示名・写真・last_contact を user_profile へUPSERT）
        if user_id:
            display_name = ""
            photo_url = None
            try:
                prof = get_line_profile(user_id)  # LINE APIから取得
                display_name = prof.get("displayName") or ""
                photo_url = prof.get("pictureUrl") or None
            except LineProfileError as e:
                app.logger.warning(f"[profile-sync] {user_id}: {e}")
            except Exception as e:
                app.logger.exception(f"[profile-sync] unexpected error: {e}")

            # last_contact はイベント時刻（UTC）
            last_contact_dt = datetime.fromtimestamp((event.get("timestamp") or 0) / 1000, tz=timezone.utc)

            # マスターへUPSERT（名前が空なら既存を維持）
            ensure_user_profile(
                user_id=user_id,
                name=display_name if display_name else None,
                photo_url=photo_url,
                last_contact=last_contact_dt
            )

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

        # ---- ここから：当日分の日次データを保存（UPSERT） ----
        if user_id:
            day = timestamp_str[:10]  # 'YYYY-MM-DD'
            try:
                # Calomeal から当日の体組成/食事合計を取得
                body_data = get_anthropometric_data(user_id, start_date=day, end_date=day)
                meal_data = get_meal_with_basis(user_id, day, day)

                # 取り出し（★ 日付/キー揺れ対応済み）
                w, bf = _extract_body_for_day(body_data, day)
                kcal, p, f, c = _extract_nutrition_for_day(meal_data, day)

                # DBへUPSERT（Noneはそのまま許容）
                upsert_metrics_daily(
                    user_id=user_id,
                    d=datetime.fromisoformat(day).date(),
                    weight_kg=w,
                    body_fat_pc=bf
                )
                upsert_nutrition_daily(
                    user_id=user_id,
                    d=datetime.fromisoformat(day).date(),
                    calorie_kcal=kcal,
                    protein_g=p,
                    fat_g=f,
                    carb_g=c
                )
            except Exception as e:
                app.logger.warning(f"[daily-upsert] {user_id} {day}: {e}")
        # ---- ここまで：UPSERT ----

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
        # user_profile を LEFT JOIN して user_name を同梱
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
            # timestamp を ISO 文字列に統一（DBが文字列のためtry）
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

# ---------------------------
# ★ 新規：/users（検索）
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
# ★ 新規：/user/profile（1件取得）
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
# ★ 新規：/user/weights（体重の期間取得）
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
# ★ 新規：/user/intake（栄養の期間取得）
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
# ★ 新規：過去分バックフィル（管理用）
# ---------------------------
@app.post("/backfill-daily")
def backfill_daily():
    """指定ユーザーの指定期間を Calomeal から取得し、日次テーブルへUPSERTする"""
    auth = _require_admin()
    if auth:
        return auth
    try:
        payload = request.get_json(force=True) or {}
        uid = (payload.get("user_id") or "").strip()
        start = (payload.get("start") or "").strip()  # 'YYYY-MM-DD'
        end = (payload.get("end") or "").strip()
        if not uid or not start or not end:
            return jsonify({"error": "bad_request"}), 400

        from datetime import timedelta
        s = datetime.fromisoformat(start).date()
        e = datetime.fromisoformat(end).date()
        if e < s:
            return jsonify({"error": "invalid_date_range"}), 400

        # まとめて取得（Calomeal側が期間取得対応ならAPIコールを節約）
        body = get_anthropometric_data(uid, start_date=start, end_date=end)
        meal = get_meal_with_basis(uid, start, end)

        d = s
        saved = 0
        while d <= e:
            day = d.isoformat()
            w, bf = _extract_body_for_day(body, day)
            kcal, p, f, c = _extract_nutrition_for_day(meal, day)

            upsert_metrics_daily(uid, d, w, bf)
            upsert_nutrition_daily(uid, d, kcal, p, f, c)

            saved += 1
            d += timedelta(days=1)

        return jsonify({"status": "ok", "saved_days": saved})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": "internal_error", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

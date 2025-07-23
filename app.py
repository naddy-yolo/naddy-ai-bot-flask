from flask import Flask, jsonify, request
import os
from utils.caromil import get_anthropometric_data

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask app is running!"

@app.route('/test-caromil', methods=['GET'])
def test_caromil():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        print("🔑 Access token loaded:", access_token)

        if not access_token:
            raise Exception("CAROMIL_ACCESS_TOKEN が設定されていません")

        # ✅ Calomeal APIは YYYY/MM/DD 形式が必須
        start_date = "2024/07/01"
        end_date = "2024/07/10"
        print(f"📅 Fetching data from {start_date} to {end_date}")

        result = get_anthropometric_data(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date
        )

        print("✅ API result:", result)
        return jsonify({"status": "ok", "result": result})

    except Exception as e:
        print("❌ Error in /test-caromil:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

# ✅ 認証コード取得用エンドポイント
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

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/test-caromil', methods=['GET'])
def test_caromil():
    try:
        access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
        if not access_token:
            raise Exception("CAROMIL_ACCESS_TOKEN が設定されていません")

        # ✅ Calomeal の test環境 + v2 API
        url = "https://test-connect.calomeal.com/api/v2/anthropometric"

        # ✅ 日付は ISO形式（YYYY-MM-DD）
        import datetime
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=7)).isoformat()
        end_date = today.isoformat()

        params = {
            "from": start_date,
            "to": end_date
        }
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            result = response.json()
            return jsonify({"status": "ok", "result": result})
        else:
            raise Exception(f"APIエラー: {response.status_code} - {response.text}")

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

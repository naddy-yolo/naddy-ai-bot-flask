from flask import Flask, request, jsonify
from utils.caromil import get_anthropometric_data

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello from Naddy's AI Bot (Flask)!"

@app.route("/test-caromil", methods=["POST"])
def test_caromil():
    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    unit = data.get("unit", "day")

    try:
        result = get_anthropometric_data(start_date, end_date, unit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request, jsonify
from utils.caromil import get_anthropometric, get_meal_with_basis

app = Flask(__name__)

@app.route("/")
def index():
    return "ナディ式AI Bot Flaskアプリが起動しています"

@app.route("/test-caromil", methods=["POST"])
def test_caromil():
    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    unit = data.get("unit", "day")

    result = get_anthropometric(start_date=start_date, end_date=end_date, unit=unit)
    return jsonify({"status": "ok", "result": result})

@app.route("/test-meal-basis", methods=["POST"])
def test_meal_basis():
    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    meal_with_basis = get_meal_with_basis(start_date, end_date)
    return jsonify({"status": "ok", "result": {"meal_with_basis": meal_with_basis}})

@app.route("/test-meal-pfc-df", methods=["POST"])
def test_meal_pfc_df():
    from services.data_formatter import extract_pfc_and_weight

    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    meal_with_basis = get_meal_with_basis(start_date, end_date)
    df = extract_pfc_and_weight(meal_with_basis)

    return jsonify({"status": "ok", "df": df.to_dict(orient="records")})

if __name__ == "__main__":
    app.run(debug=True)

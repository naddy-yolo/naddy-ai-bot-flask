from flask import Flask, request, jsonify
from utils.caromil import get_anthropometric_data, get_meal_with_basis
import pandas as pd
import os

app = Flask(__name__)

@app.route('/')
def index():
    return 'Naddy AI Bot is running!'

@app.route('/test-meal-basis', methods=['POST'])
def test_meal_with_basis():
    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    access_token = os.getenv("CAROMIL_ACCESS_TOKEN")

    print(f"🍽️ meal_with_basis取得: {start_date}〜{end_date}")
    result = get_meal_with_basis(access_token, start_date, end_date)

    return jsonify({"status": "ok", "result": result})


@app.route('/test-meal-pfc-df', methods=['POST'])
def test_meal_pfc_df():
    data = request.get_json()
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    access_token = os.getenv("CAROMIL_ACCESS_TOKEN")
    raw = get_meal_with_basis(access_token, start_date, end_date)

    # データ加工処理
    rows = []
    for day in raw["result"]["meal_with_basis"]:
        date = day["date"]
        weight = day["anthropometric"]["weight"]
        fat = day["anthropometric"]["fat"]
        calorie = day["basis"]["all"]["calorie"]
        protein = day["basis"]["all"]["protein"]
        fat_target = day["basis"]["all"]["lipid"]
        carb = day["basis"]["all"]["carbohydrate"]
        actual_protein = day["meal_histories_summary"]["all"]["protein"]
        actual_fat = day["meal_histories_summary"]["all"]["lipid"]
        actual_carb = day["meal_histories_summary"]["all"]["carbohydrate"]
        actual_calorie = day["meal_histories_summary"]["all"]["calorie"]

        rows.append({
            "date": date,
            "weight": weight,
            "fat": fat,
            "target_calorie": calorie,
            "actual_calorie": actual_calorie,
            "target_protein": protein,
            "actual_protein": actual_protein,
            "target_fat": fat_target,
            "actual_fat": actual_fat,
            "target_carb": carb,
            "actual_carb": actual_carb
        })

    df = pd.DataFrame(rows)
    df.fillna("-", inplace=True)

    return jsonify(df.to_dict(orient="records"))

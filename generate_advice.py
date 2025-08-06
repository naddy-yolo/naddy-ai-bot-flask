from utils.db import get_unreplied_requests, update_advice_text
from utils.caromil import get_meal_with_basis, get_anthropometric_data
from utils.gpt_utils import generate_advice_by_prompt

from datetime import datetime
import time


def format_prompt(meal_data: dict, body_data: dict) -> str:
    """
    GPT用のプロンプト文を構成（PFC実績・目標・体重データ含む）
    Calomeal APIの現行レスポンス構造に対応
    """
    # meal_with_basisの配列取得
    meal_list = meal_data.get("result", {}).get("meal_with_basis", [])
    if not meal_list:
        raise ValueError("meal_with_basis データが存在しません")
    meal = meal_list[0]

    # 実績値（meal_histories_summary）
    actual = meal.get("meal_histories_summary", {}).get("all", {})
    # 目標値（basis）
    target = meal.get("basis", {}).get("all", {})

    # 体重データの取得
    body_list = body_data.get("result", [])
    weight = None
    if body_list and isinstance(body_list, list):
        weight = body_list[0].get("weight")

    prompt = (
        f"昨日の食事の栄養バランスについてアドバイスをください。\n\n"
        f"【実績】\n"
        f"たんぱく質：{actual.get('protein')}g\n"
        f"脂質：{actual.get('lipid')}g\n"
        f"炭水化物：{actual.get('carbohydrate')}g\n"
        f"カロリー：{actual.get('calorie')}kcal\n\n"
        f"【目標】\n"
        f"たんぱく質：{target.get('protein')}g\n"
        f"脂質：{target.get('lipid')}g\n"
        f"炭水化物：{target.get('carbohydrate')}g\n"
        f"カロリー：{target.get('calorie')}kcal\n\n"
        f"【体重】\n{weight}kg\n\n"
        f"指導者として、丁寧で前向きなアドバイスをお願いします。"
    )
    return prompt


def generate_advice_for_unreplied():
    """
    未返信のユーザーリクエストに対して、
    CalomealデータからGPTでアドバイス生成＆保存
    """
    requests = get_unreplied_requests()
    if not requests:
        print("✅ 未返信リクエストはありません。")
        return

    for req in requests:
        print(f"🎯 処理中 user_id={req.user_id} timestamp={req.timestamp}")

        # Calomeal APIは YYYY/MM/DD 形式
        dt = datetime.fromisoformat(req.timestamp)
        date_str = dt.strftime("%Y/%m/%d")

        try:
            # user_id を直接渡す
            meal_data = get_meal_with_basis(req.user_id, date_str, date_str)
            body_data = get_anthropometric_data(req.user_id, date_str, date_str)

            prompt = format_prompt(meal_data, body_data)
            advice_text = generate_advice_by_prompt(prompt)

            update_advice_text(req.user_id, req.timestamp, advice_text)
            time.sleep(1)  # API過負荷防止のため小休止

        except Exception as e:
            print(f"❌ {req.user_id} のアドバイス生成失敗:", e)


if __name__ == "__main__":
    generate_advice_for_unreplied()

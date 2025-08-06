from utils.db import get_unreplied_requests, update_advice_text
from utils.caromil import refresh_access_token, get_meal_with_basis, get_anthropometric_data
from utils.gpt_utils import generate_advice_by_prompt

from datetime import datetime
import time


def format_prompt(meal_data: dict, body_data: dict) -> str:
    """
    GPT用のプロンプト文を構成（PFC実績・目標・体重データ含む）
    """
    # 食事（meal_with_basis）の整形
    meal = meal_data["data"][0]  # 1日分のみ前提
    actual = meal.get("actual", {})
    target = meal.get("target", {})

    # 体重（anthropometric）の整形
    weight = body_data["data"][0].get("weight") if body_data.get("data") else None

    prompt = (
        f"昨日の食事の栄養バランスについてアドバイスをください。\n\n"
        f"【実績】\n"
        f"たんぱく質：{actual.get('protein')}g\n"
        f"脂質：{actual.get('fat')}g\n"
        f"炭水化物：{actual.get('carbohydrate')}g\n"
        f"カロリー：{actual.get('calories')}kcal\n\n"
        f"【目標】\n"
        f"たんぱく質：{target.get('protein')}g\n"
        f"脂質：{target.get('fat')}g\n"
        f"炭水化物：{target.get('carbohydrate')}g\n"
        f"カロリー：{target.get('calories')}kcal\n\n"
        f"【体重】\n{weight}kg\n\n"
        f"指導者として、丁寧で前向きなアドバイスをお願いします。"
    )
    return prompt


def generate_advice_for_unreplied():
    """
    未返信のユーザーリクエストに対して、CalomealデータからGPTでアドバイス生成＆保存
    """
    requests = get_unreplied_requests()
    if not requests:
        print("✅ 未返信リクエストはありません。")
        return

    access_token = refresh_access_token()

    for req in requests:
        print(f"🎯 処理中 user_id={req.user_id} timestamp={req.timestamp}")

        # Calomeal用の日付（yyyy-mm-dd）
        dt = datetime.fromisoformat(req.timestamp)
        date_str = dt.strftime("%Y-%m-%d")

        try:
            meal_data = get_meal_with_basis(access_token, date_str, date_str)
            body_data = get_anthropometric_data(access_token, date_str, date_str)

            prompt = format_prompt(meal_data, body_data)
            advice_text = generate_advice_by_prompt(prompt)

            update_advice_text(req.user_id, req.timestamp, advice_text)
            time.sleep(1)  # API過負荷防止のため小休止（任意）

        except Exception as e:
            print(f"❌ {req.user_id} のアドバイス生成失敗:", e)


if __name__ == "__main__":
    generate_advice_for_unreplied()

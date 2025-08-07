from utils.db import get_unreplied_requests, update_advice_text
from utils.caromil import get_meal_with_basis, get_anthropometric_data
from utils.gpt_utils import generate_advice_by_prompt

from datetime import datetime, timedelta
import time


def get_target_date_from_timestamp(timestamp: str) -> str:
    """
    タイムスタンプから「分析対象の日付（YYYY/MM/DD）」を決定
    15時を境に、前日 or 当日を返す
    """
    dt = datetime.fromisoformat(timestamp)
    if dt.hour < 15:
        target_date = dt.date() - timedelta(days=1)
    else:
        target_date = dt.date()
    return target_date.strftime("%Y/%m/%d")


def format_prompt(meal_data: dict, body_data: dict, target_date: str) -> str:
    """
    GPT用のプロンプト文を構成（PFC実績・目標・体重データ含む）
    指定された日付でのアドバイス
    """
    meal_list = meal_data.get("result", {}).get("meal_with_basis", [])
    if not meal_list:
        raise ValueError("meal_with_basis データが存在しません")
    meal = meal_list[0]

    actual = meal.get("meal_histories_summary", {}).get("all", {})
    target = meal.get("basis", {}).get("all", {})

    body_list = body_data.get("result", [])
    weight = None
    if body_list and isinstance(body_list, list) and len(body_list) > 0:
        weight = body_list[0].get("weight")

    prompt = (
        f"{target_date} の食事の栄養バランスについて、実績と目標の差を踏まえたアドバイスを作成してください。\n\n"
        f"【実績（実際に摂取した量）】\n"
        f"たんぱく質：{actual.get('protein', '不明')}g\n"
        f"脂質：{actual.get('lipid', '不明')}g\n"
        f"炭水化物：{actual.get('carbohydrate', '不明')}g\n"
        f"カロリー：{actual.get('calorie', '不明')}kcal\n\n"
        f"【目標（アプリに設定された値）】\n"
        f"たんぱく質：{target.get('protein', '不明')}g\n"
        f"脂質：{target.get('lipid', '不明')}g\n"
        f"炭水化物：{target.get('carbohydrate', '不明')}g\n"
        f"カロリー：{target.get('calorie', '不明')}kcal\n\n"
        f"【体重】\n{weight or '不明'}kg\n\n"
        f"● 実績と目標の差をもとに、「良い点」と「改善提案」に分けてください。\n"
        f"● 食事のデータ以外に仮定は加えず、実績ベースで丁寧かつ前向きなアドバイスをしてください。"
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

        try:
            target_date = get_target_date_from_timestamp(req.timestamp)

            meal_data = get_meal_with_basis(req.user_id, target_date, target_date)
            body_data = get_anthropometric_data(req.user_id, target_date, target_date)

            prompt = format_prompt(meal_data, body_data, target_date)
            advice_text = generate_advice_by_prompt(prompt)

            update_advice_text(req.user_id, req.timestamp, advice_text)

            time.sleep(1)

        except Exception as e:
            print(f"❌ {req.user_id} のアドバイス生成失敗:", e)


if __name__ == "__main__":
    generate_advice_for_unreplied()

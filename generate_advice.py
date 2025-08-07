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

    # 実績値（meal_histories_summary → all）
    actual = meal.get("meal_histories_summary", {}).get("all", {})
    # 目標値（basis → all）
    target = meal.get("basis", {}).get("all", {})

    # 体重データの取得（最新の1件を使用）
    body_list = body_data.get("result", [])
    weight = None
    if body_list and isinstance(body_list, list) and len(body_list) > 0:
        weight = body_list[0].get("weight")

    # プロンプト組み立て
    prompt = (
        f"昨日の食事の栄養バランスについて、実績と目標の差を踏まえたアドバイスを作成してください。\n\n"
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

        # Calomeal APIの要求形式（YYYY/MM/DD）
        dt = datetime.fromisoformat(req.timestamp)
        date_str = dt.strftime("%Y/%m/%d")

        try:
            # Calomeal APIからデータ取得
            meal_data = get_meal_with_basis(req.user_id, date_str, date_str)
            body_data = get_anthropometric_data(req.user_id, date_str, date_str)

            # プロンプト生成とGPT呼び出し
            prompt = format_prompt(meal_data, body_data)
            advice_text = generate_advice_by_prompt(prompt)

            # アドバイスをDBに保存
            update_advice_text(req.user_id, req.timestamp, advice_text)

            # API過負荷対策の小休止
            time.sleep(1)

        except Exception as e:
            print(f"❌ {req.user_id} のアドバイス生成失敗:", e)


if __name__ == "__main__":
    generate_advice_for_unreplied()

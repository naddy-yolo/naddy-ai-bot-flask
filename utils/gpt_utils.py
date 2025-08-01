import os
import openai

def classify_request_type(message_text: str) -> str:
    """
    ユーザーの自由入力メッセージから、request_type を自動判別する。
    使用モデル：gpt-4o
    分類カテゴリ：
        - meal_feedback
        - weight_report
        - workout_question
        - system_question
        - other
    """
    try:
        print("✅ gpt_utils.py: classify_request_type 開始")
        print("📨 message_text:", message_text)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY が設定されていません")
            return "other"

        openai.api_key = api_key

        system_prompt = (
            "あなたはダイエット指導アシスタントです。"
            "以下のユーザーの入力内容をもとに、その意図を次のいずれかに分類してください。\n\n"
            "分類ラベルは以下の5つです：\n"
            "1. meal_feedback（食事に関する報告や相談）\n"
            "2. weight_report（体重・体脂肪の報告）\n"
            "3. workout_question（運動や筋トレに関する質問）\n"
            "4. system_question（アプリや記録方法などシステム関連の質問）\n"
            "5. other（上記に当てはまらないもの）\n\n"
            "回答は必ず、分類ラベル名のみで答えてください。"
        )

        print("✅ ChatCompletion.create 実行前")
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0
        )
        print("✅ ChatCompletion.create 実行完了")

        result = response.choices[0].message.content.strip()
        print("🎯 分類結果:", result)
        return result

    except Exception as e:
        print("❌ classify_request_type error:", str(e))
        return "other"

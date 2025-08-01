import os
import traceback
from openai import OpenAI

# 🔍 現在のファイル内容をログ出力（デバッグ用）
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示開始")
with open(__file__, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:30]):
        print(f"{i+1:02d}: {line.rstrip()}")
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示終了")

# ✅ 自動的に設定される proxy 環境変数を明示的に除去
for proxy_key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(proxy_key, None)

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

        # ✅ OpenAIクライアントを初期化（v1.47.0）
        client = OpenAI(api_key=api_key)

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

        print("✅ client.chat.completions.create 実行前")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0
        )
        print("✅ client.chat.completions.create 実行完了")

        result = response.choices[0].message.content.strip()
        print("🎯 分類結果:", result)
        return result

    except Exception as e:
        print("❌ classify_request_type error:", str(e))
        print("📛 スタックトレース:")
        print(traceback.format_exc())
        return "other"

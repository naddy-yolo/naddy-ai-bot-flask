import os
import traceback
from openai import Client

# 🔍 現在のファイル内容をログ出力（Render側のデプロイ検証用）
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示開始")
with open(__file__, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:30]):
        print(f"{i+1:02d}: {line.rstrip()}")
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示終了")

# ✅ 自動的に設定される proxy 環境変数を明示的に除去（念のため）
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

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment variables.")

        client = Client(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはメッセージの分類AIです。次の選択肢の中からもっとも適切な分類を返してください："
                        "[meal_feedback, weight_report, workout_question, system_question, other]。"
                        "分類名のみをJSON形式で出力してください。"
                    ),
                },
                {"role": "user", "content": message_text},
            ],
            response_format="json",
            temperature=0.0,
        )

        category = response.choices[0].message.content.strip()
        print("✅ 分類結果:", category)
        return category

    except Exception as e:
        print("❌ classify_request_type error:", e)
        print("📛 スタックトレース:")
        traceback.print_exc()
        return "other"

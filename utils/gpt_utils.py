import os
import traceback
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper

# 🔍 デバッグ用：コード内容表示（Render検証用）
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示開始")
with open(__file__, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:30]):
        print(f"{i+1:02d}: {line.rstrip()}")
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示終了")

# ✅ proxy変数を削除（OpenAIエラー対策）
for proxy_key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(proxy_key, None)

# ✅ OpenAI APIキー取得
api_key = os.getenv("OPENAI_API_KEY")

# ✅ 明示的なクライアント指定（proxies対策）
http_client = SyncHttpxClientWrapper(
    base_url="https://api.openai.com/v1",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=600,
    follow_redirects=True,
)

def classify_request_type(message_text: str) -> str:
    """
    ユーザーの自由入力メッセージから request_type を自動判別する。
    GPT-4oを使い、以下のカテゴリのいずれかを返す：
        - meal_feedback（食事に関する報告・質問）
        - weight_report（体重に関する報告）
        - workout_question（運動に関する質問）
        - system_question（Botや操作に関する問い合わせ）
        - other（上記に該当しないもの）
    """
    try:
        print("✅ gpt_utils.py: classify_request_type 開始")
        print("📨 message_text:", message_text)

        # ✅ 食事分析ボタンなどテキスト判定で固定分類
        if "食事分析" in message_text:
            print("🔍 固定分類: meal_feedback")
            return "meal_feedback"
        if "体重報告" in message_text:
            print("🔍 固定分類: weight_report")
            return "weight_report"
        if "運動質問" in message_text:
            print("🔍 固定分類: workout_question")
            return "workout_question"

        # ✅ 通常の自由入力はGPTに分類させる
        client = OpenAI(http_client=http_client)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "ユーザーからの自由入力メッセージを以下の5つに分類して、"
                        "該当するカテゴリ名だけを出力してください（他の出力は禁止）:\n"
                        "- meal_feedback\n- weight_report\n- workout_question\n"
                        "- system_question\n- other"
                    ),
                },
                {"role": "user", "content": message_text},
            ],
            temperature=0,
            max_tokens=10,
        )

        category = response.choices[0].message.content.strip()
        print("✅ 分類結果:", category)
        return category

    except Exception as e:
        print("❌ classify_request_type error:", e)
        print("📛 スタックトレース:")
        traceback.print_exc()
        return "other"

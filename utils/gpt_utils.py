import os
import traceback
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper

# 🔍 現在のファイル内容をログ出力（Render側のデプロイ検証用）
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示開始")
with open(__file__, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:30]):
        print(f"{i+1:02d}: {line.rstrip()}")
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示終了")

# ✅ 自動的に設定される proxy 環境変数を明示的に除去
for proxy_key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(proxy_key, None)

# ✅ 環境変数から OpenAI API キー取得
api_key = os.getenv("OPENAI_API_KEY")

# ✅ 手動で http クライアントを構築して proxies 回避
http_client = SyncHttpxClientWrapper(
    base_url="https://api.openai.com/v1",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=600,
    follow_redirects=True,
)

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

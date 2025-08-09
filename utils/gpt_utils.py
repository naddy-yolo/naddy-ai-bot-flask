# utils/gpt_utils.py
import os
import traceback
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper
from utils.formatting import format_daily_report  # 整形関数

# 🔍 デバッグ用：コード内容表示（Render検証用）
print("🔍 DEBUG: gpt_utils.py 現在のコード内容表示開始")
try:
    with open(__file__, "r") as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:30]):
            print(f"{i+1:02d}: {line.rstrip()}")
except Exception as _e:
    # 実行環境によっては __file__ を開けない場合があるため無視
    pass
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

# =====================================================
# 分類関数
# =====================================================
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

        # 固定分類（キーワードマッチ）
        if "食事分析" in message_text:
            return "meal_feedback"
        if "体重" in message_text:
            return "weight_report"
        if "運動" in message_text:
            return "workout_question"

        # GPTによる分類
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
        traceback.print_exc()
        return "other"


# =====================================================
# 共通プロンプト実行関数
# =====================================================
def generate_advice_by_prompt(prompt: str) -> str:
    """
    プロンプトを元に、GPTからアドバイス文を生成
    """
    try:
        print("🧠 generate_advice_by_prompt 開始")
        client = OpenAI(http_client=http_client)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはプロの女性向けダイエット指導者です。"
                        "体重やPFCバランス、栄養傾向を見て、"
                        "前向きかつ丁寧で信頼感のあるフィードバックを返してください。"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500,
        )
        advice = response.choices[0].message.content.strip()
        print("✅ アドバイス生成成功")
        return advice

    except Exception as e:
        print("❌ アドバイス生成エラー:", e)
        traceback.print_exc()
        return "アドバイスの生成に失敗しました。"


# =====================================================
# タイプ別アドバイス生成関数（キーdump＋失敗時のフォールバック出力あり）
# =====================================================
def generate_meal_advice(meal_data: dict, body_data: dict, date_str: str) -> str:
    """
    食事データ（meal_with_basis）と体組成データ（anthropometric）から食事アドバイスを生成
    - meal_data, body_data はAPIの生JSON
    - date_str は 'YYYY-MM-DD' or 'YYYY/MM/DD'（/receive-request の timestamp から）
    """
    # --- 形状ダンプ ---
    try:
        md0 = meal_data[0] if isinstance(meal_data, list) and meal_data else meal_data
        if isinstance(md0, dict):
            print("🔑 meal_with_basis keys:", list(md0.keys())[:50])
            print("🗓 meal_with_basis.date:", md0.get("date") or md0.get("target_date"))
            for k in ("meal_histories", "meals", "records", "foods"):
                if k in md0 and isinstance(md0[k], list):
                    print(f"🍽 meals candidate '{k}' length:", len(md0[k]))
                    if md0[k]:
                        print(f"🍽 {k}[0] keys:", list(md0[k][0].keys())[:50])
                    break
            if "basis" in md0:
                print("🎯 basis keys:", list(md0["basis"].keys()))
                if isinstance(md0["basis"].get("all"), dict):
                    print("🎯 basis.all keys:", list(md0["basis"]["all"].keys()))
            for k in ("goal", "targets", "summary", "totals", "meal_histories_summary"):
                if k in md0:
                    v = md0[k]
                    print(f"🧭 '{k}' type:", type(v).__name__)
                    if isinstance(v, dict):
                        print(f"🧭 {k} keys:", list(v.keys())[:50])
                        if k == "meal_histories_summary" and isinstance(v.get("all"), dict):
                            print("🧭 meal_histories_summary.all keys:", list(v["all"].keys())[:50])
        else:
            print("⚠️ meal_with_basis is not dict-like:", type(md0).__name__)
    except Exception as e:
        print("⚠️ meal_with_basis keys dump失敗:", e)

    try:
        if isinstance(body_data, dict):
            print("🔑 anthropometric wrapper keys:", list(body_data.keys())[:50])
            if isinstance(body_data.get("data"), list) and body_data["data"]:
                print("🔑 anthropometric[data][0] keys:", list(body_data["data"][0].keys())[:50])
        elif isinstance(body_data, list):
            print("🔑 anthropometric is list, length:", len(body_data))
            if body_data:
                print("🔑 anthropometric[0] keys:", list(body_data[0].keys())[:50])
        else:
            print("⚠️ anthropometric unexpected type:", type(body_data).__name__)
    except Exception as e:
        print("⚠️ anthropometric keys dump失敗:", e)
    # --- ここまでダンプ ---

    # 整形テキストを作成（失敗時はフォールバックでJSON文字列を渡す）
    try:
        formatted = format_daily_report(meal_data, body_data, date_str)
        print("📄 整形済みデータ:\n", formatted)
    except Exception as e:
        print("⚠️ format_daily_report 失敗:", e)
        formatted = (
            "【注意】整形に失敗したためJSONを直接使用します。\n\n"
            f"【食事データ(JSON)】\n{meal_data}\n\n"
            f"【体重・体脂肪データ(JSON)】\n{body_data}\n"
        )
        # ★ 失敗時のフォールバックもログ出力
        print("📄 整形フォールバック(JSONダンプ):\n", formatted)

    prompt = (
        "以下はクライアントの1日のデータです。"
        "女性向けダイエット指導として、まず良かった点→次に改善点→最後に明日の具体アクションの順で、"
        "簡潔かつ前向きにアドバイスしてください。\n\n"
        f"{formatted}\n"
    )
    return generate_advice_by_prompt(prompt)


def generate_workout_advice(message_text: str) -> str:
    """
    運動に関する質問へのアドバイスを生成
    """
    prompt = (
        "以下はクライアントからの運動に関する質問です。\n"
        "あなたはプロの女性向けダイエット・フィットネストレーナーとして、"
        "優しく、かつ根拠のあるアドバイスを返してください。\n\n"
        f"【質問】\n{message_text}\n"
    )
    return generate_advice_by_prompt(prompt)


def generate_operation_advice(message_text: str) -> str:
    """
    Botやアプリ操作に関する質問への回答を生成
    """
    prompt = (
        "以下はクライアントからのアプリやBotの操作に関する質問です。\n"
        "あなたはシンプルでわかりやすい回答を返してください。\n\n"
        f"【質問】\n{message_text}\n"
    )
    return generate_advice_by_prompt(prompt)


def generate_other_reply(message_text: str) -> str:
    """
    その他メッセージへの返信を生成
    """
    prompt = (
        "以下はクライアントからの一般的なメッセージです。\n"
        "あなたはナディとして、丁寧かつ親しみのある口調で返信してください。\n\n"
        f"【メッセージ】\n{message_text}\n"
    )
    return generate_advice_by_prompt(prompt)

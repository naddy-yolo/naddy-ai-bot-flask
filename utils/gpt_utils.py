# gpt_utils.py

import os
from openai import OpenAI

def classify_request_type(message_text: str) -> str:
    """
    ユーザーの自由入力メッセージから、request_type を自動判別する。
    例：食事のアドバイス、カロミルの使い方、運動の相談など。
    """
    try:
        system_prompt = (
            "あなたはダイエット指導アシスタントです。"
            "ユーザーからのメッセージを見て、その内容に応じて request_type を以下の中から1つ選んでください：\n"
            "・meal_analysis（食事に関する内容全般。カロミルAPI連携の食事分析依頼や、食事への質問・相談も含む）\n"
            "・calomeal_question（カロミルアプリの使い方・操作方法に関する内容）\n"
            "・workout_question（運動・ストレッチ・エクササイズなどに関する相談）\n"
            "・other（上記以外）\n"
            "該当する request_type を1単語のみで返してください。"
        )

        # OpenAIクライアントを関数内で初期化（Renderエラー回避）
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ],
            temperature=0
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("❌ classify_request_type error:", str(e))
        return "other"

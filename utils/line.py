# utils/line.py
import os
import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


class LineSendError(Exception):
    """LINE送信に失敗した時の例外"""
    pass


def send_line_message(user_id: str, text: str) -> None:
    """
    LINEのPush APIでテキストメッセージを送信する。
    環境変数 LINE_CHANNEL_ACCESS_TOKEN が必要。
    """
    if not CHANNEL_ACCESS_TOKEN:
        raise LineSendError("LINE_CHANNEL_ACCESS_TOKEN が未設定です。Renderの環境変数に追加してください。")

    if not user_id:
        raise LineSendError("user_id が空です。")

    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text[:5000] if text else ""
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(LINE_PUSH_URL, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        # LINEのエラーメッセージも含めて例外化
        raise LineSendError(f"LINE送信失敗: {resp.status_code} - {resp.text}")

# utils/line.py
import os
import requests
from typing import Dict, Any

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_PROFILE_URL_TMPL = "https://api.line.me/v2/bot/profile/{user_id}"


class LineSendError(Exception):
    """LINE送信に失敗した時の例外"""
    pass


class LineProfileError(Exception):
    """LINEプロフィール取得に失敗した時の例外"""
    pass


def _get_token() -> str:
    """
    毎回環境変数から取得（プロセス内でトークンが更新されても拾えるように）
    """
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise LineSendError("LINE_CHANNEL_ACCESS_TOKEN が未設定です。Render の環境変数に追加してください。")
    return token


def send_line_message(user_id: str, text: str) -> None:
    """
    LINEのPush APIでテキストメッセージを送信する。
    環境変数 LINE_CHANNEL_ACCESS_TOKEN が必要。
    """
    if not user_id:
        raise LineSendError("user_id が空です。")

    token = _get_token()
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
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(LINE_PUSH_URL, json=payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise LineSendError(f"LINE送信時にネットワークエラーが発生しました: {e}")

    if resp.status_code != 200:
        # LINEのエラーメッセージも含めて例外化
        raise LineSendError(f"LINE送信失敗: {resp.status_code} - {resp.text}")


def get_line_profile(user_id: str) -> Dict[str, Any]:
    """
    LINEのプロフィールAPIからユーザー情報を取得する。
    戻り値例:
      {
        "displayName": "ナディ",
        "userId": "Uxxxx",
        "pictureUrl": "https://...",
        "statusMessage": "..."
      }
    失敗時は LineProfileError を送出。
    """
    if not user_id:
        raise LineProfileError("user_id が空です。")

    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise LineProfileError("LINE_CHANNEL_ACCESS_TOKEN is not set")

    url = LINE_PROFILE_URL_TMPL.format(user_id=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise LineProfileError(f"プロフィール取得時にネットワークエラー: {e}")

    if resp.status_code == 200:
        try:
            return resp.json()
        except ValueError as e:
            raise LineProfileError(f"プロフィールのJSONパースに失敗: {e}")

    if resp.status_code in (401, 403):
        raise LineProfileError(f"Unauthorized ({resp.status_code}). トークンを確認してください。")

    if resp.status_code == 404:
        # ブロック / 友だち関係なし等
        raise LineProfileError("User not found (blocked or not a friend).")

    raise LineProfileError(f"LINEエラー {resp.status_code}: {resp.text}")

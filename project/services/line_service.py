from __future__ import annotations

import json
from urllib import error, request


LINE_PUSH_MESSAGE_URL = "https://api.line.me/v2/bot/message/push"


def notify_line(channel_access_token: str, recipient_id: str, message: str) -> None:
    """LINE Messaging API の push message でテキストを送信する。"""
    if not channel_access_token:
        raise RuntimeError("LINE channel access token is not configured.")
    if not recipient_id:
        raise RuntimeError("LINE recipient ID is not configured.")

    payload = json.dumps(
        {
            "to": recipient_id,
            "messages": [{"type": "text", "text": message}],
        }
    ).encode("utf-8")
    req = request.Request(
        LINE_PUSH_MESSAGE_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LINE returned status {resp.status}")
    except error.URLError as exc:
        raise RuntimeError(f"LINE notification failed: {exc}") from exc

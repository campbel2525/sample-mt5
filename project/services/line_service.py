from typing import Dict, Any, List, Optional
import requests


def send_line_broadcast(channel_access_token: str, texts: List[str]) -> Dict[str, Any]:
    """
    LINE Messaging API のブロードキャストメッセージで、
    友だち全員に同じメッセージを送る。

    Args:
        channel_access_token (str): チャネルアクセストークン（長期）
        texts (List[str]): 送信したいテキストメッセージのリスト

    Returns:
        Dict[str, Any]: レスポンス内容
    """
    url: str = "https://api.line.me/v2/bot/message/broadcast"

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {channel_access_token}",  # ★ Channel access token
        "Content-Type": "application/json",
    }

    messages: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": text,
        }
        for text in texts
    ]

    payload: Dict[str, Any] = {"messages": messages}

    # ★ ここは json=payload（data= じゃない）
    response: requests.Response = requests.post(url, headers=headers, json=payload)

    print("status_code:", response.status_code)
    print("response.text:", response.text)

    try:
        result: Dict[str, Any] = response.json()
    except ValueError:
        result = {
            "status_code": response.status_code,
            "body": response.text,
        }

    return result


def check_group_id(
    channel_access_token: str,
    group_id: str,
) -> Dict[str, Any]:
    """
    groupId が有効かどうかを /group/{groupId}/summary で確認する。
    200 が返れば OK、それ以外なら ID か参加状態に問題あり。
    """
    url: str = f"https://api.line.me/v2/bot/group/{group_id}/summary"

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {channel_access_token}",
    }

    response: requests.Response = requests.get(url, headers=headers, timeout=10)

    try:
        result: Dict[str, Any] = response.json()
    except ValueError:
        result = {
            "status_code": response.status_code,
            "body": response.text,
        }

    print("status_code:", response.status_code)
    print("response:", result)
    return result


def send_line_group_message(
    channel_access_token: str,
    group_id: str,
    texts: List[str],
) -> Dict[str, Any]:
    """
    特定の LINE グループ（groupId 指定）にメッセージを送信するロジック。

    Args:
        channel_access_token (str): LINE Messaging API のチャネルアクセストークン（長期）
        group_id (str): 送信先グループの groupId
        texts (List[str]): 送信したいテキストメッセージのリスト
                           要素ごとに1バブルとして送信される

    Returns:
        Dict[str, Any]: LINE Platform からのレスポンス内容
    """
    url: str = "https://api.line.me/v2/bot/message/push"

    # 認証ヘッダ
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }

    # メッセージ配列に整形
    messages: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": text,
        }
        for text in texts
    ]

    payload: Dict[str, Any] = {
        "to": group_id,  # ★ userId ではなく groupId を指定
        "messages": messages,
    }

    response: requests.Response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10,
    )

    # レスポンスを dict に整形
    try:
        result: Dict[str, Any] = response.json()
    except ValueError:
        result = {
            "status_code": response.status_code,
            "body": response.text,
        }

    # ステータスコードチェック（必要なら例外投げてもOK）
    if response.status_code != 200:
        print("LINE 送信時にエラーが発生しました:")
        print("status_code:", response.status_code)
        print("response body:", response.text)
        print(response)

    return result

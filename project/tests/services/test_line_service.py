import json
from unittest.mock import MagicMock, patch

import pytest

from services.line_service import LINE_PUSH_MESSAGE_URL, notify_line


@patch("services.line_service.request.urlopen")
def test_notify_line_sends_text_message(mock_urlopen: MagicMock) -> None:
    response = mock_urlopen.return_value.__enter__.return_value
    response.status = 200

    notify_line(
        channel_access_token="channel-token",
        recipient_id="recipient-id",
        message="LINE message",
    )

    req = mock_urlopen.call_args.args[0]
    assert req.full_url == LINE_PUSH_MESSAGE_URL
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer channel-token"
    assert json.loads(req.data) == {
        "to": "recipient-id",
        "messages": [{"type": "text", "text": "LINE message"}],
    }
    mock_urlopen.assert_called_once_with(req, timeout=10)


def test_notify_line_requires_channel_access_token() -> None:
    with pytest.raises(RuntimeError, match="channel access token"):
        notify_line("", "recipient-id", "LINE message")


def test_notify_line_requires_recipient_id() -> None:
    with pytest.raises(RuntimeError, match="recipient ID"):
        notify_line("channel-token", "", "LINE message")

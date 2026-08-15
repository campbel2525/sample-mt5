from unittest.mock import patch

from scripts.send_message import main, send_slack_message


@patch("scripts.send_message.notify_slack")
def test_send_slack_message(mock_notify_slack) -> None:
    send_slack_message("Slack message")

    assert mock_notify_slack.call_args.kwargs["message"] == "Slack message"

@patch("scripts.send_message.send_slack_message")
def test_main_sends_slack_message(mock_send_slack_message) -> None:
    result = main(["slack", "--message", "Slack message"])

    assert result == 0
    mock_send_slack_message.assert_called_once_with("Slack message")


@patch("scripts.send_message.send_line_message")
def test_main_sends_line_message(mock_send_line_message) -> None:
    result = main(["line", "--message", "LINE message"])

    assert result == 0
    mock_send_line_message.assert_called_once_with("LINE message")

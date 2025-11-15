"""Application settings using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MT5
    mt5_common_dir: str = "/mt5_common"
    mt5_cmd_file_name: str = "mt5_cmd.txt"
    mt5_resp_prefix: str = "mt5_resp_"

    # Slack
    slack_web_hook_url_moving_average_notification: str = ""

    # Debug / tooling
    debug_mode: bool = True
    debugpy_port: int = 5678

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s %(message)s"

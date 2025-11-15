import logging
from typing import Union

_LOGGER_INITIALIZED: bool

def _resolve_level(level: Union[int, str]) -> int: ...
def setup_logger(
    name: str,
    *,
    level: Union[int, str] = ...,
    fmt: str = ...,
) -> logging.Logger: ...

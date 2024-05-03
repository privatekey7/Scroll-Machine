from enum import Enum
from typing import Optional

from loguru import logger as loguru_logger
from telebot import TeleBot

from config import LOG_TO_TELEGRAM, TELEGRAM_BOT_TOKEN, TELEGRAM_IDS

# logs file path
LOGS_FILE_PATH = "data/logs/logs.log"


class LogType(Enum):
    SUCCESS = "🟢"
    ERROR = "🔴"
    INFO = "⚪️"
    DEBUG = "🔵"
    EXCEPTION = "❗️"
    WARNING = "🟠"


class Logger:
    def __init__(self) -> None:
        self.tg_logger = Logger._setup_telegram_bot()
        self.loguru_logger = loguru_logger
        Logger._configure_file_logging()

    def _log(self, log_type: LogType, msg: str, log_to_telegram: bool = False) -> None:
        if log_type is LogType.SUCCESS:
            self.loguru_logger.success(msg)
        elif log_type is LogType.ERROR:
            self.loguru_logger.error(msg)
        elif log_type is LogType.INFO:
            self.loguru_logger.info(msg)
        elif log_type is LogType.DEBUG:
            self.loguru_logger.debug(msg)
        elif log_type is LogType.EXCEPTION:
            self.loguru_logger.exception(msg)
        elif log_type is LogType.WARNING:
            self.loguru_logger.warning(msg)

        if LOG_TO_TELEGRAM and log_to_telegram:
            self.log_to_telegram(msg=msg, log_type=log_type)

    def success(self, msg: str, log_to_telegram: bool = False) -> None:
        self._log(log_type=LogType.SUCCESS, msg=msg, log_to_telegram=log_to_telegram)

    def info(self, msg: str, log_to_telegram: bool = False):
        self._log(log_type=LogType.INFO, msg=msg, log_to_telegram=log_to_telegram)

    def error(self, msg: str, log_to_telegram: bool = True) -> None:
        self._log(log_type=LogType.ERROR, msg=msg, log_to_telegram=log_to_telegram)

    def debug(self, msg: str, log_to_telegram: bool = False) -> None:
        self._log(log_type=LogType.DEBUG, msg=msg, log_to_telegram=log_to_telegram)

    def exception(self, msg: str, log_to_telegram: bool = False) -> None:
        self._log(log_type=LogType.EXCEPTION, msg=msg, log_to_telegram=log_to_telegram)

    def warning(self, msg: str, log_to_telegram: bool = False) -> None:
        self._log(log_type=LogType.WARNING, msg=msg, log_to_telegram=log_to_telegram)

    def log_to_telegram(self, log_type: LogType, msg: str) -> None:
        try:
            for id in TELEGRAM_IDS:
                self.tg_logger.send_message(chat_id=id, text=f"{log_type.value} {msg}")
        except Exception as e:
            self.loguru_logger.error(f"Telegram log failed with error: {e}")

    @staticmethod
    def _setup_telegram_bot() -> Optional[TeleBot]:
        return TeleBot(token=TELEGRAM_BOT_TOKEN, disable_web_page_preview=True) if LOG_TO_TELEGRAM else None

    @staticmethod
    def _configure_file_logging():
        loguru_logger.add(sink=LOGS_FILE_PATH)


logger = Logger()

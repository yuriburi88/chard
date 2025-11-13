from types import ModuleType
import sys


def _ensure_telegram_stubs() -> None:
    if "telegram" not in sys.modules:
        telegram_stub = ModuleType("telegram")
        telegram_stub.Bot = object  # placeholder; tests monkeypatch as needed
        sys.modules["telegram"] = telegram_stub

    if "telegram.error" not in sys.modules:
        telegram_error_stub = ModuleType("telegram.error")
        telegram_error_stub.TelegramError = Exception

        sys.modules["telegram.error"] = telegram_error_stub


_ensure_telegram_stubs()


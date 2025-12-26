"""Pytest configuration and shared fixtures."""

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


# Telegram stubs for testing without actual telegram package
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


# Fixtures directory path
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_rss_data() -> dict[str, Any]:
    """Load sample RSS feed data for testing."""
    with open(FIXTURES_DIR / "sample_rss_data.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_telegram_data() -> dict[str, Any]:
    """Load sample Telegram messages for testing."""
    with open(FIXTURES_DIR / "sample_telegram_data.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_articles() -> list[dict[str, Any]]:
    """Generate sample article data for testing."""
    return [
        {
            "title": "Bitcoin Hits New High",
            "content": "Bitcoin reached $100,000 today amid institutional buying.",
            "source": "CoinDesk",
            "published": "2024-12-25T10:00:00Z",
            "url": "https://example.com/btc-high",
        },
        {
            "title": "Ethereum ETF Approved",
            "content": "SEC approves spot Ethereum ETF applications.",
            "source": "The Block",
            "published": "2024-12-25T09:00:00Z",
            "url": "https://example.com/eth-etf",
        },
        {
            "title": "Fed Rate Decision",
            "content": "Federal Reserve holds rates steady, signals cuts in 2025.",
            "source": "Bloomberg",
            "published": "2024-12-25T08:00:00Z",
            "url": "https://example.com/fed-rates",
        },
    ]


@pytest.fixture
def sample_keywords() -> list[dict[str, Any]]:
    """Generate sample keyword data for testing."""
    return [
        {"keyword": "Bitcoin", "frequency": 25, "category": "crypto"},
        {"keyword": "Ethereum", "frequency": 18, "category": "crypto"},
        {"keyword": "Federal Reserve", "frequency": 12, "category": "macro"},
        {"keyword": "ETF", "frequency": 15, "category": "crypto"},
        {"keyword": "Interest Rate", "frequency": 10, "category": "macro"},
    ]


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Generate mock configuration for testing."""
    return {
        "collection_period": {
            "mode": "days_back",
            "days_back": 1,
            "recent_hours": 24,
        },
        "llm": {
            "model": "gemini-2.5-flash",
            "provider": "google",
            "max_tokens": 8000,
            "temperature": 0.1,
        },
        "output": {
            "top_keywords_count": 10,
            "summary_paragraphs": 4,
            "log_level": "INFO",
        },
        "narrative": {
            "enable_segmentation": True,
            "crypto_paragraphs": 2,
            "integrated_paragraphs": 3,
        },
    }

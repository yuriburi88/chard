import pytest
from datetime import datetime, timezone

from src.collectors.models import Article, CollectedItem


def test_article_to_collected_item_includes_metadata() -> None:
    article = Article(
        title="Sample Title",
        url="https://example.com/article",
        content="Article content goes here.",
        source="Example Source",
        published_at=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        source_type="rss",
        description="Summary text",
        author="Reporter",
        tags=["crypto", "market"]
    )

    item = article.to_collected_item()

    assert item.source_type == "rss"
    assert item.source_name == "Example Source"
    assert item.timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert item.text == "Article content goes here."
    assert item.metadata["title"] == "Sample Title"
    assert item.metadata["url"] == "https://example.com/article"
    assert item.metadata["description"] == "Summary text"
    # author는 프로젝트 목적에 불필요하므로 제외됨
    assert "author" not in item.metadata
    assert item.metadata["tags"] == ["crypto", "market"]


def test_collected_item_round_trip() -> None:
    original = CollectedItem(
        source_type="telegram",
        source_name="Crypto Channel",
        timestamp=datetime(2025, 1, 2, 9, 30, tzinfo=timezone.utc),
        text="Important telegram update.",
        metadata={
            "telegram_message_ids": [101, 102],
            "telegram_message_count": 2,
        },
    )

    data = original.to_dict()
    restored = CollectedItem.from_dict(data)

    assert restored == original




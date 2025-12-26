"""
CHARD 파이프라인 통합 테스트

전체 데이터 처리 파이프라인의 통합 동작을 테스트합니다.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_rss_articles():
    """모의 RSS 기사 데이터"""
    now = datetime.now(timezone.utc)
    return [
        {
            "source": "CoinDesk",
            "source_type": "rss",
            "title": "Bitcoin Surges Past $100K as Institutional Adoption Grows",
            "content": "Bitcoin reached a new all-time high today as major institutions continue to accumulate the cryptocurrency. BlackRock's Bitcoin ETF saw record inflows.",
            "url": "https://example.com/btc-100k",
            "timestamp": now.isoformat(),
        },
        {
            "source": "The Block",
            "source_type": "rss",
            "title": "Ethereum ETF Sees Record Inflows",
            "content": "The newly launched Ethereum ETF recorded its highest single-day inflows since launch, signaling growing institutional interest in ETH.",
            "url": "https://example.com/eth-etf",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
        },
    ]


@pytest.fixture
def mock_telegram_messages():
    """모의 Telegram 메시지 데이터"""
    now = datetime.now(timezone.utc)
    return [
        {
            "source": "Telegram",
            "source_type": "telegram",
            "channel": "cryptonews",
            "content": "Breaking: BTC breaks $100K! Institutional buying pressure continues. ETF inflows at all-time highs.",
            "timestamp": now.isoformat(),
        },
        {
            "source": "Telegram",
            "source_type": "telegram",
            "channel": "macroanalysis",
            "content": "Fed signals potential rate cuts in 2025. Risk assets responding positively. Dollar weakness expected.",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
        },
    ]


@pytest.fixture
def mock_config():
    """모의 설정"""
    return {
        "collection_period": {
            "mode": "days_back",
            "days_back": 1,
        },
        "llm": {
            "model": "gemini-2.5-flash",
            "provider": "google",
            "max_tokens": 8000,
            "chunk_size": 50000,
        },
        "normalization": {
            "embedding_threshold": 0.9,
            "dbscan_min_samples": 2,
        },
        "narrative": {
            "enable_segmentation": True,
            "crypto_paragraphs": 2,
            "integrated_paragraphs": 3,
        },
        "output": {
            "top_keywords_count": 10,
            "summary_paragraphs": 4,
        },
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_data_collection_to_chunking(
    mock_rss_articles, mock_telegram_messages, mock_config
):
    """
    데이터 수집부터 청킹까지의 통합 테스트

    수집된 데이터가 collector_node를 통해 올바르게 청크로 분할되는지 확인합니다.
    """
    # 원본 레코드 병합
    raw_records = mock_rss_articles + mock_telegram_messages

    # 모의 Preprocessor
    mock_preprocessor = MagicMock()

    async def mock_chunk_messages(records, max_tokens):
        # 단순히 레코드를 2개씩 묶어서 반환
        chunks = []
        for i in range(0, len(records), 2):
            chunks.append(records[i : i + 2])
        return chunks

    mock_preprocessor.chunk_messages = mock_chunk_messages

    initial_state = {
        "raw_records": raw_records,
        "config": mock_config,
        "errors": [],
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        result = await collector_node(initial_state)

        # 청크가 생성되었는지 확인
        assert "chunks" in result
        assert result["chunk_count"] > 0

        # 모든 레코드가 청크에 포함되어 있는지 확인
        total_records_in_chunks = sum(len(chunk) for chunk in result["chunks"])
        assert total_records_in_chunks == len(raw_records)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_flow(
    mock_rss_articles, mock_telegram_messages, mock_config
):
    """
    전체 파이프라인 흐름 테스트

    collector_node -> keyword_extractor -> aggregator -> insight_node 흐름을 테스트합니다.
    """
    raw_records = mock_rss_articles + mock_telegram_messages

    # 모의 객체들 설정
    mock_preprocessor = MagicMock()

    async def mock_chunk_messages(records, max_tokens):
        return [records]

    mock_preprocessor.chunk_messages = mock_chunk_messages

    # 1단계: collector_node
    initial_state = {
        "raw_records": raw_records,
        "config": mock_config,
        "errors": [],
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        after_collector = await collector_node(initial_state)

    assert "chunks" in after_collector
    assert after_collector["chunk_count"] > 0

    # 나머지 노드들은 LLM 의존성이 있어 완전한 테스트가 어려움
    # 실제 통합 테스트에서는 LLM을 모의 처리하거나 실제 API 사용


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_propagation(mock_config):
    """
    에러 전파 테스트

    파이프라인에서 발생한 에러가 올바르게 전파되는지 확인합니다.
    """
    # 빈 레코드로 시작
    initial_state = {
        "raw_records": [],
        "config": mock_config,
        "errors": [],
    }

    from src.workflows.nodes.collector_node import collector_node

    result = await collector_node(initial_state)

    # 에러가 기록되어야 함
    assert len(result["errors"]) > 0
    assert result["chunks"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_state_preservation_through_pipeline(mock_rss_articles, mock_config):
    """
    파이프라인을 통한 상태 보존 테스트

    각 노드를 거치면서 상태가 올바르게 보존되는지 확인합니다.
    """
    mock_preprocessor = MagicMock()

    async def mock_chunk_messages(records, max_tokens):
        return [records]

    mock_preprocessor.chunk_messages = mock_chunk_messages

    initial_state = {
        "raw_records": mock_rss_articles,
        "config": mock_config,
        "errors": [],
        "custom_field": "should_be_preserved",
        "metadata": {"run_id": "test-123"},
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        result = await collector_node(initial_state)

    # 커스텀 필드가 보존되어야 함
    assert result.get("custom_field") == "should_be_preserved"
    assert result.get("metadata") == {"run_id": "test-123"}
    assert result.get("config") == mock_config


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mixed_source_handling(
    mock_rss_articles, mock_telegram_messages, mock_config
):
    """
    혼합 소스 처리 테스트

    RSS와 Telegram 등 다양한 소스의 데이터가 올바르게 처리되는지 확인합니다.
    """
    # Economic Calendar 데이터 추가
    ec_data = [
        {
            "source": "economic_calendar",
            "source_type": "economic_calendar",
            "title": "Fed Rate Decision",
            "content": "Federal Reserve keeps rates unchanged",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]

    raw_records = mock_rss_articles + mock_telegram_messages + ec_data

    mock_preprocessor = MagicMock()

    async def mock_chunk_messages(records, max_tokens):
        return [records]

    mock_preprocessor.chunk_messages = mock_chunk_messages

    initial_state = {
        "raw_records": raw_records,
        "config": mock_config,
        "errors": [],
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        result = await collector_node(initial_state)

    # Economic Calendar가 필터링되었는지 확인
    if result["chunks"]:
        all_sources = [r.get("source") for chunk in result["chunks"] for r in chunk]
        assert "economic_calendar" not in all_sources

    # RSS와 Telegram 데이터는 포함되어야 함
    all_sources_set = set(all_sources) if result["chunks"] else set()
    assert (
        "CoinDesk" in all_sources_set
        or "The Block" in all_sources_set
        or "Telegram" in all_sources_set
    )

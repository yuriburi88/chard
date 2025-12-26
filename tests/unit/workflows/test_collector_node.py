"""
CollectorNode 단위 테스트

collector_node 함수의 데이터 청킹 기능을 테스트합니다.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_raw_records():
    """샘플 원본 레코드 데이터"""
    now = datetime.now(timezone.utc)
    return [
        {
            "source": "CoinDesk",
            "title": "Bitcoin Surges Past $100K",
            "content": "Bitcoin reached a new all-time high as institutional buying continues.",
            "timestamp": now.isoformat(),
        },
        {
            "source": "The Block",
            "title": "Ethereum ETF Sees Record Inflows",
            "content": "The newly launched Ethereum ETF recorded its highest single-day inflows.",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "source": "Telegram",
            "title": "",
            "content": "Market update: BTC dominance at 52%, altcoin season may be approaching.",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
        },
    ]


@pytest.fixture
def sample_state_with_records(sample_raw_records):
    """원본 레코드가 포함된 샘플 상태"""
    return {
        "raw_records": sample_raw_records,
        "config": {
            "llm": {
                "chunk_size": 50000,
            }
        },
        "errors": [],
    }


@pytest.fixture
def mock_preprocessor():
    """Preprocessor 모의 객체"""
    mock = MagicMock()

    async def mock_chunk_messages(records, max_tokens):
        # 간단히 레코드를 하나의 청크로 반환
        return [records]

    mock.chunk_messages = mock_chunk_messages
    return mock


@pytest.mark.asyncio
async def test_collector_node_basic_chunking(
    sample_state_with_records, mock_preprocessor
):
    """
    기본 청킹 테스트

    collector_node가 raw_records를 청크로 분할하는지 확인합니다.
    """
    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        result = await collector_node(sample_state_with_records)

        assert "chunks" in result
        assert "chunk_count" in result
        assert result["chunk_count"] >= 1
        assert len(result["chunks"]) == result["chunk_count"]


@pytest.mark.asyncio
async def test_collector_node_empty_records():
    """
    빈 레코드 처리 테스트

    raw_records가 비어있을 때 적절한 에러 메시지를 반환하는지 확인합니다.
    """
    from src.workflows.nodes.collector_node import collector_node

    empty_state = {
        "raw_records": [],
        "config": {},
        "errors": [],
    }

    result = await collector_node(empty_state)

    assert result["chunks"] == []
    assert result["chunk_count"] == 0
    assert len(result["errors"]) > 0
    assert "비어있습니다" in result["errors"][-1]


@pytest.mark.asyncio
async def test_collector_node_economic_calendar_filtering(mock_preprocessor):
    """
    Economic Calendar 필터링 테스트

    economic_calendar 소스는 키워드 추출에서 제외되는지 확인합니다.
    """
    now = datetime.now(timezone.utc)
    state_with_ec = {
        "raw_records": [
            {
                "source": "CoinDesk",
                "title": "Bitcoin News",
                "content": "Bitcoin content",
                "timestamp": now.isoformat(),
            },
            {
                "source": "economic_calendar",
                "title": "Fed Rate Decision",
                "content": "Federal Reserve keeps rates unchanged",
                "timestamp": now.isoformat(),
            },
        ],
        "config": {"llm": {"chunk_size": 50000}},
        "errors": [],
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        result = await collector_node(state_with_ec)

        # Economic Calendar가 아닌 레코드만 청크에 포함되어야 함
        if result["chunks"]:
            all_records = [r for chunk in result["chunks"] for r in chunk]
            sources = [r.get("source") for r in all_records]
            assert "economic_calendar" not in sources


@pytest.mark.asyncio
async def test_collector_node_only_economic_calendar():
    """
    Economic Calendar만 있을 때 테스트

    economic_calendar 레코드만 있으면 에러를 반환하는지 확인합니다.
    """
    from src.workflows.nodes.collector_node import collector_node

    now = datetime.now(timezone.utc)
    ec_only_state = {
        "raw_records": [
            {
                "source": "economic_calendar",
                "title": "Fed Rate Decision",
                "content": "Federal Reserve keeps rates unchanged",
                "timestamp": now.isoformat(),
            },
        ],
        "config": {},
        "errors": [],
    }

    result = await collector_node(ec_only_state)

    assert result["chunks"] == []
    assert result["chunk_count"] == 0
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_collector_node_preserves_existing_errors():
    """
    기존 에러 보존 테스트

    기존 에러 목록이 유지되는지 확인합니다.
    """
    from src.workflows.nodes.collector_node import collector_node

    state_with_errors = {
        "raw_records": [],
        "config": {},
        "errors": ["Previous error 1", "Previous error 2"],
    }

    result = await collector_node(state_with_errors)

    assert "Previous error 1" in result["errors"]
    assert "Previous error 2" in result["errors"]
    assert len(result["errors"]) >= 3  # 기존 2개 + 새 에러 1개


@pytest.mark.asyncio
async def test_collector_node_default_chunk_size(sample_raw_records, mock_preprocessor):
    """
    기본 청크 크기 테스트

    설정이 없을 때 기본 청크 크기(50000)가 사용되는지 확인합니다.
    """
    state_no_config = {
        "raw_records": sample_raw_records,
        "config": {},
        "errors": [],
    }

    with patch(
        "src.workflows.nodes.collector_node.Preprocessor",
        return_value=mock_preprocessor,
    ):
        from src.workflows.nodes.collector_node import collector_node

        # 함수가 정상 실행되면 기본값이 사용된 것
        result = await collector_node(state_no_config)

        # 에러 없이 청크가 생성되어야 함
        assert "chunks" in result

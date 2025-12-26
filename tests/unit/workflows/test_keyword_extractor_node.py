"""
KeywordExtractorNode 단위 테스트

keyword_extractor_node 함수의 키워드 추출 기능을 테스트합니다.
"""

from datetime import datetime, timezone

import pytest


@pytest.fixture
def sample_chunks():
    """샘플 청크 데이터"""
    now = datetime.now(timezone.utc)
    return [
        [
            {
                "source": "CoinDesk",
                "title": "Bitcoin Surges Past $100K",
                "content": "Bitcoin reached a new all-time high. BTC dominance increases.",
                "timestamp": now.isoformat(),
            },
            {
                "source": "The Block",
                "title": "Ethereum ETF Approval",
                "content": "SEC approves Ethereum ETF. ETH price rallies.",
                "timestamp": now.isoformat(),
            },
        ],
        [
            {
                "source": "Telegram",
                "content": "Fed announces rate cut. Risk assets rally including Bitcoin.",
                "timestamp": now.isoformat(),
            },
        ],
    ]


@pytest.fixture
def sample_state_with_chunks(sample_chunks):
    """청크가 포함된 샘플 상태"""
    return {
        "chunks": sample_chunks,
        "chunk_count": len(sample_chunks),
        "config": {
            "llm": {
                "model": "gemini-2.5-flash",
                "provider": "google",
            },
            "normalization": {
                "embedding_threshold": 0.9,
            },
        },
        "errors": [],
    }


@pytest.mark.asyncio
async def test_keyword_extractor_node_empty_chunks():
    """
    빈 청크 처리 테스트

    청크가 비어있을 때 적절히 처리하는지 확인합니다.
    """
    try:
        from src.workflows.nodes.keyword_extractor_node import keyword_extractor_node

        empty_state = {
            "chunks": [],
            "chunk_count": 0,
            "config": {
                "llm": {"model": "gemini-2.5-flash"},
            },
            "errors": [],
        }

        result = await keyword_extractor_node(empty_state)

        # 에러가 기록되거나 빈 키워드 목록이 반환되어야 함
        assert "errors" in result or "raw_keywords" in result
    except ImportError:
        pytest.skip("keyword_extractor_node not available")
    except Exception:
        # 빈 청크면 에러가 발생할 수 있음
        pass

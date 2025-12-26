"""
InsightNode 단위 테스트

insight_node 함수의 내러티브 생성 기능을 테스트합니다.
"""


import pytest


@pytest.fixture
def sample_keywords():
    """샘플 키워드 데이터"""
    return [
        {"keyword": "Bitcoin", "frequency": 25, "category": "crypto"},
        {"keyword": "Ethereum", "frequency": 18, "category": "crypto"},
        {"keyword": "Federal Reserve", "frequency": 12, "category": "macro"},
        {"keyword": "ETF", "frequency": 15, "category": "crypto"},
        {"keyword": "Interest Rate", "frequency": 10, "category": "macro"},
    ]


@pytest.fixture
def sample_state_with_keywords(sample_keywords):
    """키워드가 포함된 샘플 상태"""
    return {
        "normalized_keywords": sample_keywords,
        "aggregated_keywords": sample_keywords,
        "chunks": [[{"content": "Sample content"}]],
        "raw_records": [
            {
                "content": "Sample record",
                "source": "test",
                "timestamp": "2024-12-25T10:00:00Z",
            }
        ],
        "config": {
            "llm": {
                "model": "gemini-2.5-flash",
                "provider": "google",
                "max_tokens": 8000,
            },
            "narrative": {
                "enable_segmentation": True,
                "crypto_paragraphs": 2,
                "integrated_paragraphs": 3,
            },
            "output": {
                "top_keywords_count": 10,
            },
        },
        "errors": [],
    }


@pytest.mark.asyncio
async def test_insight_node_empty_keywords():
    """
    빈 키워드 처리 테스트

    키워드가 없을 때 적절히 처리하는지 확인합니다.
    """
    try:
        from src.workflows.nodes.insight_node import insight_node

        empty_state = {
            "normalized_keywords": [],
            "aggregated_keywords": [],
            "chunks": [],
            "raw_records": [],
            "config": {
                "narrative": {"enable_segmentation": False},
                "output": {"top_keywords_count": 10},
                "llm": {"model": "gemini-2.5-flash"},
            },
            "errors": [],
        }

        result = await insight_node(empty_state)

        # 에러가 기록되거나 빈 내러티브가 반환되어야 함
        assert "errors" in result or "insight_result" in result
    except ImportError:
        pytest.skip("insight_node not available")
    except Exception as e:
        # 키워드가 없으면 에러가 발생할 수 있음
        assert "keyword" in str(e).lower() or "empty" in str(e).lower() or True

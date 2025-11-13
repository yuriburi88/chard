"""
AggregatorNode 보조 유틸리티에 대한 단위 테스트.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Sequence

import importlib
import pytest

aggregator_module = importlib.import_module("src.workflows.nodes.aggregator_node")
_select_top_keywords = aggregator_module._select_top_keywords


class TestSelectTopKeywords:
    """
    `_select_top_keywords` 함수의 동작을 검증합니다.
    """

    @staticmethod
    def test_returns_ranked_keywords_sorted_descending() -> None:
        """
        점수를 기준으로 내림차순 정렬되고 순위가 부여되는지 확인합니다.
        """
        scored_keywords = [
            {"term": "beta", "score": 12.0},
            {"term": "alpha", "score": 40.0},
            {"term": "gamma", "score": 8.0},
        ]

        result = _select_top_keywords(scored_keywords, limit=2, include_ties=False)

        assert [item["term"] for item in result] == ["alpha", "beta"]
        assert [item["rank"] for item in result] == [1, 2]

    @staticmethod
    def test_include_ties_extends_selection() -> None:
        """
        동일 점수로 인해 순위가 동점일 때 추가 항목이 포함되는지 확인합니다.
        """
        scored_keywords = [
            {"term": "alpha", "score": 10.0},
            {"term": "beta", "score": 9.0},
            {"term": "gamma", "score": 9.0},
            {"term": "delta", "score": 7.0},
        ]

        result = _select_top_keywords(scored_keywords, limit=2, include_ties=True)

        assert [item["term"] for item in result] == ["alpha", "beta", "gamma"]
        assert [item["rank"] for item in result] == [1, 2, 2]

    @staticmethod
    def test_raises_error_on_invalid_limit() -> None:
        """
        limit 값이 1 미만일 때 예외를 발생시키는지 검증합니다.
        """
        with pytest.raises(ValueError):
            _select_top_keywords([{"term": "alpha", "score": 1.0}], limit=0, include_ties=False)


@pytest.mark.asyncio
async def test_aggregator_node_applies_llm_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    LLM 검증 결과가 최종 상위 키워드에 반영되는지 확인합니다.
    """

    async def fake_cluster(
        keywords: Sequence[Dict[str, Any]],
        **_: Any,
    ) -> list[Dict[str, Any]]:
        enriched: list[Dict[str, Any]] = []
        for index, keyword in enumerate(keywords):
            keyword_copy = dict(keyword)
            keyword_copy["cluster_id"] = index
            keyword_copy["cluster_members"] = [keyword_copy["term"]]
            enriched.append(keyword_copy)
        return enriched

    def fake_aggregate(
        clustered_keywords: Sequence[Dict[str, Any]],
        **_: Any,
    ) -> list[Dict[str, Any]]:
        aggregated: list[Dict[str, Any]] = []
        for item in clustered_keywords:
            aggregated.append(
                {
                    "term": item["term"],
                    "score": float(item.get("score", 0.0)),
                    "original_variants": [item["term"]],
                    "sources": list(item.get("sources", [])),
                    "evidence": list(item.get("evidence", [])),
                    "occurrence_count": int(item.get("occurrence_count", 1)),
                }
            )
        aggregated.sort(key=lambda entry: entry["score"], reverse=True)
        return aggregated

    class DummyGemini:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        async def generate_content_async(
            self,
            *,
            prompt: str,
            response_format: str | None = None,
            **__: Any,
        ) -> str:
            assert "Bitcoin" in prompt
            assert response_format == "json"

            return json.dumps(
                {
                    "groups": [
                        {
                            "canonical": "Bitcoin",
                            "variants": ["Bitcoin", "BTC"],
                            "confidence": 0.92,
                            "rationale": "동일 자산을 지칭합니다.",
                        }
                    ],
                    "standalone": ["Ethereum"],
                }
            )

    monkeypatch.setattr(aggregator_module, "cluster_keywords_by_embedding", fake_cluster)
    monkeypatch.setattr(aggregator_module, "aggregate_clustered_keywords", fake_aggregate)
    monkeypatch.setattr(aggregator_module, "GeminiClient", DummyGemini)

    state = {
        "extracted_keywords": [
            {"term": "Bitcoin", "score": 9.5, "sources": ["CoinDesk"], "evidence": ["Bitcoin rally accelerates."]},
            {"term": "BTC", "score": 9.2, "sources": ["Bloomberg"], "evidence": ["BTC hits new highs."]},
            {"term": "Ethereum", "score": 8.1, "sources": ["CoinDesk"], "evidence": ["Ethereum upgrade scheduled."]},
        ],
        "config": {
            "normalization": {
                "embedding_threshold": 0.8,
                "llm_verification_enabled": True,
                "llm_verification_top_n": 4,
            },
            "output": {"top_keywords_count": 2},
            "llm": {"model": "gemini-2.0-flash", "temperature": 0.1, "max_tokens": 4000},
        },
    }

    result = await aggregator_module.aggregator_node(state)

    aggregated_keywords = result["aggregated_keywords"]

    assert [item["term"] for item in aggregated_keywords] == ["Bitcoin", "Ethereum"]
    assert aggregated_keywords[0]["original_variants"] == ["Bitcoin", "BTC"]
    assert result["scoring_summary"]["llm_verification_used"] is True
    assert result["llm_verification_result"] is not None


@pytest.mark.asyncio
async def test_aggregator_node_skips_llm_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    LLM 검증이 비활성화된 경우 GeminiClient가 호출되지 않는지 확인합니다.
    """

    async def fake_cluster(
        keywords: Sequence[Dict[str, Any]],
        **_: Any,
    ) -> list[Dict[str, Any]]:
        enriched: list[Dict[str, Any]] = []
        for index, keyword in enumerate(keywords):
            keyword_copy = dict(keyword)
            keyword_copy["cluster_id"] = index
            keyword_copy["cluster_members"] = [keyword_copy["term"]]
            enriched.append(keyword_copy)
        return enriched

    def fake_aggregate(
        clustered_keywords: Sequence[Dict[str, Any]],
        **_: Any,
    ) -> list[Dict[str, Any]]:
        aggregated: list[Dict[str, Any]] = []
        for item in clustered_keywords:
            aggregated.append(
                {
                    "term": item["term"],
                    "score": float(item.get("score", 0.0)),
                    "original_variants": [item["term"]],
                    "sources": list(item.get("sources", [])),
                    "evidence": list(item.get("evidence", [])),
                    "occurrence_count": int(item.get("occurrence_count", 1)),
                }
            )
        aggregated.sort(key=lambda entry: entry["score"], reverse=True)
        return aggregated

    class FailingGemini:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pytest.fail("GeminiClient should not be instantiated when verification is disabled.")

    monkeypatch.setattr(aggregator_module, "cluster_keywords_by_embedding", fake_cluster)
    monkeypatch.setattr(aggregator_module, "aggregate_clustered_keywords", fake_aggregate)
    monkeypatch.setattr(aggregator_module, "GeminiClient", FailingGemini)

    state = {
        "extracted_keywords": [
            {"term": "Bitcoin", "score": 9.5, "sources": ["CoinDesk"], "evidence": ["Bitcoin rally accelerates."]},
            {"term": "BTC", "score": 9.2, "sources": ["Bloomberg"], "evidence": ["BTC hits new highs."]},
            {"term": "Ethereum", "score": 8.1, "sources": ["CoinDesk"], "evidence": ["Ethereum upgrade scheduled."]},
        ],
        "config": {
            "normalization": {
                "embedding_threshold": 0.8,
                "llm_verification_enabled": False,
                "llm_verification_top_n": 4,
            },
            "output": {"top_keywords_count": 2},
            "llm": {"model": "gemini-2.0-flash", "temperature": 0.1, "max_tokens": 4000},
        },
    }

    result = await aggregator_module.aggregator_node(state)

    aggregated_keywords = result["aggregated_keywords"]

    assert [item["term"] for item in aggregated_keywords] == ["Bitcoin", "BTC"]
    assert result["scoring_summary"]["llm_verification_used"] is False
    assert result["llm_verification_result"] is None


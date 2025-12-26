"""
LLM 동의어 검증 유틸리티 테스트.
"""

from __future__ import annotations

import math

import pytest

from src.workflows.normalization.llm_verifier import merge_llm_groups_with_keywords


class TestMergeLlmGroupsWithKeywords:
    """
    ``merge_llm_groups_with_keywords`` 함수 동작을 검증합니다.
    """

    @staticmethod
    def _sample_candidates() -> list[dict[str, object]]:
        return [
            {
                "term": "Bitcoin",
                "score": 9.5,
                "rank": 1,
                "original_variants": ["BTC", "bitcoin"],
                "sources": ["CoinDesk", "Bloomberg"],
                "evidence": ["Bitcoin rally accelerates."],
                "occurrence_count": 2,
            },
            {
                "term": "BTC",
                "score": 9.2,
                "rank": 2,
                "original_variants": ["BTC"],
                "sources": ["CoinDesk"],
                "evidence": ["BTC hits new highs."],
                "occurrence_count": 1,
            },
            {
                "term": "Ethereum",
                "score": 8.1,
                "rank": 3,
                "original_variants": ["ETH"],
                "sources": ["CoinDesk"],
                "evidence": ["Ethereum upgrade scheduled."],
                "occurrence_count": 1,
            },
        ]

    @staticmethod
    def test_merges_group_and_preserves_original_variants() -> None:
        """
        그룹 정보가 주어졌을 때 original_variants가 확장되는지 검증합니다.
        """
        llm_result = {
            "groups": [
                {
                    "canonical": "Bitcoin",
                    "variants": ["Bitcoin", "BTC"],
                    "confidence": 0.9,
                    "rationale": "동일 자산을 지칭",
                }
            ],
            "standalone": ["Ethereum"],
        }

        merged = merge_llm_groups_with_keywords(
            candidate_keywords=TestMergeLlmGroupsWithKeywords._sample_candidates(),
            llm_result=llm_result,
            evidence_limit=5,
        )

        bitcoin_entry = next(item for item in merged if item["term"] == "Bitcoin")

        assert math.isclose(bitcoin_entry["score"], 9.5)
        assert bitcoin_entry["llm_metadata"]["confidence"] == 0.9
        assert bitcoin_entry["llm_metadata"]["canonical"] == "Bitcoin"
        assert bitcoin_entry["llm_metadata"]["variants"] == ["Bitcoin", "BTC"]

        assert bitcoin_entry["original_variants"] == ["Bitcoin", "BTC", "bitcoin"]
        assert bitcoin_entry["occurrence_count"] == 3

        ethereum_entry = next(item for item in merged if item["term"] == "Ethereum")
        assert ethereum_entry["original_variants"] == ["Ethereum", "ETH"]

    @staticmethod
    def test_respects_top_n_parameter() -> None:
        """
        top_n이 지정되면 해당 개수만 반환되는지 확인합니다.
        """
        llm_result = {
            "groups": [
                {
                    "canonical": "Bitcoin",
                    "variants": ["Bitcoin", "BTC"],
                    "confidence": 0.9,
                }
            ],
        }

        merged = merge_llm_groups_with_keywords(
            candidate_keywords=TestMergeLlmGroupsWithKeywords._sample_candidates(),
            llm_result=llm_result,
            top_n=1,
        )

        assert len(merged) == 1
        assert merged[0]["term"] == "Bitcoin"

    @staticmethod
    def test_handles_missing_llm_result() -> None:
        """
        LLM 응답이 없으면 후보 그대로 정렬하여 반환해야 합니다.
        """
        merged = merge_llm_groups_with_keywords(
            candidate_keywords=TestMergeLlmGroupsWithKeywords._sample_candidates(),
            llm_result=None,
        )

        assert [item["term"] for item in merged] == ["Bitcoin", "BTC", "Ethereum"]

    @staticmethod
    def test_invalid_top_n_raises_value_error() -> None:
        """
        top_n이 1 미만이면 예외를 발생시켜야 합니다.
        """
        with pytest.raises(ValueError):
            merge_llm_groups_with_keywords(
                candidate_keywords=TestMergeLlmGroupsWithKeywords._sample_candidates(),
                llm_result={},
                top_n=0,
            )

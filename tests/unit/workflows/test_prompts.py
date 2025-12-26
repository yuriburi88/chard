"""
프롬프트 템플릿 유틸리티에 대한 단위 테스트.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROMPTS_MODULE_PATH = (
    Path(__file__).resolve().parents[3] / "src" / "workflows" / "prompts.py"
)
PROMPTS_SPEC = importlib.util.spec_from_file_location(
    "prompts_module", PROMPTS_MODULE_PATH
)
prompts_module = importlib.util.module_from_spec(PROMPTS_SPEC)
assert PROMPTS_SPEC.loader is not None
PROMPTS_SPEC.loader.exec_module(prompts_module)  # type: ignore[call-arg]

build_insight_prompt = prompts_module.build_insight_prompt
build_synonym_verification_prompt = prompts_module.build_synonym_verification_prompt
parse_insight_response = prompts_module.parse_insight_response
prepare_insight_prompt_inputs = prompts_module.prepare_insight_prompt_inputs


class TestBuildSynonymVerificationPrompt:
    """
    동의어 검증 프롬프트 생성 함수를 검증합니다.
    """

    @staticmethod
    def test_prompt_includes_candidate_payload() -> None:
        """
        프롬프트에 후보 키워드 정보와 출력 포맷 지시가 포함되는지 확인합니다.
        """
        candidate_keywords = [
            {
                "term": "Bitcoin",
                "score": 9.5,
                "rank": 1,
                "original_variants": ["BTC", "bitcoin", "BTC"],
                "sources": ["CoinDesk", "Bloomberg"],
                "evidence": ["Bitcoin rally accelerates.", "BTC hits new highs."],
                "occurrence_count": 3,
            },
            {
                "term": "Ethereum",
                "score": 8.2,
                "rank": 2,
                "original_variants": ["ETH", "ether"],
                "sources": ["CoinDesk"],
                "evidence": ["ETH staking demand rises."],
                "occurrence_count": 2,
            },
        ]

        prompt = build_synonym_verification_prompt(
            candidate_keywords,
            top_n=5,
            max_variants=4,
        )

        assert "Bitcoin" in prompt
        assert '"groups"' in prompt
        assert '"standalone"' in prompt
        assert '"confidence"' in prompt
        assert '"rationale"' in prompt

    @staticmethod
    def test_raises_error_when_candidates_missing() -> None:
        """
        후보가 비어 있거나 top_n이 잘못되면 예외가 발생해야 합니다.
        """
        with pytest.raises(ValueError):
            build_synonym_verification_prompt([], top_n=5)

        with pytest.raises(ValueError):
            build_synonym_verification_prompt([{"term": "Bitcoin"}], top_n=0)


class TestInsightPromptUtilities:
    """
    Insight 프롬프트 관련 유틸리티를 검증합니다.
    """

    @staticmethod
    def test_prepare_insight_prompt_inputs_normalizes_keywords() -> None:
        """
        키워드와 출처 데이터가 정규화되고 문단 수가 3~5 범위로 제한되는지 확인합니다.
        """
        aggregated_keywords = [
            {
                "term": "Bitcoin",
                "score": 92.5,
                "original_variants": ["BTC", "bitcoin"],
                "evidence": ["Bitcoin rallies amid ETF inflows."],
                "sources": ["CoinDesk", "Bloomberg"],
                "occurrence_count": 4,
            },
            {
                "term": "Ethereum",
                "score": 81.0,
                "original_variants": ["ETH"],
                "evidence": ["ETH staking demand grows steadily."],
                "sources": ["CoinDesk"],
                "occurrence_count": 2,
            },
        ]

        raw_records = [
            {
                "source": "rss",
                "timestamp": "2024-05-01T12:00:00Z",
                "text": "Bitcoin price surges as ETF inflows accelerate.",
                "meta": {
                    "title": "ETF inflows lift Bitcoin",
                    "url": "https://example.com/bitcoin-etf",
                },
            },
            {
                "source": "rss",
                "timestamp": "2024-05-01T13:00:00Z",
                "text": "Ethereum staking continues to expand across DeFi platforms.",
                "meta": {
                    "title": "Ethereum staking expansion",
                    "url": "https://example.com/eth-staking",
                },
            },
        ]

        prepared = prepare_insight_prompt_inputs(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=6,
            max_sources=3,
            include_excerpts=False,
        )

        assert prepared["summary_paragraphs"] == 5
        assert len(prepared["keywords"]) == 2
        assert prepared["keywords"][0]["original_variants"][0] == "Bitcoin"
        assert prepared["source_highlights"]
        assert "excerpt" not in prepared["source_highlights"][0]

    @staticmethod
    def test_build_insight_prompt_contains_expected_sections() -> None:
        """
        Insight 프롬프트에 키워드와 출처 하이라이트가 포함되는지 확인합니다.
        """
        aggregated_keywords = [
            {
                "term": "Solana",
                "score": 70.0,
                "original_variants": ["SOL"],
                "evidence": ["Solana apps see higher user growth."],
                "sources": ["Decrypt"],
                "occurrence_count": 3,
            }
        ]

        raw_records = [
            {
                "source": "rss",
                "timestamp": "2024-05-01T12:00:00Z",
                "text": "Solana ecosystem projects are experiencing a surge.",
                "meta": {
                    "title": "Solana ecosystem surge",
                    "url": "https://example.com/solana-surge",
                },
            }
        ]

        prepared_inputs = prepare_insight_prompt_inputs(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=4,
            max_sources=2,
            include_excerpts=True,
        )

        prompt = build_insight_prompt(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=4,
            max_sources=2,
            include_excerpts=True,
            prepared_inputs=prepared_inputs,
        )

        assert "Solana" in prompt
        assert '"narrative_summary"' in prompt
        assert '"trading_insights"' in prompt
        assert "https://example.com/solana-surge" in prompt

    @staticmethod
    def test_parse_insight_response_handles_code_fence() -> None:
        """
        코드 펜스로 감싼 응답도 올바르게 파싱되는지 검증합니다.
        """
        response_text = """```json
{
  "narrative_summary": [
    "Bitcoin ETF inflows continue to support bullish sentiment.",
    "Ethereum staking growth indicates long-term confidence."
  ],
  "trading_insights": {
    "opportunities": ["Monitor ETF-driven rallies."],
    "risks": ["Volatility from regulatory discussions."],
    "market_sentiment": "긍정적"
  },
  "key_sources": [
    {
      "title": "Bitcoin ETF inflow update",
      "url": "https://example.com/bitcoin-etf",
      "relevance": ["Bitcoin"]
    }
  ]
}
```"""

        parsed = parse_insight_response(response_text)

        assert len(parsed["narrative_summary"]) == 2
        assert parsed["trading_insights"]["market_sentiment"] == "긍정적"
        assert parsed["key_sources"][0]["title"] == "Bitcoin ETF inflow update"

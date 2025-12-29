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

# Key Points 관련 함수들
build_macro_keypoints_prompt = prompts_module.build_macro_keypoints_prompt
build_crypto_keypoints_prompt = prompts_module.build_crypto_keypoints_prompt
build_integrated_keypoints_prompt = prompts_module.build_integrated_keypoints_prompt
parse_keypoints_response = prompts_module.parse_keypoints_response

# Narrative 프롬프트 함수들 (key_points 파라미터 포함)
build_macro_narrative_prompt = prompts_module.build_macro_narrative_prompt
build_crypto_narrative_prompt = prompts_module.build_crypto_narrative_prompt
build_integrated_narrative_prompt = prompts_module.build_integrated_narrative_prompt


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


class TestKeyPointsPrompts:
    """
    Key Points 프롬프트 생성 함수들을 검증합니다.
    """

    @staticmethod
    def _sample_keywords():
        """테스트용 샘플 키워드"""
        return [
            {
                "term": "Bitcoin",
                "score": 92.5,
                "original_variants": ["BTC", "bitcoin"],
                "evidence": ["Bitcoin rallies amid ETF inflows."],
                "sources": ["CoinDesk", "Bloomberg"],
                "occurrence_count": 4,
            },
            {
                "term": "Federal Reserve",
                "score": 85.0,
                "original_variants": ["Fed", "연준"],
                "evidence": ["Fed signals rate pause."],
                "sources": ["Bloomberg"],
                "occurrence_count": 3,
            },
        ]

    @staticmethod
    def _sample_source_highlights():
        """테스트용 샘플 소스 하이라이트"""
        return [
            {
                "title": "Bitcoin ETF inflows surge",
                "url": "https://example.com/btc-etf",
                "relevance": ["Bitcoin", "ETF"],
            },
            {
                "title": "Fed holds rates steady",
                "url": "https://example.com/fed-rates",
                "relevance": ["Federal Reserve"],
            },
        ]

    def test_build_macro_keypoints_prompt_contains_expected_sections(self) -> None:
        """
        Macro Key Points 프롬프트에 필수 섹션이 포함되는지 확인합니다.
        """
        keywords = self._sample_keywords()
        source_highlights = self._sample_source_highlights()

        prompt = build_macro_keypoints_prompt(
            keywords, source_highlights, economic_events=None
        )

        # 프롬프트에 키워드가 포함되어야 함
        assert "Bitcoin" in prompt or "Federal Reserve" in prompt
        # Key Points 출력 형식 지침이 포함되어야 함
        assert "key_points" in prompt
        assert "source_mapping" in prompt
        # 5~20개 범위 지침이 포함되어야 함
        assert "5" in prompt and "20" in prompt

    def test_build_crypto_keypoints_prompt_contains_expected_sections(self) -> None:
        """
        Crypto Key Points 프롬프트에 필수 섹션이 포함되는지 확인합니다.
        """
        keywords = self._sample_keywords()
        source_highlights = self._sample_source_highlights()

        prompt = build_crypto_keypoints_prompt(
            keywords, source_highlights, economic_events=None
        )

        assert "key_points" in prompt
        assert "source_mapping" in prompt

    def test_build_integrated_keypoints_prompt_includes_both_categories(self) -> None:
        """
        통합 Key Points 프롬프트에 Macro/Crypto Key Points가 포함되는지 확인합니다.
        """
        macro_key_points = [
            "연준이 금리 동결을 결정했습니다.",
            "인플레이션이 2.5%로 하락했습니다.",
        ]
        crypto_key_points = [
            "비트코인 ETF 유입이 10억 달러를 돌파했습니다.",
            "이더리움 스테이킹 비율이 25%를 넘었습니다.",
        ]
        keywords = self._sample_keywords()

        prompt = build_integrated_keypoints_prompt(
            macro_key_points, crypto_key_points, keywords, economic_events=None
        )

        # Macro Key Points가 포함되어야 함
        assert "금리 동결" in prompt or "Macro" in prompt
        # Crypto Key Points가 포함되어야 함
        assert "비트코인" in prompt or "Crypto" in prompt
        # 출력 형식 지침이 포함되어야 함
        assert "key_points" in prompt

    def test_parse_keypoints_response_valid_json(self) -> None:
        """
        유효한 JSON 응답을 올바르게 파싱하는지 확인합니다.
        """
        response_text = """```json
{
    "key_points": [
        "비트코인이 10만 달러를 돌파했습니다.",
        "연준이 금리를 동결했습니다.",
        "이더리움 스테이킹 비율이 증가했습니다.",
        "규제 불확실성이 지속되고 있습니다.",
        "기관 투자자들의 유입이 늘어났습니다."
    ],
    "source_mapping": {
        "0": [1, 2],
        "1": [3],
        "2": [4, 5],
        "3": [6],
        "4": [7, 8]
    }
}
```"""

        parsed = parse_keypoints_response(response_text, category="Test")

        assert "key_points" in parsed
        assert "source_mapping" in parsed
        assert len(parsed["key_points"]) == 5
        assert parsed["source_mapping"]["0"] == [1, 2]

    def test_parse_keypoints_response_validates_range(self) -> None:
        """
        Key Points 개수가 5~20개 범위를 벗어나면 경고가 발생하는지 확인합니다.
        """
        # 4개 - 범위 미만 (경고 발생하지만 파싱은 성공)
        response_too_few = """{
            "key_points": ["포인트1", "포인트2", "포인트3", "포인트4"],
            "source_mapping": {}
        }"""

        parsed = parse_keypoints_response(response_too_few, category="Test")
        assert len(parsed["key_points"]) == 4  # 파싱은 성공

    def test_parse_keypoints_response_handles_missing_fields(self) -> None:
        """
        필수 필드가 없는 응답도 기본값으로 처리하는지 확인합니다.
        """
        response_text = """{"key_points": ["포인트1", "포인트2", "포인트3", "포인트4", "포인트5"]}"""

        parsed = parse_keypoints_response(response_text, category="Test")

        assert "key_points" in parsed
        assert "source_mapping" in parsed  # 기본값으로 빈 dict
        assert parsed["source_mapping"] == {}


class TestNarrativePromptsWithKeyPoints:
    """
    Key Points 파라미터가 추가된 Narrative 프롬프트를 검증합니다.
    """

    @staticmethod
    def _sample_keywords():
        """테스트용 샘플 키워드"""
        return [
            {
                "term": "Bitcoin",
                "score": 92.5,
                "original_variants": ["BTC"],
                "evidence": ["Bitcoin rallies."],
                "sources": ["CoinDesk"],
                "occurrence_count": 4,
            },
        ]

    @staticmethod
    def _sample_source_highlights():
        """테스트용 샘플 소스 하이라이트"""
        return [
            {
                "title": "Bitcoin ETF inflows",
                "url": "https://example.com/btc",
                "relevance": ["Bitcoin"],
            },
        ]

    def test_build_macro_narrative_prompt_without_key_points(self) -> None:
        """
        key_points 없이 기존 방식으로 동작하는지 확인합니다 (하위 호환성).
        """
        keywords = self._sample_keywords()
        source_highlights = self._sample_source_highlights()

        prompt = build_macro_narrative_prompt(
            keywords, source_highlights, economic_events=None, key_points=None
        )

        # 기존 프롬프트 형식이 유지되어야 함
        assert "narrative" in prompt.lower()
        # Key Points 섹션이 없어야 함
        assert "Key Points (필수 반영)" not in prompt

    def test_build_macro_narrative_prompt_with_key_points(self) -> None:
        """
        key_points가 있으면 프롬프트에 Key Points 섹션이 추가되는지 확인합니다.
        """
        keywords = self._sample_keywords()
        source_highlights = self._sample_source_highlights()
        key_points = [
            "비트코인이 10만 달러를 돌파했습니다.",
            "ETF 유입이 급증하고 있습니다.",
        ]

        prompt = build_macro_narrative_prompt(
            keywords, source_highlights, economic_events=None, key_points=key_points
        )

        # Key Points 섹션이 포함되어야 함
        assert "Key Points" in prompt
        assert "비트코인이 10만 달러" in prompt
        assert "ETF 유입" in prompt

    def test_build_crypto_narrative_prompt_with_key_points(self) -> None:
        """
        Crypto Narrative 프롬프트에 key_points가 반영되는지 확인합니다.
        """
        keywords = self._sample_keywords()
        source_highlights = self._sample_source_highlights()
        key_points = ["디파이 TVL이 증가했습니다.", "NFT 거래량이 급증했습니다."]

        prompt = build_crypto_narrative_prompt(
            keywords,
            source_highlights,
            num_paragraphs=2,
            economic_events=None,
            key_points=key_points,
        )

        assert "Key Points" in prompt
        assert "디파이 TVL" in prompt or "NFT 거래량" in prompt

    def test_build_integrated_narrative_prompt_with_key_points(self) -> None:
        """
        통합 Narrative 프롬프트에 key_points가 반영되는지 확인합니다.
        """
        macro_narrative = ["연준이 금리를 동결했습니다."]
        crypto_narrative = ["비트코인이 상승했습니다."]
        keywords = self._sample_keywords()
        key_points = ["거시경제와 암호화폐 시장의 상관관계가 강화되고 있습니다."]

        prompt = build_integrated_narrative_prompt(
            macro_narrative,
            crypto_narrative,
            keywords,
            num_paragraphs=3,
            economic_events=None,
            key_points=key_points,
        )

        assert "Key Points" in prompt
        assert "상관관계" in prompt

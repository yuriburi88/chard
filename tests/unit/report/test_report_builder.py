"""
Report Builder 단위 테스트

Key Points 기반 NarrativeWithKeyPoints 구조의 출력을 검증합니다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPORT_BUILDER_PATH = (
    Path(__file__).resolve().parents[3] / "src" / "report" / "report_builder.py"
)
REPORT_BUILDER_SPEC = importlib.util.spec_from_file_location(
    "report_builder_module", REPORT_BUILDER_PATH
)
report_builder_module = importlib.util.module_from_spec(REPORT_BUILDER_SPEC)
assert REPORT_BUILDER_SPEC.loader is not None
REPORT_BUILDER_SPEC.loader.exec_module(report_builder_module)

build_json_report = report_builder_module.build_json_report
build_markdown_report = report_builder_module.build_markdown_report
_build_category_narrative_section = report_builder_module._build_category_narrative_section
_build_markdown_narrative_section = report_builder_module._build_markdown_narrative_section


class TestCategoryNarrativeSection:
    """
    _build_category_narrative_section 함수를 검증합니다.
    """

    def test_with_narrative_with_key_points_structure(self) -> None:
        """
        NarrativeWithKeyPoints 구조가 올바르게 렌더링되는지 확인합니다.
        """
        category_data = {
            "key_points": [
                "비트코인이 10만 달러를 돌파했습니다.",
                "ETF 유입이 급증하고 있습니다.",
                "기관 투자자들의 관심이 증가했습니다.",
            ],
            "paragraphs": [
                "비트코인은 ETF 승인 이후 강세를 보이고 있습니다.",
                "향후 금리 인하 기대감이 상승 모멘텀을 더할 것으로 예상됩니다.",
            ],
            "source_mapping": {"0": [1, 2], "1": [3]},
        }

        result = _build_category_narrative_section("Macro", category_data)

        # 헤더 확인
        assert "### Macro 내러티브 요약" in result
        # Key Points 섹션 확인
        assert "#### Key Points" in result
        assert "• 비트코인이 10만 달러를 돌파했습니다." in result
        assert "• ETF 유입이 급증하고 있습니다." in result
        # 분석 섹션 확인
        assert "#### 분석" in result
        assert "비트코인은 ETF 승인 이후 강세를 보이고 있습니다." in result

    def test_with_legacy_list_structure(self) -> None:
        """
        기존 list[str] 구조도 하위 호환성이 유지되는지 확인합니다.
        """
        category_data = [
            "첫 번째 문단입니다.",
            "두 번째 문단입니다.",
        ]

        result = _build_category_narrative_section("Crypto", category_data)

        # 헤더 확인
        assert "### Crypto 내러티브 요약" in result
        # 문단 확인
        assert "첫 번째 문단입니다." in result
        assert "두 번째 문단입니다." in result
        # Key Points 섹션은 없어야 함
        assert "#### Key Points" not in result

    def test_with_empty_key_points(self) -> None:
        """
        key_points가 비어있어도 paragraphs는 렌더링되는지 확인합니다.
        """
        category_data = {
            "key_points": [],
            "paragraphs": ["문단만 있는 경우입니다."],
            "source_mapping": {},
        }

        result = _build_category_narrative_section("통합", category_data)

        assert "### 통합 내러티브 요약" in result
        assert "#### 분석" in result
        assert "문단만 있는 경우입니다." in result
        # Key Points 섹션은 없어야 함 (비어있으므로)
        assert "#### Key Points" not in result

    def test_with_empty_paragraphs(self) -> None:
        """
        paragraphs가 비어있어도 key_points는 렌더링되는지 확인합니다.
        """
        category_data = {
            "key_points": ["Key Point만 있는 경우입니다."],
            "paragraphs": [],
            "source_mapping": {},
        }

        result = _build_category_narrative_section("Macro", category_data)

        assert "### Macro 내러티브 요약" in result
        assert "#### Key Points" in result
        assert "• Key Point만 있는 경우입니다." in result
        # 분석 섹션은 없어야 함 (비어있으므로)
        assert "#### 분석" not in result

    def test_with_empty_data(self) -> None:
        """
        모든 데이터가 비어있으면 빈 문자열을 반환하는지 확인합니다.
        """
        category_data = {
            "key_points": [],
            "paragraphs": [],
            "source_mapping": {},
        }

        result = _build_category_narrative_section("Macro", category_data)

        assert result == ""

    def test_with_empty_list(self) -> None:
        """
        빈 리스트도 빈 문자열을 반환하는지 확인합니다.
        """
        result = _build_category_narrative_section("Crypto", [])

        assert result == ""


class TestMarkdownNarrativeSection:
    """
    _build_markdown_narrative_section 함수를 검증합니다.
    """

    def test_with_narrative_with_key_points(self) -> None:
        """
        NarrativeWithKeyPoints 구조가 포함된 state가 올바르게 렌더링되는지 확인합니다.
        """
        state = {
            "insights": {
                "narratives": {
                    "macro": {
                        "key_points": ["Macro 포인트 1", "Macro 포인트 2"],
                        "paragraphs": ["Macro 문단 1"],
                        "source_mapping": {},
                    },
                    "crypto": {
                        "key_points": ["Crypto 포인트 1"],
                        "paragraphs": ["Crypto 문단 1", "Crypto 문단 2"],
                        "source_mapping": {},
                    },
                    "integrated": {
                        "key_points": ["통합 포인트 1"],
                        "paragraphs": ["통합 문단 1"],
                        "source_mapping": {},
                    },
                }
            }
        }

        result = _build_markdown_narrative_section(state)

        # 각 카테고리가 모두 포함되어야 함
        assert "### Macro 내러티브 요약" in result
        assert "### Crypto 내러티브 요약" in result
        assert "### 통합 내러티브 요약" in result

        # Key Points가 포함되어야 함
        assert "• Macro 포인트 1" in result
        assert "• Crypto 포인트 1" in result
        assert "• 통합 포인트 1" in result

    def test_with_legacy_list_structure(self) -> None:
        """
        기존 list[str] 구조도 하위 호환성이 유지되는지 확인합니다.
        """
        state = {
            "insights": {
                "narratives": {
                    "macro": ["Macro 문단 1", "Macro 문단 2"],
                    "crypto": ["Crypto 문단 1"],
                    "integrated": ["통합 문단 1"],
                }
            }
        }

        result = _build_markdown_narrative_section(state)

        assert "### Macro 내러티브 요약" in result
        assert "Macro 문단 1" in result
        assert "Macro 문단 2" in result

    def test_with_no_narratives(self) -> None:
        """
        narratives가 없으면 적절한 메시지가 반환되는지 확인합니다.
        """
        state = {"insights": {}}

        result = _build_markdown_narrative_section(state)

        assert "내러티브 요약이 없습니다" in result


class TestBuildJsonReport:
    """
    build_json_report 함수를 검증합니다.
    """

    def test_with_narrative_with_key_points(self) -> None:
        """
        NarrativeWithKeyPoints 구조가 JSON 리포트에 포함되는지 확인합니다.
        """
        state = {
            "aggregated_keywords": [
                {"term": "Bitcoin", "score": 90, "original_variants": ["BTC"]},
            ],
            "insights": {
                "narratives": {
                    "macro": {
                        "key_points": ["Macro 포인트"],
                        "paragraphs": ["Macro 문단"],
                        "source_mapping": {},
                    },
                },
                "trading_insights": {},
                "key_sources": [],
            },
            "errors": [],
        }

        report = build_json_report(state)

        # insights가 그대로 포함되어야 함
        assert "insights" in report
        assert "narratives" in report["insights"]
        assert "macro" in report["insights"]["narratives"]
        assert "key_points" in report["insights"]["narratives"]["macro"]
        assert report["insights"]["narratives"]["macro"]["key_points"] == ["Macro 포인트"]

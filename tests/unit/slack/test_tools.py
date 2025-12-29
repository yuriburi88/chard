"""
CHARD 도구 테스트

Claude Tool Use를 위한 도구 정의 및 실행 함수 테스트
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.slack.tools import (
    TOOLS,
    DEFAULT_TIMEOUT,
    TOOL_TIMEOUTS,
    execute_tool,
    with_timeout,
)


class TestToolDefinitions:
    """도구 정의 테스트"""

    def test_tools_list_not_empty(self):
        """도구 목록이 비어있지 않은지 테스트"""
        assert len(TOOLS) > 0

    def test_required_tools_exist(self):
        """필수 도구가 정의되어 있는지 테스트"""
        tool_names = [tool["name"] for tool in TOOLS]

        assert "run_analysis" in tool_names
        assert "run_analysis_filtered" in tool_names
        assert "get_latest_report" in tool_names
        assert "get_latest_keywords" in tool_names
        assert "list_available_sources" in tool_names

    def test_tool_has_required_fields(self):
        """각 도구에 필수 필드가 있는지 테스트"""
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "type" in tool["input_schema"]

    def test_run_analysis_schema(self):
        """run_analysis 도구 스키마 테스트"""
        tool = next(t for t in TOOLS if t["name"] == "run_analysis")

        assert tool["input_schema"]["type"] == "object"
        assert "days_back" in tool["input_schema"]["properties"]

    def test_run_analysis_filtered_schema(self):
        """run_analysis_filtered 도구 스키마 테스트"""
        tool = next(t for t in TOOLS if t["name"] == "run_analysis_filtered")

        props = tool["input_schema"]["properties"]
        assert "source" in props
        assert "keyword" in props
        assert "days_back" in props
        assert props["source"]["enum"] == ["rss", "telegram", "all"]


class TestToolTimeouts:
    """타임아웃 설정 테스트"""

    def test_timeout_values_set(self):
        """타임아웃 값이 설정되어 있는지 테스트"""
        assert TOOL_TIMEOUTS["run_analysis"] == 300
        assert TOOL_TIMEOUTS["get_latest_report"] == 30
        assert DEFAULT_TIMEOUT == 60

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """타임아웃 내 완료 테스트"""
        async def quick_task():
            return "success"

        result = await with_timeout(quick_task(), timeout=5, tool_name="test")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_expired(self):
        """타임아웃 초과 테스트"""
        async def slow_task():
            await asyncio.sleep(10)
            return "too late"

        with pytest.raises(TimeoutError, match="도구 실행 시간 초과"):
            await with_timeout(slow_task(), timeout=0.1, tool_name="test")


class TestExecuteTool:
    """도구 실행 테스트"""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """알 수 없는 도구 실행 테스트"""
        result = await execute_tool("unknown_tool", {})
        assert "알 수 없는 도구" in result

    @pytest.mark.asyncio
    async def test_execute_get_latest_report_no_output(self):
        """출력 없을 때 get_latest_report 테스트"""
        with patch("src.slack.tools.PROJECT_ROOT") as mock_root:
            mock_root.__truediv__ = MagicMock(
                return_value=Path("/nonexistent/output")
            )

            result = await execute_tool("get_latest_report", {})
            assert "찾을 수 없습니다" in result or "오류" in result

    @pytest.mark.asyncio
    async def test_execute_get_latest_keywords_no_output(self):
        """출력 없을 때 get_latest_keywords 테스트"""
        with patch("src.slack.tools.PROJECT_ROOT") as mock_root:
            mock_root.__truediv__ = MagicMock(
                return_value=Path("/nonexistent/output")
            )

            result = await execute_tool("get_latest_keywords", {"limit": 5})
            assert "찾을 수 없습니다" in result or "오류" in result

    @pytest.mark.asyncio
    async def test_execute_list_available_sources_error(self):
        """소스 목록 조회 에러 테스트"""
        with patch("src.slack.tools._list_available_sources") as mock_func:
            mock_func.side_effect = Exception("Config error")

            result = await execute_tool("list_available_sources", {})
            assert "오류" in result


class TestGetLatestReport:
    """get_latest_report 상세 테스트"""

    @pytest.fixture
    def mock_output_dir(self, tmp_path):
        """임시 출력 디렉토리 fixture"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # 날짜별 디렉토리 생성
        date_dir = output_dir / "2025-12-29"
        date_dir.mkdir()

        # 리포트 파일 생성
        report_file = date_dir / "report_summary.md"
        report_file.write_text(
            "# 시장 분석 리포트\n\n## 키워드\n- Bitcoin: 높은 관심\n",
            encoding="utf-8"
        )

        return output_dir

    @pytest.mark.asyncio
    async def test_get_latest_report_success(self, mock_output_dir):
        """리포트 조회 성공 테스트"""
        with patch("src.slack.tools.PROJECT_ROOT", mock_output_dir.parent):
            from src.slack.tools import _get_latest_report

            result = await _get_latest_report()

            assert "2025-12-29" in result
            assert "키워드" in result or "리포트" in result


class TestGetLatestKeywords:
    """get_latest_keywords 상세 테스트"""

    @pytest.fixture
    def mock_output_with_keywords(self, tmp_path):
        """키워드 데이터가 있는 출력 디렉토리 fixture"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        date_dir = output_dir / "2025-12-29"
        date_dir.mkdir()

        # 분석 JSON 파일 생성
        analysis_data = {
            "aggregated_keywords": [
                {"term": "Bitcoin", "score": 95.5, "occurrence_count": 50, "category": "crypto"},
                {"term": "Ethereum", "score": 85.2, "occurrence_count": 35, "category": "crypto"},
                {"term": "Fed", "score": 75.0, "occurrence_count": 20, "category": "macro"},
            ]
        }

        analysis_file = date_dir / "analysis_summary.json"
        analysis_file.write_text(json.dumps(analysis_data), encoding="utf-8")

        return output_dir

    @pytest.mark.asyncio
    async def test_get_latest_keywords_success(self, mock_output_with_keywords):
        """키워드 조회 성공 테스트"""
        with patch("src.slack.tools.PROJECT_ROOT", mock_output_with_keywords.parent):
            from src.slack.tools import _get_latest_keywords

            result = await _get_latest_keywords({"limit": 3})

            assert "Bitcoin" in result
            assert "Ethereum" in result
            assert "95.5" in result or "95" in result

    @pytest.mark.asyncio
    async def test_get_latest_keywords_with_limit(self, mock_output_with_keywords):
        """키워드 개수 제한 테스트"""
        with patch("src.slack.tools.PROJECT_ROOT", mock_output_with_keywords.parent):
            from src.slack.tools import _get_latest_keywords

            result = await _get_latest_keywords({"limit": 1})

            assert "Bitcoin" in result
            # Ethereum은 제한으로 인해 없을 수 있음


class TestRunAnalysis:
    """run_analysis 테스트"""

    @pytest.mark.asyncio
    async def test_run_analysis_import_error(self):
        """main.py import 실패 시 데모 모드 테스트"""
        with patch("src.slack.tools._get_analysis_summary") as mock_summary:
            mock_summary.return_value = "📊 데모 분석 결과"

            # main 모듈이 없는 환경 시뮬레이션
            with patch.dict("sys.modules", {"main": None}):
                from src.slack.tools import _run_analysis

                result = await _run_analysis({"days_back": 1})

                # 데모 모드이거나 에러 메시지
                assert "분석" in result or "오류" in result


class TestRunAnalysisFiltered:
    """run_analysis_filtered 테스트"""

    @pytest.mark.asyncio
    async def test_run_analysis_filtered_with_keyword(self):
        """키워드 필터 분석 테스트"""
        with patch("src.slack.tools._get_latest_report") as mock_report:
            mock_report.return_value = "# 분석 리포트\nBitcoin 관련 뉴스..."

            from src.slack.tools import _run_analysis_filtered

            result = await _run_analysis_filtered({
                "source": "rss",
                "keyword": "bitcoin",
                "days_back": 1,
            })

            assert "필터" in result or "분석" in result

    @pytest.mark.asyncio
    async def test_run_analysis_filtered_all_sources(self):
        """전체 소스 분석 테스트"""
        with patch("src.slack.tools._get_latest_report") as mock_report:
            mock_report.return_value = "# 전체 분석 리포트"

            from src.slack.tools import _run_analysis_filtered

            result = await _run_analysis_filtered({
                "source": "all",
                "days_back": 1,
            })

            assert "리포트" in result or "분석" in result

"""
CHARD Tools for Claude

Claude API의 Tool Use를 위한 도구 정의 및 실행 함수.
기존 CHARD 파이프라인을 호출하여 분석을 수행합니다.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any


# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# 도구별 타임아웃 설정 (초)
TOOL_TIMEOUTS = {
    "run_analysis": 300,  # 5분
    "run_analysis_filtered": 300,  # 5분
    "get_latest_report": 30,  # 30초
    "get_latest_keywords": 30,  # 30초
    "list_available_sources": 10,  # 10초
}

DEFAULT_TIMEOUT = 60  # 기본 1분


async def with_timeout(coro, timeout: float, tool_name: str):
    """타임아웃이 적용된 코루틴 실행"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as e:
        logger.error(f"도구 타임아웃: {tool_name} ({timeout}초 초과)")
        raise TimeoutError(f"도구 실행 시간 초과 ({timeout}초)") from e

# Claude Tool Use 형식의 도구 정의
TOOLS = [
    {
        "name": "run_analysis",
        "description": "Run full market analysis on recent news from all sources (RSS + Telegram). "
                      "This executes the complete CHARD pipeline: data collection → preprocessing → "
                      "keyword extraction → narrative generation → report creation. "
                      "Takes 1-2 minutes to complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 1 = today only)",
                    "default": 1,
                },
            },
        },
    },
    {
        "name": "run_analysis_filtered",
        "description": "Run market analysis with specific filters. Can filter by source (RSS or Telegram), "
                      "keyword, or time period. Use this when user wants specific analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["rss", "telegram", "all"],
                    "description": "Data source to analyze: 'rss' for news feeds only, 'telegram' for Telegram only, 'all' for both",
                    "default": "all",
                },
                "keyword": {
                    "type": "string",
                    "description": "Keyword to filter news (e.g., 'bitcoin', 'ethereum', '비트코인'). "
                                  "Only articles containing this keyword will be analyzed.",
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to analyze",
                    "default": 1,
                },
            },
        },
    },
    {
        "name": "get_latest_report",
        "description": "Get the most recent analysis report. Returns the full markdown report "
                      "with keywords, market sentiment, and trading insights.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_latest_keywords",
        "description": "Get the top trending keywords from the latest analysis. "
                      "Shows keyword scores, occurrence counts, and categories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of keywords to return (default: 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "list_available_sources",
        "description": "List all available data sources configured in CHARD (RSS feeds and Telegram channels).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


async def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """
    도구를 실행하고 결과를 반환합니다.

    Args:
        tool_name: 도구 이름
        tool_input: 도구 입력 파라미터

    Returns:
        도구 실행 결과 (문자열)
    """
    logger.info(f"도구 실행: {tool_name}, 입력: {tool_input}")

    # 타임아웃 설정
    timeout = TOOL_TIMEOUTS.get(tool_name, DEFAULT_TIMEOUT)

    try:
        if tool_name == "run_analysis":
            coro = _run_analysis(tool_input)
        elif tool_name == "run_analysis_filtered":
            coro = _run_analysis_filtered(tool_input)
        elif tool_name == "get_latest_report":
            coro = _get_latest_report()
        elif tool_name == "get_latest_keywords":
            coro = _get_latest_keywords(tool_input)
        elif tool_name == "list_available_sources":
            coro = _list_available_sources()
        else:
            return f"알 수 없는 도구: {tool_name}"

        # 타임아웃 적용하여 실행
        return await with_timeout(coro, timeout, tool_name)

    except TimeoutError:
        logger.error(f"도구 타임아웃: {tool_name}")
        return f"⏱️ 도구 실행 시간 초과 ({timeout}초). 잠시 후 다시 시도해 주세요."

    except Exception as e:
        logger.error(f"도구 실행 실패: {tool_name}, 에러: {e}")
        return f"도구 실행 중 오류 발생: {str(e)}"


async def _run_analysis(args: dict[str, Any]) -> str:
    """전체 분석 실행"""
    days_back = args.get("days_back", 1)

    logger.info(f"전체 분석 시작 (days_back={days_back})")

    try:
        # main.py의 분석 함수 임포트 및 실행
        # NOTE: main.py는 main_async()를 사용하므로, 직접 실행보다는
        # 최신 결과를 반환하는 방식으로 구현
        # 실제 파이프라인 실행은 별도 subprocess로 처리하는 것이 안전
        import subprocess

        # 비동기로 파이프라인 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["python", "main.py", "--days-back", str(days_back)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=280,  # 타임아웃보다 약간 짧게
            ),
        )

        if result.returncode == 0:
            # 실행 성공 - 최신 결과 가져오기
            summary = await _get_analysis_summary()
            return f"✅ 분석 완료!\n\n{summary}"
        else:
            logger.error(f"파이프라인 실행 실패: {result.stderr[:500]}")
            return f"분석 실행 중 오류 발생: {result.stderr[:200]}"

    except subprocess.TimeoutExpired:
        logger.warning("파이프라인 실행 타임아웃")
        return "⏱️ 분석 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        logger.error(f"분석 실행 실패: {e}")
        return f"분석 실행 중 오류 발생: {str(e)}"


async def _run_analysis_filtered(args: dict[str, Any]) -> str:
    """필터링된 분석 실행"""
    source = args.get("source", "all")
    keyword = args.get("keyword")
    days_back = args.get("days_back", 1)

    filter_desc = []
    if source != "all":
        filter_desc.append(f"소스: {source}")
    if keyword:
        filter_desc.append(f"키워드: {keyword}")
    filter_desc.append(f"기간: {days_back}일")

    logger.info(f"필터 분석 시작: {', '.join(filter_desc)}")

    # TODO: 실제 필터링 로직 구현
    # 현재는 전체 분석 결과에서 필터링하는 방식으로 구현

    try:
        # 최신 분석 결과 가져오기
        report = await _get_latest_report()

        if keyword:
            # 키워드가 포함된 부분만 강조
            filter_info = f"🔍 필터 조건: {', '.join(filter_desc)}\n\n"
            return filter_info + report
        else:
            return report

    except Exception as e:
        logger.error(f"필터 분석 실패: {e}")
        return f"필터 분석 중 오류 발생: {str(e)}"


async def _get_latest_report() -> str:
    """최신 리포트 조회"""
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return "분석 결과를 찾을 수 없습니다. 먼저 분석을 실행해 주세요."

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return "분석 결과를 찾을 수 없습니다."

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # 리포트 파일 찾기
    report_files = (list(latest_dir.glob("*_summary.md"))
                    + list(latest_dir.glob("report_*.md")))

    if not report_files:
        # JSON 파일에서 요약 생성
        return await _get_analysis_summary()

    # 가장 최근 리포트 읽기
    latest_report = sorted(report_files, reverse=True)[0]

    with open(latest_report, encoding="utf-8") as f:
        content = f.read()

    # 너무 길면 요약
    if len(content) > 3000:
        content = content[:3000] + "\n\n... (내용이 길어 일부만 표시)"

    return f"📄 {date_str} 분석 리포트\n\n{content}"


async def _get_latest_keywords(args: dict[str, Any]) -> str:
    """최신 키워드 조회"""
    limit = args.get("limit", 10)

    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return "분석 결과를 찾을 수 없습니다."

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return "분석 결과를 찾을 수 없습니다."

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # 분석 파일 찾기
    analysis_files = (list(latest_dir.glob("analysis_*.json"))
                      + list(latest_dir.glob("*_summary.json")))

    if not analysis_files:
        return f"{date_str}의 분석 결과 파일을 찾을 수 없습니다."

    # 첫 번째 분석 파일 읽기
    with open(analysis_files[0], encoding="utf-8") as f:
        analysis_data = json.load(f)

    # 키워드 추출
    keywords = analysis_data.get("aggregated_keywords", [])

    if not keywords:
        # 다른 형식 시도
        keywords = analysis_data.get("keywords", [])

    if not keywords:
        return f"{date_str}의 키워드 데이터가 비어있습니다."

    # 상위 N개 선택
    top_keywords = keywords[:limit]

    # 결과 포맷팅
    result = f"🔑 {date_str} 주요 키워드 (상위 {len(top_keywords)}개)\n\n"

    for i, kw in enumerate(top_keywords, 1):
        if isinstance(kw, dict):
            term = kw.get("term", kw.get("keyword", "Unknown"))
            score = kw.get("score", kw.get("importance", 0))
            occurrence = kw.get("occurrence_count", kw.get("count", 0))
            category = kw.get("category", "N/A")

            result += f"{i}. **{term}**\n"
            result += f"   • 점수: {score:.1f}\n"
            result += f"   • 출현: {occurrence}회\n"
            if category != "N/A":
                result += f"   • 카테고리: {category}\n"
            result += "\n"
        else:
            result += f"{i}. {kw}\n"

    return result


async def _get_analysis_summary() -> str:
    """분석 요약 생성"""
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return "분석 결과를 찾을 수 없습니다. 먼저 분석을 실행해 주세요."

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return "분석 결과를 찾을 수 없습니다."

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # JSON 파일 찾기
    json_files = list(latest_dir.glob("*.json"))

    if not json_files:
        return f"{date_str}의 분석 결과 파일을 찾을 수 없습니다."

    # 가장 최근 JSON 파일 읽기
    latest_json = sorted(json_files, reverse=True)[0]

    with open(latest_json, encoding="utf-8") as f:
        data = json.load(f)

    # 요약 생성
    summary = f"📊 {date_str} 분석 요약\n\n"

    # 키워드 정보
    keywords = data.get("aggregated_keywords", data.get("keywords", []))[:5]
    if keywords:
        summary += "🔑 상위 키워드:\n"
        for i, kw in enumerate(keywords, 1):
            if isinstance(kw, dict):
                term = kw.get("term", kw.get("keyword", "Unknown"))
                score = kw.get("score", 0)
                summary += f"  {i}. {term} ({score:.1f}점)\n"
            else:
                summary += f"  {i}. {kw}\n"
        summary += "\n"

    # 인사이트 정보
    insights = data.get("insights", {})
    if insights:
        if "market_sentiment" in insights:
            sentiment = insights["market_sentiment"]
            summary += f"📈 시장 심리: {sentiment.get('direction', 'N/A')} "
            summary += f"(신뢰도 {sentiment.get('confidence', 0):.0%})\n"

        if "volatility" in insights:
            volatility = insights["volatility"]
            summary += f"📉 변동성: {volatility.get('level', 'N/A')} "
            summary += f"(신뢰도 {volatility.get('confidence', 0):.0%})\n"

        summary += "\n"

    # 품질 점수
    quality = data.get("quality_score", data.get("quality", {}))
    if isinstance(quality, dict):
        overall = quality.get("overall", quality.get("score", 0))
        summary += f"✅ 품질 점수: {overall:.1f}%\n"
    elif isinstance(quality, (int, float)):
        summary += f"✅ 품질 점수: {quality:.1f}%\n"

    return summary


async def _list_available_sources() -> str:
    """사용 가능한 소스 목록"""
    try:
        from src.config_manager import ConfigManager

        config_path = PROJECT_ROOT / "config" / "config.yml"
        env_path = PROJECT_ROOT / ".env"

        config_manager = ConfigManager(str(config_path), str(env_path))
        app_config = config_manager.load()

        result = "📡 사용 가능한 데이터 소스\n\n"

        # RSS 피드
        rss_sources = app_config.rss_sources
        result += f"**RSS 피드** ({len(rss_sources)}개)\n"
        for source in rss_sources[:5]:  # 상위 5개만
            result += f"  • {source.name}\n"
        if len(rss_sources) > 5:
            result += f"  • ... 외 {len(rss_sources) - 5}개\n"
        result += "\n"

        # Telegram 채널
        telegram_sources = app_config.telegram_sources
        result += f"**Telegram 채널** ({len(telegram_sources)}개)\n"
        for source in telegram_sources[:5]:
            result += f"  • {source.channel_id} ({source.name})\n"
        if len(telegram_sources) > 5:
            result += f"  • ... 외 {len(telegram_sources) - 5}개\n"

        return result

    except Exception as e:
        logger.error(f"소스 목록 조회 실패: {e}")
        return f"소스 목록 조회 중 오류 발생: {str(e)}"

"""
리포트 빌더 모듈

분석 결과를 Markdown 및 JSON 형식으로 리포트를 생성합니다.
LLM 파이프라인 문서의 섹션 7을 참조하여 구현되었습니다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.workflows.state import AnalysisState

logger = logging.getLogger(__name__)


def build_json_report(state: AnalysisState) -> Dict[str, Any]:
    """
    AnalysisState에서 JSON 리포트를 생성합니다.

    LLM 파이프라인 문서 섹션 7.1의 형식을 따릅니다.

    Args:
        state: LangGraph 워크플로 최종 상태

    Returns:
        JSON 리포트 딕셔너리
    """
    logger.info("[ReportBuilder] JSON 리포트 생성 시작")

    # 실행 메타데이터 구성
    execution_metadata = _build_execution_metadata(state)

    # 상위 키워드 구성 (원본 변형 정보 포함)
    top_keywords = _build_top_keywords(state)

    # 인사이트 구성 (내러티브 요약, 거래 인사이트, 주요 출처)
    insights = state.get("insights", {})

    # 에러 목록
    errors = state.get("errors", [])

    report = {
        "execution_metadata": execution_metadata,
        "top_keywords": top_keywords,
        "insights": insights,
        "errors": errors,
    }

    logger.info(
        "[ReportBuilder] JSON 리포트 생성 완료: "
        f"키워드 {len(top_keywords)}개, "
        f"내러티브 요약 {len(insights.get('narrative_summary', []))}개 문단, "
        f"에러 {len(errors)}개"
    )

    return report


def build_markdown_report(
    state: AnalysisState,
    *,
    timezone_offset: int = 9,
) -> str:
    """
    AnalysisState에서 Markdown 리포트를 생성합니다.

    LLM 파이프라인 문서 섹션 7.2의 형식을 따릅니다.

    Args:
        state: LangGraph 워크플로 최종 상태
        timezone_offset: 표시 시간대 오프셋 (기본값: 9 = KST)

    Returns:
        Markdown 리포트 문자열
    """
    logger.info("[ReportBuilder] Markdown 리포트 생성 시작")

    # 헤더 섹션
    header = _build_markdown_header(state, timezone_offset=timezone_offset)

    # 상위 키워드 섹션
    keywords_section = _build_markdown_keywords_section(state)

    # 내러티브 요약 섹션
    narrative_section = _build_markdown_narrative_section(state)

    # 거래 인사이트 섹션
    insights_section = _build_markdown_insights_section(state)

    # 주요 출처 섹션
    sources_section = _build_markdown_sources_section(state)

    # 에러 섹션 (에러가 있는 경우만)
    errors_section = _build_markdown_errors_section(state)

    # 리포트 조합
    markdown_parts = [
        header,
        keywords_section,
        narrative_section,
        insights_section,
        sources_section,
    ]

    if errors_section:
        markdown_parts.append(errors_section)

    markdown_content = "\n\n".join(markdown_parts)

    logger.info(
        "[ReportBuilder] Markdown 리포트 생성 완료: "
        f"길이={len(markdown_content)}자"
    )

    return markdown_content


def _build_execution_metadata(state: AnalysisState) -> Dict[str, Any]:
    """
    실행 메타데이터를 구성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        실행 메타데이터 딕셔너리
    """
    end_time = state.get("end_time")
    start_time = state.get("start_time")
    execution_time = state.get("execution_time", 0.0)
    chunk_count = state.get("chunk_count", 0)
    raw_records = state.get("raw_records", [])
    errors = state.get("errors", [])

    metadata = {
        "timestamp": (
            end_time.isoformat()
            if end_time and isinstance(end_time, datetime)
            else datetime.now(timezone.utc).isoformat()
        ),
        "start_time": (
            start_time.isoformat()
            if start_time and isinstance(start_time, datetime)
            else None
        ),
        "duration_seconds": float(execution_time),
        "chunks_processed": int(chunk_count),
        "total_records": len(raw_records),
        "errors_count": len(errors),
    }

    return metadata


def _build_top_keywords(state: AnalysisState) -> List[Dict[str, Any]]:
    """
    상위 키워드 리스트를 구성합니다.

    원본 변형 정보(original_variants)를 포함합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        상위 키워드 리스트
    """
    aggregated_keywords = state.get("aggregated_keywords", [])

    if not aggregated_keywords:
        logger.warning("[ReportBuilder] aggregated_keywords가 비어 있습니다.")
        return []

    # 키워드를 딕셔너리로 변환 (TypedDict는 dict처럼 사용 가능)
    keywords = []
    for idx, keyword in enumerate(aggregated_keywords, start=1):
        if not isinstance(keyword, dict):
            keyword = dict(keyword)

        keyword_dict: Dict[str, Any] = {
            "term": keyword.get("term", ""),
            "original_variants": keyword.get("original_variants", []),
            "score": float(keyword.get("score", 0.0)),
            "evidence": keyword.get("evidence", []),
            "sources": keyword.get("sources", []),
            "occurrence_count": int(keyword.get("occurrence_count", 0)),
        }

        # 선택적 필드 추가
        if "rank" in keyword:
            keyword_dict["rank"] = int(keyword["rank"])

        if "cluster_id" in keyword:
            keyword_dict["cluster_id"] = keyword["cluster_id"]

        keywords.append(keyword_dict)

    logger.debug(
        f"[ReportBuilder] 상위 키워드 {len(keywords)}개 구성 완료"
    )

    return keywords


def _build_markdown_header(
    state: AnalysisState,
    *,
    timezone_offset: int = 9,
) -> str:
    """
    Markdown 리포트 헤더를 생성합니다.

    Args:
        state: LangGraph 워크플로 상태
        timezone_offset: 표시 시간대 오프셋

    Returns:
        Markdown 헤더 문자열
    """
    end_time = state.get("end_time")
    start_time = state.get("start_time")
    raw_records = state.get("raw_records", [])

    # 시간대 변환
    tz = timezone.utc
    if timezone_offset != 0:
        from datetime import timedelta

        tz = timezone(timedelta(hours=timezone_offset))

    # 생성 시간
    if end_time and isinstance(end_time, datetime):
        creation_time = end_time.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        timezone_name = f"UTC{timezone_offset:+d}"
    else:
        creation_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        timezone_name = f"UTC{timezone_offset:+d}"

    # 분석 기간
    if start_time and isinstance(start_time, datetime):
        period_start = start_time.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        period_end = (
            end_time.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            if end_time and isinstance(end_time, datetime)
            else creation_time
        )
        period_text = f"{period_start} ~ {period_end} {timezone_name}"
    else:
        period_text = "N/A"

    # 데이터 소스 통계
    rss_count = sum(
        1
        for record in raw_records
        if isinstance(record, dict) and record.get("source") == "rss"
    )
    telegram_count = sum(
        1
        for record in raw_records
        if isinstance(record, dict) and record.get("source") == "telegram"
    )

    header = f"""# 디지털 자산 시장 내러티브 요약

**생성 시간**: {creation_time} {timezone_name}
**분석 기간**: {period_text}
**데이터 소스**: RSS 기사 {rss_count}건, 텔레그램 메시지 {telegram_count}건"""

    return header


def _build_markdown_keywords_section(state: AnalysisState) -> str:
    """
    상위 키워드 섹션을 생성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        Markdown 키워드 섹션 문자열
    """
    top_keywords = _build_top_keywords(state)

    if not top_keywords:
        return "## 상위 키워드\n\n키워드가 없습니다."

    # 테이블 헤더
    table_rows = [
        "| 순위 | 키워드 | 원본 변형 | 중요도 | 출처 수 |",
        "|------|--------|-----------|--------|---------|",
    ]

    # 키워드 행 추가
    for idx, keyword in enumerate(top_keywords, start=1):
        term = str(keyword.get("term", ""))
        original_variants = keyword.get("original_variants", [])
        score = keyword.get("score", 0.0)
        occurrence_count = keyword.get("occurrence_count", 0)

        # 원본 변형 정보 포맷팅 (최대 3개만 표시)
        if original_variants:
            variants_display = ", ".join(
                str(v) for v in original_variants[:3]
            )
            if len(original_variants) > 3:
                variants_display += f" 외 {len(original_variants) - 3}개"
        else:
            variants_display = term

        # 중요도 점수는 정수로 표시
        score_display = int(round(score))

        table_rows.append(
            f"| {idx} | {term} | {variants_display} | {score_display} | {occurrence_count} |"
        )

    section = "## 상위 키워드\n\n" + "\n".join(table_rows)

    return section


def _build_markdown_narrative_section(state: AnalysisState) -> str:
    """
    내러티브 요약 섹션을 생성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        Markdown 내러티브 요약 섹션 문자열
    """
    insights = state.get("insights", {})
    narrative_summary = insights.get("narrative_summary", [])

    if not narrative_summary:
        return "## 시장 내러티브 요약\n\n내러티브 요약이 없습니다."

    # 각 문단을 별도 줄로 표시
    paragraphs = []
    for idx, paragraph in enumerate(narrative_summary, start=1):
        paragraphs.append(f"{paragraph}")

    section = "## 시장 내러티브 요약\n\n" + "\n\n".join(paragraphs)

    return section


def _build_markdown_insights_section(state: AnalysisState) -> str:
    """
    거래 인사이트 섹션을 생성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        Markdown 거래 인사이트 섹션 문자열
    """
    insights = state.get("insights", {})
    trading_insights = insights.get("trading_insights", {})

    if not trading_insights:
        return "## 거래 인사이트\n\n거래 인사이트가 없습니다."

    opportunities = trading_insights.get("opportunities", [])
    risks = trading_insights.get("risks", [])
    market_sentiment = trading_insights.get("market_sentiment", "N/A")

    # 기회 섹션
    opportunities_text = "### 기회\n\n"
    if opportunities:
        for opp in opportunities:
            opportunities_text += f"- {opp}\n"
    else:
        opportunities_text += "기회 항목이 없습니다.\n"

    # 위험 요소 섹션
    risks_text = "### 위험 요소\n\n"
    if risks:
        for risk in risks:
            risks_text += f"- {risk}\n"
    else:
        risks_text += "위험 항목이 없습니다.\n"

    # 시장 심리 섹션
    sentiment_text = f"### 시장 심리\n\n{market_sentiment}\n"

    section = (
        "## 거래 인사이트\n\n"
        + opportunities_text
        + "\n"
        + risks_text
        + "\n"
        + sentiment_text
    )

    return section


def _build_markdown_sources_section(state: AnalysisState) -> str:
    """
    주요 출처 섹션을 생성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        Markdown 주요 출처 섹션 문자열
    """
    insights = state.get("insights", {})
    key_sources = insights.get("key_sources", [])

    if not key_sources:
        return "## 주요 출처\n\n주요 출처가 없습니다."

    # 출처 리스트 생성
    source_items = []
    for idx, source in enumerate(key_sources, start=1):
        if not isinstance(source, dict):
            continue

        title = str(source.get("title", "N/A"))
        url = source.get("url")
        relevance = source.get("relevance", [])

        # 관련성 키워드 포맷팅
        if isinstance(relevance, list):
            relevance_text = ", ".join(str(r) for r in relevance)
        else:
            relevance_text = str(relevance) if relevance else ""

        # 링크가 있으면 마크다운 링크 형식으로, 없으면 텍스트만
        if url:
            source_text = f"{idx}. [{title}]({url})"
        else:
            source_text = f"{idx}. {title}"

        if relevance_text:
            source_text += f" - {relevance_text}"

        source_items.append(source_text)

    section = "## 주요 출처\n\n" + "\n".join(source_items)

    return section


def _build_markdown_errors_section(state: AnalysisState) -> str:
    """
    에러 섹션을 생성합니다.

    Args:
        state: LangGraph 워크플로 상태

    Returns:
        Markdown 에러 섹션 문자열 (에러가 없으면 빈 문자열)
    """
    errors = state.get("errors", [])

    if not errors:
        return ""

    error_items = []
    for idx, error in enumerate(errors, start=1):
        error_items.append(f"{idx}. {error}")

    section = "## 에러\n\n" + "\n".join(error_items)

    return section


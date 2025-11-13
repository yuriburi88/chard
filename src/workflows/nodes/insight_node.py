"""
InsightNode 구현

LLM 파이프라인 문서의 섹션 3.4를 기반으로 최종 키워드에서
시장 내러티브 요약과 거래 인사이트를 생성합니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import List, Mapping, Sequence

from src.workflows.llm_client import GeminiClient
from src.workflows.prompts import (
    build_insight_prompt,
    parse_insight_response,
    prepare_insight_prompt_inputs,
)
from src.workflows.state import AnalysisState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _InsightSettings:
    """
    InsightNode 수행에 필요한 설정 값을 저장하는 자료형.
    """

    model: str
    temperature: float
    max_tokens: int
    summary_paragraphs: int
    highlight_limit: int
    include_excerpts: bool


async def insight_node(state: AnalysisState) -> AnalysisState:
    """
    AggregatorNode 결과를 기반으로 내러티브 요약 및 거래 인사이트를 생성합니다.

    처리 단계:
        1. 입력 데이터 검증 및 설정 로드
        2. 프롬프트 구성에 사용할 키워드/출처 정보 정규화
        3. Gemini API 호출을 통한 내러티브/인사이트 생성
        4. 응답 파싱 및 상태 업데이트

    Args:
        state: LangGraph 상태 (최종 키워드와 원본 데이터 포함)

    Returns:
        인사이트가 추가된 LangGraph 상태
    """
    logger.info("[InsightNode] 인사이트 생성 단계 시작")

    aggregated_keywords = list(state.get("aggregated_keywords", []))

    if not aggregated_keywords:
        warning_msg = "InsightNode: aggregated_keywords가 비어 있어 인사이트를 생성할 수 없습니다."

        logger.warning("[InsightNode] %s", warning_msg)

        return {
            **state,
            "insights": {},
            "errors": state.get("errors", []) + [warning_msg],
        }

    raw_records = list(state.get("raw_records", []))
    raw_record_count = len(raw_records)

    logger.info(
        "[InsightNode] 입력 통계: aggregated_keywords=%d, raw_records=%d",
        len(aggregated_keywords),
        raw_record_count,
    )

    config_obj = state.get("config", {})
    config_mapping: Mapping[str, object] = config_obj if isinstance(config_obj, Mapping) else {}

    try:
        settings = _resolve_insight_settings(config_mapping)
    except ValueError as exc:
        error_msg = f"InsightNode: 설정 로드 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)

        return {
            **state,
            "insights": {},
            "errors": state.get("errors", []) + [error_msg],
        }

    logger.debug(
        "[InsightNode] 사용 설정: %s",
        json.dumps(asdict(settings), ensure_ascii=False),
    )

    errors: List[str] = list(state.get("errors", []))

    # ID 매핑 가져오기 (evidence_ids를 원본 텍스트로 복원하기 위해)
    id_mapping = state.get("id_mapping")
    
    try:
        prepared_inputs = prepare_insight_prompt_inputs(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=settings.summary_paragraphs,
            max_sources=settings.highlight_limit,
            include_excerpts=settings.include_excerpts,
            id_mapping=id_mapping,
        )
    except ValueError as exc:
        error_msg = f"InsightNode: 프롬프트 입력 준비 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)
        errors.append(error_msg)

        return {
            **state,
            "insights": {},
            "errors": errors,
        }

    keyword_payload = prepared_inputs.get("keywords", [])
    source_highlights = prepared_inputs.get("source_highlights", [])

    logger.info(
        "[InsightNode] 키워드 페이로드: %s",
        json.dumps(keyword_payload, ensure_ascii=False),
    )

    logger.info(
        "[InsightNode] 출처 하이라이트: %s",
        json.dumps(source_highlights, ensure_ascii=False),
    )

    try:
        prompt = build_insight_prompt(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=settings.summary_paragraphs,
            max_sources=settings.highlight_limit,
            include_excerpts=settings.include_excerpts,
            prepared_inputs=prepared_inputs,
            id_mapping=id_mapping,
        )
    except ValueError as exc:
        error_msg = f"InsightNode: 프롬프트 생성 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)
        errors.append(error_msg)

        return {
            **state,
            "insights": {},
            "errors": errors,
        }

    logger.debug(
        "[InsightNode] 프롬프트 생성 완료: 길이=%d, 내용=%s",
        len(prompt),
        prompt,
    )

    llm_client: GeminiClient

    try:
        llm_client = GeminiClient(
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = f"InsightNode: GeminiClient 초기화 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)
        errors.append(error_msg)

        return {
            **state,
            "insights": {},
            "errors": errors,
        }

    try:
        response_text = await llm_client.generate_content_async(
            prompt=prompt,
            response_format="json",
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = f"InsightNode: Gemini API 호출 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)
        errors.append(error_msg)

        return {
            **state,
            "insights": {},
            "errors": errors,
        }

    logger.debug(
        "[InsightNode] LLM 응답 수신: 길이=%d, 내용=%s",
        len(response_text),
        response_text,
    )

    try:
        insights = parse_insight_response(response_text)
    except ValueError as exc:
        error_msg = f"InsightNode: 응답 파싱 실패 - {exc}"

        logger.error("[InsightNode] %s", error_msg, exc_info=True)
        errors.append(error_msg)

        return {
            **state,
            "insights": {},
            "errors": errors,
        }

    logger.info(
        "[InsightNode] 내러티브 요약 %d개, 기회 %d개, 위험 %d개 생성",
        len(insights["narrative_summary"]),
        len(insights["trading_insights"]["opportunities"]),
        len(insights["trading_insights"]["risks"]),
    )

    logger.info(
        "[InsightNode] 최종 인사이트: %s",
        json.dumps(insights, ensure_ascii=False),
    )

    return {
        **state,
        "insights": insights,
        "insight_inputs": prepared_inputs,
        "errors": errors,
    }


def _resolve_insight_settings(config: Mapping[str, object]) -> _InsightSettings:
    """
    config.yml 정보를 InsightNode에서 사용하기 편한 형태로 변환합니다.

    Args:
        config: ConfigManager에서 전달된 설정 딕셔너리.

    Returns:
        InsightNode 설정 값이 포함된 `_InsightSettings` 인스턴스.

    Raises:
        ValueError: 필수 설정이 누락되거나 잘못된 경우.
    """
    llm_config_raw = config.get("llm", {})
    output_config_raw = config.get("output", {})

    llm_config: Mapping[str, object] = llm_config_raw if isinstance(llm_config_raw, Mapping) else {}
    output_config: Mapping[str, object] = output_config_raw if isinstance(output_config_raw, Mapping) else {}

    model = str(llm_config.get("insight_model", llm_config.get("model", "gemini-2.0-flash-exp"))).strip()
    if not model:
        raise ValueError("InsightNode: 사용할 LLM 모델을 찾을 수 없습니다.")

    temperature = float(llm_config.get("insight_temperature", llm_config.get("temperature", 0.1) or 0.1))
    max_tokens = int(llm_config.get("insight_max_tokens", llm_config.get("max_tokens", 4000) or 4000))

    summary_paragraphs = int(output_config.get("summary_paragraphs", 4) or 4)
    highlight_limit = int(output_config.get("key_source_limit", 5) or 5)
    include_excerpts = bool(output_config.get("insight_include_excerpts", True))

    if summary_paragraphs < 1:
        raise ValueError("InsightNode: summary_paragraphs 값은 1 이상이어야 합니다.")

    if highlight_limit < 1:
        raise ValueError("InsightNode: key_source_limit 값은 1 이상이어야 합니다.")

    return _InsightSettings(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        summary_paragraphs=summary_paragraphs,
        highlight_limit=highlight_limit,
        include_excerpts=include_excerpts,
    )


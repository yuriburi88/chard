"""
InsightNode 구현

LLM 파이프라인 문서의 섹션 3.4를 기반으로 최종 키워드에서
시장 내러티브 요약과 거래 인사이트를 생성합니다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from src.workflows.llm_client import GeminiClient
from src.workflows.prompts import (
    build_crypto_keypoints_prompt,
    build_crypto_narrative_prompt,
    build_insight_prompt,
    build_integrated_keypoints_prompt,
    build_integrated_narrative_prompt,
    build_macro_keypoints_prompt,
    build_macro_narrative_prompt,
    parse_insight_response,
    parse_keypoints_response,
    parse_narrative_response,
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

    세분화 모드 활성화 시 (3단계):
        1. Macro 내러티브 생성 (1회 LLM 호출)
        2. Crypto 내러티브 생성 (1회 LLM 호출)
        3. 통합 내러티브 생성 - Macro/Crypto 참조 (1회 LLM 호출)
        4. 거래 인사이트 생성 (기존 방식)

    세분화 모드 비활성화 시:
        기존 방식대로 단일 내러티브 생성

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
    config_mapping: Mapping[str, object] = (
        config_obj if isinstance(config_obj, Mapping) else {}
    )

    # 내러티브 세분화 설정 확인
    narrative_config = config_mapping.get("narrative", {})
    if not isinstance(narrative_config, Mapping):
        narrative_config = {}

    enable_segmentation = narrative_config.get("enable_segmentation", True)

    # DEPRECATED: enable_segmentation=false는 더 이상 지원되지 않습니다.
    # 2단계 Key Points 기반 내러티브 생성 방식이 항상 사용됩니다.
    if not enable_segmentation:
        logger.warning(
            "[InsightNode] ⚠️ DEPRECATED: enable_segmentation=false 설정은 더 이상 지원되지 않습니다. "
            "2단계 Key Points 기반 내러티브 생성 방식이 항상 사용됩니다. "
            "config.yml에서 enable_segmentation 설정을 제거해주세요."
        )
        # 강제로 활성화 (deprecated 설정 무시)
        enable_segmentation = True

    logger.info(
        "[InsightNode] 내러티브 세분화 모드: %s",
        "활성화" if enable_segmentation else "비활성화",
    )

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

    errors: list[str] = list(state.get("errors", []))

    # ID 매핑 가져오기 (evidence_ids를 원본 텍스트로 복원하기 위해)
    id_mapping = state.get("id_mapping")

    # 세분화 모드 분기 처리
    if enable_segmentation:
        categorized_keywords = state.get("categorized_keywords", {})

        if not categorized_keywords:
            logger.warning(
                "[InsightNode] categorized_keywords가 비어있어 세분화를 건너뜁니다."
            )
            enable_segmentation = False
        else:
            try:
                insights = await _generate_segmented_narratives(
                    state=state,
                    settings=settings,
                    narrative_config=narrative_config,
                    categorized_keywords=categorized_keywords,
                    raw_records=raw_records,
                    errors=errors,
                )

                logger.info("[InsightNode] 세분화된 내러티브 생성 완료")

                # Phase 3: 품질 평가 수행
                quality_metrics_dict = None
                try:
                    from pathlib import Path

                    from src.workflows.quality_metrics import QualityEvaluator

                    evaluator = QualityEvaluator()

                    # 동적 키워드 캐시 로드
                    dynamic_cache_file = narrative_config.get(
                        "dynamic_keywords", {}
                    ).get("cache_file", "dynamic_keywords_cache.json")
                    dynamic_cache = {}
                    try:
                        cache_path = Path(dynamic_cache_file)
                        if cache_path.exists():
                            with open(cache_path, encoding="utf-8") as f:
                                dynamic_cache = json.load(f)
                    except Exception:
                        dynamic_cache = {}

                    # 내러티브 텍스트 추출 (NarrativeWithKeyPoints 구조 지원)
                    # 2-카테고리 시스템: macro, crypto, integrated
                    narratives_data = insights.get("narratives", {})

                    # 새로운 구조: {"macro": {"key_points": [...], "paragraphs": [...]}}
                    # 기존 구조: {"macro": ["문단1", "문단2"]}
                    def extract_paragraphs(category_data):
                        """NarrativeWithKeyPoints 또는 list[str]에서 paragraphs 추출"""
                        if isinstance(category_data, dict):
                            # 새로운 구조: paragraphs 필드에서 추출
                            return category_data.get("paragraphs", [])
                        elif isinstance(category_data, list):
                            # 기존 구조: 직접 반환
                            return category_data
                        return []

                    narratives_for_quality = {
                        "macro": "\n\n".join(extract_paragraphs(narratives_data.get("macro", []))),
                        "crypto": "\n\n".join(extract_paragraphs(narratives_data.get("crypto", []))),
                        "integrated": "\n\n".join(
                            extract_paragraphs(narratives_data.get("integrated", []))
                        ),
                    }

                    # 품질 평가 실행
                    quality_metrics = evaluator.evaluate(
                        categorized_keywords=categorized_keywords,
                        narratives=narratives_for_quality,
                        dynamic_keywords_cache=dynamic_cache,
                    )

                    # 품질 리포트 로깅
                    quality_report = evaluator.print_report(quality_metrics)
                    logger.info("\n" + quality_report)

                    # 경고가 있으면 errors에 추가
                    if quality_metrics.warnings:
                        for warning in quality_metrics.warnings:
                            logger.warning(f"[품질 평가] {warning}")

                    # Dataclass를 dict로 변환 (JSON 직렬화 가능하도록)
                    quality_metrics_dict = asdict(quality_metrics)

                except Exception as eval_exc:
                    logger.warning(
                        f"[InsightNode] 품질 평가 실패: {eval_exc}", exc_info=True
                    )

                return {
                    **state,
                    "insights": insights,
                    "quality_metrics": quality_metrics_dict,
                    "errors": errors,
                }
            except Exception as exc:
                error_msg = f"InsightNode: 세분화된 내러티브 생성 실패 - {exc}"
                logger.error(f"[InsightNode] {error_msg}", exc_info=True)
                errors.append(error_msg)
                # Fall back to non-segmented mode
                enable_segmentation = False
                logger.warning("[InsightNode] 세분화 실패로 기본 모드로 전환합니다.")

    # 세분화 비활성화 시 또는 세분화 실패 시 기본 모드로 실행
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

    # Phase 3: 품질 평가 수행 (비세분화 모드)
    quality_metrics_dict = None
    try:
        from pathlib import Path

        from src.workflows.quality_metrics import QualityEvaluator

        evaluator = QualityEvaluator()

        # 동적 키워드 캐시 로드
        dynamic_cache_file = narrative_config.get("dynamic_keywords", {}).get(
            "cache_file", "dynamic_keywords_cache.json"
        )
        dynamic_cache = {}
        try:
            cache_path = Path(dynamic_cache_file)
            if cache_path.exists():
                with open(cache_path, encoding="utf-8") as f:
                    dynamic_cache = json.load(f)
        except Exception:
            dynamic_cache = {}

        # 내러티브 텍스트 추출 (비세분화 모드)
        # 2-카테고리 시스템: macro, crypto, integrated
        narratives = {
            "macro": "",
            "crypto": "",
            "integrated": "\n\n".join(insights.get("narrative_summary", [])),
        }

        # 품질 평가 실행
        quality_metrics = evaluator.evaluate(
            categorized_keywords=categorized_keywords,
            narratives=narratives,
            dynamic_keywords_cache=dynamic_cache,
        )

        # 품질 리포트 로깅
        quality_report = evaluator.print_report(quality_metrics)
        logger.info("\n" + quality_report)

        # 경고가 있으면 errors에 추가
        if quality_metrics.warnings:
            for warning in quality_metrics.warnings:
                logger.warning(f"[품질 평가] {warning}")

        # Dataclass를 dict로 변환 (JSON 직렬화 가능하도록)
        quality_metrics_dict = asdict(quality_metrics)

    except Exception as eval_exc:
        logger.warning(f"[InsightNode] 품질 평가 실패: {eval_exc}", exc_info=True)

    return {
        **state,
        "insights": insights,
        "insight_inputs": prepared_inputs,
        "quality_metrics": quality_metrics_dict,
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

    llm_config: Mapping[str, object] = (
        llm_config_raw if isinstance(llm_config_raw, Mapping) else {}
    )
    output_config: Mapping[str, object] = (
        output_config_raw if isinstance(output_config_raw, Mapping) else {}
    )

    model = str(
        llm_config.get("insight_model", llm_config.get("model", "gemini-2.0-flash-exp"))
    ).strip()
    if not model:
        raise ValueError("InsightNode: 사용할 LLM 모델을 찾을 수 없습니다.")

    temperature = float(
        llm_config.get("insight_temperature", llm_config.get("temperature", 0.1) or 0.1)
    )
    max_tokens = int(
        llm_config.get("insight_max_tokens", llm_config.get("max_tokens", 4000) or 4000)
    )

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


async def _generate_keypoints(
    llm_client: GeminiClient,
    category: str,
    keywords: list,
    source_highlights: list,
    economic_events: list,
) -> dict:
    """
    1단계: Key Points를 생성합니다.

    Args:
        llm_client: GeminiClient 인스턴스
        category: 카테고리 ("macro", "crypto", "integrated")
        keywords: 키워드 리스트
        source_highlights: 소스 하이라이트 리스트
        economic_events: Economic Calendar 이벤트 리스트

    Returns:
        Key Points 딕셔너리 {"key_points": [...], "source_mapping": {...}}

    Raises:
        Exception: LLM 호출 또는 파싱 실패 시
    """
    if category == "macro":
        prompt = build_macro_keypoints_prompt(
            keywords, source_highlights, economic_events
        )
    elif category == "crypto":
        prompt = build_crypto_keypoints_prompt(
            keywords, source_highlights, economic_events
        )
    else:
        raise ValueError(f"지원하지 않는 카테고리: {category}")

    response_text = await llm_client.generate_content_async(
        prompt=prompt, response_format="json"
    )

    return parse_keypoints_response(response_text, category=f"{category.capitalize()} Key Points")


async def _generate_integrated_keypoints(
    llm_client: GeminiClient,
    macro_key_points: list[str],
    crypto_key_points: list[str],
    all_keywords: list,
    economic_events: list,
) -> dict:
    """
    1단계: 통합 Key Points를 생성합니다.

    Args:
        llm_client: GeminiClient 인스턴스
        macro_key_points: Macro Key Points 리스트
        crypto_key_points: Crypto Key Points 리스트
        all_keywords: 전체 키워드 리스트
        economic_events: Economic Calendar 이벤트 리스트

    Returns:
        Key Points 딕셔너리 {"key_points": [...], "source_mapping": {...}}
    """
    prompt = build_integrated_keypoints_prompt(
        macro_key_points, crypto_key_points, all_keywords, economic_events
    )

    response_text = await llm_client.generate_content_async(
        prompt=prompt, response_format="json"
    )

    return parse_keypoints_response(response_text, category="Integrated Key Points")


def _filter_sources_by_keypoints(
    source_mapping: dict[str, list],
    source_highlights: list[dict],
) -> list[dict]:
    """
    source_mapping을 기반으로 관련 소스만 필터링합니다.

    Args:
        source_mapping: Key Point → 소스 ID 매핑
        source_highlights: 전체 소스 하이라이트 리스트

    Returns:
        필터링된 소스 하이라이트 리스트 (매핑 실패 시 원본 반환)
    """
    if not source_mapping:
        logger.warning(
            "[_filter_sources_by_keypoints] source_mapping이 비어있어 전체 소스를 반환합니다."
        )
        return source_highlights

    # source_mapping에서 모든 소스 ID 수집
    all_source_ids: set = set()
    for ids in source_mapping.values():
        if isinstance(ids, list):
            for id_val in ids:
                if isinstance(id_val, int):
                    all_source_ids.add(id_val)

    if not all_source_ids:
        logger.warning(
            "[_filter_sources_by_keypoints] 유효한 소스 ID가 없어 전체 소스를 반환합니다."
        )
        return source_highlights

    # 소스 필터링 (ID 기반)
    # source_highlights에는 직접 ID가 없으므로 인덱스 기반으로 필터링
    # 또는 전체 소스를 반환 (현재 구현에서는 전체 반환)
    # TODO: 실제 소스 ID 매핑 구현 필요
    logger.info(
        f"[_filter_sources_by_keypoints] 참조된 소스 ID: {len(all_source_ids)}개"
    )

    return source_highlights


async def _generate_narrative_from_keypoints(
    llm_client: GeminiClient,
    category: str,
    key_points: list[str],
    keywords: list,
    source_highlights: list,
    economic_events: list,
    num_paragraphs: int = 2,
    macro_narrative: list[str] | None = None,
    crypto_narrative: list[str] | None = None,
) -> list[str]:
    """
    2단계: Key Points를 기반으로 Narrative를 생성합니다.

    Args:
        llm_client: GeminiClient 인스턴스
        category: 카테고리 ("macro", "crypto", "integrated")
        key_points: Key Points 리스트
        keywords: 키워드 리스트
        source_highlights: 소스 하이라이트 리스트
        economic_events: Economic Calendar 이벤트 리스트
        num_paragraphs: 생성할 문단 수
        macro_narrative: Macro 내러티브 (integrated 전용)
        crypto_narrative: Crypto 내러티브 (integrated 전용)

    Returns:
        내러티브 문단 리스트

    Raises:
        Exception: LLM 호출 또는 파싱 실패 시
    """
    if category == "macro":
        prompt = build_macro_narrative_prompt(
            keywords, source_highlights, economic_events, key_points=key_points
        )
    elif category == "crypto":
        prompt = build_crypto_narrative_prompt(
            keywords, source_highlights, num_paragraphs, economic_events, key_points=key_points
        )
    elif category == "integrated":
        prompt = build_integrated_narrative_prompt(
            macro_narrative or [],
            crypto_narrative or [],
            keywords,
            num_paragraphs,
            economic_events,
            key_points=key_points,
        )
    else:
        raise ValueError(f"지원하지 않는 카테고리: {category}")

    response_text = await llm_client.generate_content_async(
        prompt=prompt, response_format="json"
    )

    return parse_narrative_response(response_text, category.capitalize())


async def _generate_segmented_narratives(
    state: AnalysisState,
    settings: _InsightSettings,
    narrative_config: Mapping[str, object],
    categorized_keywords: Mapping[str, Sequence],
    raw_records: list,
    errors: list[str],
) -> dict:
    """
    세분화된 내러티브를 생성합니다 (2단계 LLM 호출 방식).

    1단계: Key Points 생성 (Macro, Crypto, Integrated)
    2단계: Key Points 기반 Narrative 생성 (Macro, Crypto, Integrated)

    총 6회 LLM 호출:
    - Macro: Key Points 생성 → Narrative 생성 (2회)
    - Crypto: Key Points 생성 → Narrative 생성 (2회)
    - Integrated: Key Points 생성 → Narrative 생성 (2회)

    Args:
        state: LangGraph 상태
        settings: InsightNode 설정
        narrative_config: 내러티브 설정
        categorized_keywords: 카테고리별 키워드
        raw_records: 원본 레코드
        errors: 에러 리스트 (참조로 전달)

    Returns:
        세분화된 인사이트 딕셔너리
        {
            "narratives": {
                "macro": {"key_points": [...], "paragraphs": [...], "source_mapping": {...}},
                "crypto": {"key_points": [...], "paragraphs": [...], "source_mapping": {...}},
                "integrated": {"key_points": [...], "paragraphs": [...], "source_mapping": {...}}
            },
            "trading_insights": {...},
            "key_sources": [...]
        }
    """

    # 문단 수 설정
    crypto_paragraphs = int(narrative_config.get("crypto_paragraphs", 2))
    integrated_paragraphs = int(narrative_config.get("integrated_paragraphs", 3))

    id_mapping = state.get("id_mapping")

    # 카테고리별 키워드 추출 (2-카테고리 시스템)
    macro_keywords = list(categorized_keywords.get("macro", []))
    crypto_keywords = list(categorized_keywords.get("crypto", []))
    all_keywords = list(state.get("aggregated_keywords", []))

    logger.info(
        "[InsightNode] 카테고리별 키워드 수: Macro=%d, Crypto=%d",
        len(macro_keywords),
        len(crypto_keywords),
    )

    # Economic Calendar 이벤트 필터링
    # 주의: DataNormalizer.to_dict_format()에서 source_type → source로 변환됨
    economic_events = []
    for record in raw_records:
        source = (
            record.get("source")
            if isinstance(record, dict)
            else getattr(record, "source", None)
        )
        if source == "economic_calendar":
            economic_events.append(record)

    logger.info(f"[InsightNode] Economic Calendar 이벤트: {len(economic_events)}개")

    # 출처 하이라이트 준비
    try:
        prepared_inputs = prepare_insight_prompt_inputs(
            all_keywords,
            raw_records,
            summary_paragraphs=integrated_paragraphs,
            max_sources=settings.highlight_limit,
            include_excerpts=settings.include_excerpts,
            id_mapping=id_mapping,
        )
        source_highlights = prepared_inputs.get("source_highlights", [])
    except Exception as exc:
        logger.error(f"[InsightNode] 출처 준비 실패: {exc}", exc_info=True)
        source_highlights = []

    # LLM 클라이언트 초기화
    try:
        llm_client = GeminiClient(
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except Exception as exc:
        error_msg = f"InsightNode: GeminiClient 초기화 실패 - {exc}"
        logger.error(f"[InsightNode] {error_msg}", exc_info=True)
        errors.append(error_msg)
        return {}

    # NarrativeWithKeyPoints 형식으로 결과 저장
    narratives: dict[str, dict] = {}

    # ========================================
    # 1. Macro: Key Points 생성 → Narrative 생성 (2회 LLM 호출)
    # ========================================
    macro_key_points_data: dict = {"key_points": [], "source_mapping": {}}
    if macro_keywords:
        try:
            # 1-1. Macro Key Points 생성
            logger.info("[InsightNode] Macro Key Points 생성 중 (1단계)...")
            macro_key_points_data = await _generate_keypoints(
                llm_client, "macro", macro_keywords, source_highlights, economic_events
            )
            logger.info(
                f"[InsightNode] Macro Key Points {len(macro_key_points_data['key_points'])}개 생성 완료"
            )

            # 1-2. Macro Narrative 생성 (Key Points 기반)
            logger.info("[InsightNode] Macro Narrative 생성 중 (2단계, Key Points 기반)...")
            macro_paragraphs = await _generate_narrative_from_keypoints(
                llm_client,
                "macro",
                macro_key_points_data["key_points"],
                macro_keywords,
                source_highlights,
                economic_events,
            )
            logger.info(
                f"[InsightNode] Macro Narrative {len(macro_paragraphs)}개 문단 생성 완료"
            )

            narratives["macro"] = {
                "key_points": macro_key_points_data["key_points"],
                "paragraphs": macro_paragraphs,
                "source_mapping": macro_key_points_data.get("source_mapping", {}),
            }

        except Exception as exc:
            error_msg = f"Macro 2단계 생성 실패: {exc}"
            logger.error(f"[InsightNode] {error_msg}", exc_info=True)
            errors.append(error_msg)

            # Fallback: 기존 방식으로 시도
            logger.warning("[InsightNode] Macro fallback: 기존 1단계 방식으로 재시도...")
            try:
                macro_prompt = build_macro_narrative_prompt(
                    macro_keywords, source_highlights, economic_events=economic_events
                )
                macro_response = await llm_client.generate_content_async(
                    prompt=macro_prompt, response_format="json"
                )
                macro_paragraphs = parse_narrative_response(macro_response, "Macro")
                narratives["macro"] = {
                    "key_points": [],
                    "paragraphs": macro_paragraphs,
                    "source_mapping": {},
                }
                logger.info("[InsightNode] Macro fallback 성공")
            except Exception as fallback_exc:
                logger.error(f"[InsightNode] Macro fallback 실패: {fallback_exc}")
                narratives["macro"] = {"key_points": [], "paragraphs": [], "source_mapping": {}}
    else:
        logger.warning("[InsightNode] Macro 키워드가 없어 내러티브를 건너뜁니다.")
        narratives["macro"] = {"key_points": [], "paragraphs": [], "source_mapping": {}}

    # ========================================
    # 2. Crypto: Key Points 생성 → Narrative 생성 (2회 LLM 호출)
    # ========================================
    crypto_key_points_data: dict = {"key_points": [], "source_mapping": {}}
    if crypto_keywords:
        try:
            # 2-1. Crypto Key Points 생성
            logger.info("[InsightNode] Crypto Key Points 생성 중 (1단계)...")
            crypto_key_points_data = await _generate_keypoints(
                llm_client, "crypto", crypto_keywords, source_highlights, economic_events
            )
            logger.info(
                f"[InsightNode] Crypto Key Points {len(crypto_key_points_data['key_points'])}개 생성 완료"
            )

            # 2-2. Crypto Narrative 생성 (Key Points 기반)
            logger.info("[InsightNode] Crypto Narrative 생성 중 (2단계, Key Points 기반)...")
            crypto_paragraphs_result = await _generate_narrative_from_keypoints(
                llm_client,
                "crypto",
                crypto_key_points_data["key_points"],
                crypto_keywords,
                source_highlights,
                economic_events,
                num_paragraphs=crypto_paragraphs,
            )
            logger.info(
                f"[InsightNode] Crypto Narrative {len(crypto_paragraphs_result)}개 문단 생성 완료"
            )

            narratives["crypto"] = {
                "key_points": crypto_key_points_data["key_points"],
                "paragraphs": crypto_paragraphs_result,
                "source_mapping": crypto_key_points_data.get("source_mapping", {}),
            }

        except Exception as exc:
            error_msg = f"Crypto 2단계 생성 실패: {exc}"
            logger.error(f"[InsightNode] {error_msg}", exc_info=True)
            errors.append(error_msg)

            # Fallback: 기존 방식으로 시도
            logger.warning("[InsightNode] Crypto fallback: 기존 1단계 방식으로 재시도...")
            try:
                crypto_prompt = build_crypto_narrative_prompt(
                    crypto_keywords,
                    source_highlights,
                    num_paragraphs=crypto_paragraphs,
                    economic_events=economic_events,
                )
                crypto_response = await llm_client.generate_content_async(
                    prompt=crypto_prompt, response_format="json"
                )
                crypto_paragraphs_result = parse_narrative_response(crypto_response, "Crypto")
                narratives["crypto"] = {
                    "key_points": [],
                    "paragraphs": crypto_paragraphs_result,
                    "source_mapping": {},
                }
                logger.info("[InsightNode] Crypto fallback 성공")
            except Exception as fallback_exc:
                logger.error(f"[InsightNode] Crypto fallback 실패: {fallback_exc}")
                narratives["crypto"] = {"key_points": [], "paragraphs": [], "source_mapping": {}}
    else:
        logger.warning("[InsightNode] Crypto 키워드가 없어 내러티브를 건너뜁니다.")
        narratives["crypto"] = {"key_points": [], "paragraphs": [], "source_mapping": {}}

    # ========================================
    # 3. Integrated: Key Points 생성 → Narrative 생성 (2회 LLM 호출)
    # ========================================
    try:
        # 3-1. Integrated Key Points 생성
        logger.info("[InsightNode] Integrated Key Points 생성 중 (1단계)...")
        integrated_key_points_data = await _generate_integrated_keypoints(
            llm_client,
            macro_key_points_data.get("key_points", []),
            crypto_key_points_data.get("key_points", []),
            all_keywords,
            economic_events,
        )
        logger.info(
            f"[InsightNode] Integrated Key Points {len(integrated_key_points_data['key_points'])}개 생성 완료"
        )

        # 3-2. Integrated Narrative 생성 (Key Points 기반)
        logger.info("[InsightNode] Integrated Narrative 생성 중 (2단계, Key Points 기반)...")
        integrated_paragraphs = await _generate_narrative_from_keypoints(
            llm_client,
            "integrated",
            integrated_key_points_data["key_points"],
            all_keywords,
            source_highlights,
            economic_events,
            num_paragraphs=integrated_paragraphs,
            macro_narrative=narratives.get("macro", {}).get("paragraphs", []),
            crypto_narrative=narratives.get("crypto", {}).get("paragraphs", []),
        )
        logger.info(
            f"[InsightNode] Integrated Narrative {len(integrated_paragraphs)}개 문단 생성 완료"
        )

        narratives["integrated"] = {
            "key_points": integrated_key_points_data["key_points"],
            "paragraphs": integrated_paragraphs,
            "source_mapping": integrated_key_points_data.get("source_mapping", {}),
        }

    except Exception as exc:
        error_msg = f"Integrated 2단계 생성 실패: {exc}"
        logger.error(f"[InsightNode] {error_msg}", exc_info=True)
        errors.append(error_msg)

        # Fallback: 기존 방식으로 시도
        logger.warning("[InsightNode] Integrated fallback: 기존 1단계 방식으로 재시도...")
        try:
            integrated_prompt = build_integrated_narrative_prompt(
                narratives.get("macro", {}).get("paragraphs", []),
                narratives.get("crypto", {}).get("paragraphs", []),
                all_keywords,
                num_paragraphs=integrated_paragraphs,
                economic_events=economic_events,
            )
            integrated_response = await llm_client.generate_content_async(
                prompt=integrated_prompt, response_format="json"
            )
            integrated_paragraphs = parse_narrative_response(
                integrated_response, "Integrated"
            )
            narratives["integrated"] = {
                "key_points": [],
                "paragraphs": integrated_paragraphs,
                "source_mapping": {},
            }
            logger.info("[InsightNode] Integrated fallback 성공")
        except Exception as fallback_exc:
            logger.error(f"[InsightNode] Integrated fallback 실패: {fallback_exc}")
            narratives["integrated"] = {"key_points": [], "paragraphs": [], "source_mapping": {}}

    # ========================================
    # 4. 거래 인사이트 생성 (기존 방식)
    # ========================================
    try:
        logger.info("[InsightNode] 거래 인사이트 생성 중...")
        insight_prompt = build_insight_prompt(
            all_keywords,
            raw_records,
            summary_paragraphs=0,  # 내러티브는 이미 생성했으므로 0
            max_sources=settings.highlight_limit,
            include_excerpts=settings.include_excerpts,
            prepared_inputs=prepared_inputs,
            id_mapping=id_mapping,
        )
        insight_response = await llm_client.generate_content_async(
            prompt=insight_prompt, response_format="json"
        )
        insights_data = parse_insight_response(insight_response)

        trading_insights = insights_data.get("trading_insights", {})
        key_sources = insights_data.get("key_sources", [])

        logger.info(
            "[InsightNode] 거래 인사이트 생성 완료: 기회=%d, 위험=%d",
            len(trading_insights.get("opportunities", [])),
            len(trading_insights.get("risks", [])),
        )

    except Exception as exc:
        error_msg = f"거래 인사이트 생성 실패: {exc}"
        logger.error(f"[InsightNode] {error_msg}", exc_info=True)
        errors.append(error_msg)
        trading_insights = {"opportunities": [], "risks": []}
        key_sources = []

    # LLM 호출 횟수 로깅
    logger.info(
        "[InsightNode] 2단계 LLM 호출 완료: "
        f"Macro (Key Points: {len(narratives.get('macro', {}).get('key_points', []))}개, "
        f"Paragraphs: {len(narratives.get('macro', {}).get('paragraphs', []))}개), "
        f"Crypto (Key Points: {len(narratives.get('crypto', {}).get('key_points', []))}개, "
        f"Paragraphs: {len(narratives.get('crypto', {}).get('paragraphs', []))}개), "
        f"Integrated (Key Points: {len(narratives.get('integrated', {}).get('key_points', []))}개, "
        f"Paragraphs: {len(narratives.get('integrated', {}).get('paragraphs', []))}개)"
    )

    return {
        "narratives": narratives,
        "trading_insights": trading_insights,
        "key_sources": key_sources,
    }

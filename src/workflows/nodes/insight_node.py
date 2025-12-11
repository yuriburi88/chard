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

    세분화 모드 활성화 시:
        1. Macro/Crypto Native/Crypto-Macro 카테고리별 내러티브 생성 (3회 LLM 호출)
        2. 통합 내러티브 생성 (1회 LLM 호출)
        3. 거래 인사이트 생성 (기존 방식)

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
    config_mapping: Mapping[str, object] = config_obj if isinstance(config_obj, Mapping) else {}

    # 내러티브 세분화 설정 확인
    narrative_config = config_mapping.get("narrative", {})
    if not isinstance(narrative_config, Mapping):
        narrative_config = {}

    enable_segmentation = narrative_config.get("enable_segmentation", True)

    logger.info("[InsightNode] 내러티브 세분화 모드: %s", "활성화" if enable_segmentation else "비활성화")

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

    # 세분화 모드 분기 처리
    if enable_segmentation:
        categorized_keywords = state.get("categorized_keywords", {})

        if not categorized_keywords:
            logger.warning("[InsightNode] categorized_keywords가 비어있어 세분화를 건너뜁니다.")
            enable_segmentation = False
        else:
            try:
                insights = await _generate_segmented_narratives(
                    state=state,
                    settings=settings,
                    narrative_config=narrative_config,
                    categorized_keywords=categorized_keywords,
                    raw_records=raw_records,
                    errors=errors
                )

                logger.info("[InsightNode] 세분화된 내러티브 생성 완료")

                # Phase 3: 품질 평가 수행
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
                            with open(cache_path, "r", encoding="utf-8") as f:
                                dynamic_cache = json.load(f)
                    except Exception:
                        dynamic_cache = {}

                    # 내러티브 텍스트 추출 (리스트를 문자열로 변환)
                    narratives_data = insights.get("narratives", {})
                    narratives = {
                        "macro": "\n\n".join(narratives_data.get("macro", [])),
                        "crypto_native": "\n\n".join(narratives_data.get("crypto_native", [])),
                        "crypto_macro": "\n\n".join(narratives_data.get("crypto_macro", [])),
                        "integrated": "\n\n".join(narratives_data.get("integrated", []))
                    }

                    # 품질 평가 실행
                    quality_metrics = evaluator.evaluate(
                        categorized_keywords=categorized_keywords,
                        narratives=narratives,
                        dynamic_keywords_cache=dynamic_cache
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
                with open(cache_path, "r", encoding="utf-8") as f:
                    dynamic_cache = json.load(f)
        except Exception:
            dynamic_cache = {}

        # 내러티브 텍스트 추출 (비세분화 모드)
        narratives = {
            "macro": "",
            "crypto_native": "",
            "crypto_macro": "",
            "integrated": "\n\n".join(insights.get("narrative_summary", []))
        }

        # 품질 평가 실행
        quality_metrics = evaluator.evaluate(
            categorized_keywords=categorized_keywords,
            narratives=narratives,
            dynamic_keywords_cache=dynamic_cache
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


async def _generate_segmented_narratives(
    state: AnalysisState,
    settings: _InsightSettings,
    narrative_config: Mapping[str, object],
    categorized_keywords: Mapping[str, Sequence],
    raw_records: List,
    errors: List[str]
) -> dict:
    """
    세분화된 내러티브를 생성합니다 (Macro/Crypto Native/Crypto-Macro/Integrated).

    Args:
        state: LangGraph 상태
        settings: InsightNode 설정
        narrative_config: 내러티브 설정
        categorized_keywords: 카테고리별 키워드
        raw_records: 원본 레코드
        errors: 에러 리스트 (참조로 전달)

    Returns:
        세분화된 인사이트 딕셔너리
    """
    from src.workflows.prompts import (
        build_macro_narrative_prompt,
        build_crypto_native_narrative_prompt,
        build_crypto_macro_narrative_prompt,
        build_integrated_narrative_prompt,
        build_insight_prompt,
        parse_narrative_response,
        parse_insight_response,
        prepare_insight_prompt_inputs,
    )

    macro_paragraphs = int(narrative_config.get("macro_paragraphs", 2))
    crypto_native_paragraphs = int(narrative_config.get("crypto_native_paragraphs", 2))
    crypto_macro_paragraphs = int(narrative_config.get("crypto_macro_paragraphs", 2))
    integrated_paragraphs = int(narrative_config.get("integrated_paragraphs", 3))

    id_mapping = state.get("id_mapping")

    # 카테고리별 키워드 추출
    macro_keywords = list(categorized_keywords.get("macro", []))
    crypto_native_keywords = list(categorized_keywords.get("crypto_native", []))
    crypto_macro_keywords = list(categorized_keywords.get("crypto_macro", []))
    all_keywords = list(state.get("aggregated_keywords", []))

    logger.info(
        "[InsightNode] 카테고리별 키워드 수: Macro=%d, Crypto Native=%d, Crypto-Macro=%d",
        len(macro_keywords),
        len(crypto_native_keywords),
        len(crypto_macro_keywords)
    )

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

    narratives = {}

    # 1. Macro 내러티브 생성
    if macro_keywords:
        try:
            logger.info("[InsightNode] Macro 내러티브 생성 중...")
            macro_prompt = build_macro_narrative_prompt(
                macro_keywords,
                source_highlights,
                num_paragraphs=macro_paragraphs
            )
            macro_response = await llm_client.generate_content_async(
                prompt=macro_prompt,
                response_format="json"
            )
            narratives["macro"] = parse_narrative_response(macro_response, "Macro")
            logger.info(f"[InsightNode] Macro 내러티브 {len(narratives['macro'])}개 문단 생성 완료")
        except Exception as exc:
            error_msg = f"Macro 내러티브 생성 실패: {exc}"
            logger.error(f"[InsightNode] {error_msg}", exc_info=True)
            errors.append(error_msg)
            narratives["macro"] = []
    else:
        logger.warning("[InsightNode] Macro 키워드가 없어 내러티브를 건너뜁니다.")
        narratives["macro"] = []

    # 2. Crypto Native 내러티브 생성
    if crypto_native_keywords:
        try:
            logger.info("[InsightNode] Crypto Native 내러티브 생성 중...")
            crypto_native_prompt = build_crypto_native_narrative_prompt(
                crypto_native_keywords,
                source_highlights,
                num_paragraphs=crypto_native_paragraphs
            )
            crypto_native_response = await llm_client.generate_content_async(
                prompt=crypto_native_prompt,
                response_format="json"
            )
            narratives["crypto_native"] = parse_narrative_response(crypto_native_response, "Crypto Native")
            logger.info(f"[InsightNode] Crypto Native 내러티브 {len(narratives['crypto_native'])}개 문단 생성 완료")
        except Exception as exc:
            error_msg = f"Crypto Native 내러티브 생성 실패: {exc}"
            logger.error(f"[InsightNode] {error_msg}", exc_info=True)
            errors.append(error_msg)
            narratives["crypto_native"] = []
    else:
        logger.warning("[InsightNode] Crypto Native 키워드가 없어 내러티브를 건너뜁니다.")
        narratives["crypto_native"] = []

    # 3. Crypto-Macro 내러티브 생성
    if crypto_macro_keywords:
        try:
            logger.info("[InsightNode] Crypto-Macro 내러티브 생성 중...")
            crypto_macro_prompt = build_crypto_macro_narrative_prompt(
                crypto_macro_keywords,
                source_highlights,
                num_paragraphs=crypto_macro_paragraphs
            )
            crypto_macro_response = await llm_client.generate_content_async(
                prompt=crypto_macro_prompt,
                response_format="json"
            )
            narratives["crypto_macro"] = parse_narrative_response(crypto_macro_response, "Crypto-Macro")
            logger.info(f"[InsightNode] Crypto-Macro 내러티브 {len(narratives['crypto_macro'])}개 문단 생성 완료")
        except Exception as exc:
            error_msg = f"Crypto-Macro 내러티브 생성 실패: {exc}"
            logger.error(f"[InsightNode] {error_msg}", exc_info=True)
            errors.append(error_msg)
            narratives["crypto_macro"] = []
    else:
        logger.warning("[InsightNode] Crypto-Macro 키워드가 없어 내러티브를 건너뜁니다.")
        narratives["crypto_macro"] = []

    # 4. 통합 내러티브 생성
    try:
        logger.info("[InsightNode] 통합 내러티브 생성 중...")
        integrated_prompt = build_integrated_narrative_prompt(
            narratives.get("macro", []),
            narratives.get("crypto_native", []),
            narratives.get("crypto_macro", []),
            all_keywords,
            num_paragraphs=integrated_paragraphs
        )
        integrated_response = await llm_client.generate_content_async(
            prompt=integrated_prompt,
            response_format="json"
        )
        narratives["integrated"] = parse_narrative_response(integrated_response, "Integrated")
        logger.info(f"[InsightNode] 통합 내러티브 {len(narratives['integrated'])}개 문단 생성 완료")
    except Exception as exc:
        error_msg = f"통합 내러티브 생성 실패: {exc}"
        logger.error(f"[InsightNode] {error_msg}", exc_info=True)
        errors.append(error_msg)
        narratives["integrated"] = []

    # 5. 거래 인사이트 생성 (기존 방식)
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
            prompt=insight_prompt,
            response_format="json"
        )
        insights_data = parse_insight_response(insight_response)

        trading_insights = insights_data.get("trading_insights", {})
        key_sources = insights_data.get("key_sources", [])

        logger.info(
            "[InsightNode] 거래 인사이트 생성 완료: 기회=%d, 위험=%d",
            len(trading_insights.get("opportunities", [])),
            len(trading_insights.get("risks", []))
        )

    except Exception as exc:
        error_msg = f"거래 인사이트 생성 실패: {exc}"
        logger.error(f"[InsightNode] {error_msg}", exc_info=True)
        errors.append(error_msg)
        trading_insights = {"opportunities": [], "risks": []}
        key_sources = []

    return {
        "narratives": narratives,
        "trading_insights": trading_insights,
        "key_sources": key_sources,
    }


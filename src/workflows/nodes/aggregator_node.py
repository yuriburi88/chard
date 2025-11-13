"""
AggregatorNode 구현

LLM 파이프라인 문서의 섹션 3.3을 참조하여 구현되었습니다.
임베딩 기반 클러스터링 결과를 이용해 키워드 스코어를 통합하고,
후속 LLM 검증 단계를 위해 상위 후보 키워드를 선정합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, MutableMapping, Sequence, Tuple

from src.workflows.state import AnalysisState
from src.workflows.normalization import (
    aggregate_clustered_keywords,
    cluster_keywords_by_embedding,
)
from src.workflows.normalization.embedding_cluster import (
    DEFAULT_GEMINI_EMBEDDING_MODEL,
    DEFAULT_GEMINI_TASK_TYPE,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
)
from src.workflows.llm_client import GeminiClient
from src.workflows.prompts import build_synonym_verification_prompt, parse_json_from_llm_response
from src.workflows.normalization.llm_verifier import merge_llm_groups_with_keywords

logger = logging.getLogger(__name__)


async def aggregator_node(state: AnalysisState) -> AnalysisState:
    """
    추출된 키워드를 임베딩 기반으로 통합하고 스코어를 재계산합니다.

    처리 단계:
        1. 입력 키워드 검증 및 설정 로드
        2. 임베딩을 활용한 DBSCAN 클러스터링 수행
        3. 클러스터별 메타데이터 통합 및 스코어 재계산
        4. 상위 후보 키워드 및 최종 상위 N개 키워드 선정
        5. 상태 업데이트 (clustered_keywords, scored_keywords, candidate_keywords, aggregated_keywords)

    Args:
        state: LangGraph 상태 (추출된 키워드 및 설정 포함)

    Returns:
        AggregatorNode 수행 결과가 반영된 LangGraph 상태
    """
    logger.info("[AggregatorNode] 스코어 통합 단계 시작")

    extracted_keywords = state.get("extracted_keywords", [])
    if not extracted_keywords:
        warning_msg = "AggregatorNode: 입력 키워드가 비어 있어 스코어 통합을 수행할 수 없습니다."

        logger.warning("[AggregatorNode] %s", warning_msg)

        return {
            **state,
            "clustered_keywords": [],
            "scored_keywords": [],
            "candidate_keywords": [],
            "aggregated_keywords": [],
            "errors": state.get("errors", []) + [warning_msg],
        }

    logger.info(
        "[AggregatorNode] 입력 키워드 수: %d",
        len(extracted_keywords),
    )

    config = state.get("config", {})
    normalization_config = config.get("normalization", {})
    output_config = config.get("output", {})

    errors: List[str] = list(state.get("errors", []))

    settings = _build_normalization_settings(normalization_config, output_config)

    logger.debug(
        "[AggregatorNode] 사용 설정: %s",
        json.dumps(settings.__dict__, ensure_ascii=False),
    )

    extracted_keyword_copies: List[MutableMapping[str, Any]] = [
        dict(keyword) for keyword in extracted_keywords
    ]

    try:
        clustered_keywords = await cluster_keywords_by_embedding(
            extracted_keyword_copies,
            similarity_threshold=settings.similarity_threshold,
            min_cluster_size=settings.min_cluster_size,
            provider=settings.provider,
            api_key=settings.api_key,
            model=settings.embedding_model,
            task_type=settings.embedding_task_type,
            concurrency_limit=settings.embedding_concurrency,
            normalize_embeddings=settings.normalize_embeddings,
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = f"AggregatorNode: 임베딩 클러스터링 실패 - {exc}"

        logger.error("[AggregatorNode] %s", error_msg, exc_info=True)

        return {
            **state,
            "clustered_keywords": [],
            "scored_keywords": [],
            "candidate_keywords": [],
            "aggregated_keywords": [],
            "errors": state.get("errors", []) + [error_msg],
        }

    logger.info(
        "[AggregatorNode] 클러스터링 완료: 총 클러스터 수=%d",
        len({kw["cluster_id"] for kw in clustered_keywords}),
    )

    try:
        scored_keywords = aggregate_clustered_keywords(
            clustered_keywords,
            evidence_limit=settings.evidence_limit,
            source_weight=settings.source_weight,
            occurrence_weight=settings.occurrence_weight,
            evidence_weight=settings.evidence_weight,
        )
    except Exception as exc:  # noqa: BLE001
        error_msg = f"AggregatorNode: 스코어 재계산 실패 - {exc}"

        logger.error("[AggregatorNode] %s", error_msg, exc_info=True)

        return {
            **state,
            "clustered_keywords": clustered_keywords,
            "scored_keywords": [],
            "candidate_keywords": [],
            "aggregated_keywords": [],
            "errors": state.get("errors", []) + [error_msg],
        }

    logger.info(
        "[AggregatorNode] 스코어 재계산 완료: 총 키워드 수=%d",
        len(scored_keywords),
    )

    candidate_limit = max(settings.candidate_limit, settings.top_keywords_count)

    candidate_keywords = _select_top_keywords(
        scored_keywords,
        limit=candidate_limit,
        include_ties=True,
    )
    preliminary_top_keywords = _select_top_keywords(
        scored_keywords,
        limit=settings.top_keywords_count,
        include_ties=False,
    )

    logger.info(
        "[AggregatorNode] 후보 키워드 선정 완료: limit=%d, include_ties=%s, 반환=%d",
        candidate_limit,
        True,
        len(candidate_keywords),
    )

    logger.info(
        "[AggregatorNode] 1차 최상위 키워드 선정 완료: limit=%d, include_ties=%s, 반환=%d",
        settings.top_keywords_count,
        False,
        len(preliminary_top_keywords),
    )

    logger.info(
        "[AggregatorNode] 상위 후보 %d개, 1차 상위 %d개 선정",
        len(candidate_keywords),
        len(preliminary_top_keywords),
    )

    _log_keyword_list(
        label="[AggregatorNode] 상위 후보 키워드 목록",
        keywords=candidate_keywords,
    )

    _log_keyword_list(
        label="[AggregatorNode] 1차 상위 키워드 목록",
        keywords=preliminary_top_keywords,
    )

    final_keywords = preliminary_top_keywords
    llm_verification_result: Dict[str, Any] | None = None
    llm_used = False

    if settings.llm_verification_enabled and candidate_keywords:
        llm_config = config.get("llm", {})

        try:
            final_keywords, llm_verification_result = await _apply_llm_verification(
                candidate_keywords=candidate_keywords,
                settings=settings,
                llm_config=llm_config,
            )

            if final_keywords:
                llm_used = True

                _log_keyword_list(
                    label="[AggregatorNode] LLM 검증 이후 최종 키워드 목록",
                    keywords=final_keywords,
                )
            else:
                logger.warning(
                    "[AggregatorNode] LLM 검증 결과가 비어 있어 1차 결과를 유지합니다.",
                )
                final_keywords = preliminary_top_keywords
        except Exception as exc:  # noqa: BLE001
            error_msg = f"AggregatorNode: LLM 동의어 검증 실패 - {exc}"

            logger.error("[AggregatorNode] %s", error_msg, exc_info=True)

            errors.append(error_msg)
            final_keywords = preliminary_top_keywords
    else:
        logger.info(
            "[AggregatorNode] LLM 검증 단계를 건너뜁니다. enabled=%s, 후보 수=%d",
            settings.llm_verification_enabled,
            len(candidate_keywords),
        )

    scoring_summary = {
        "extracted_count": len(extracted_keywords),
        "cluster_count": len({kw["cluster_id"] for kw in clustered_keywords}),
        "scored_count": len(scored_keywords),
        "candidate_count": len(candidate_keywords),
        "top_keywords_count": len(final_keywords),
        "llm_verification_enabled": settings.llm_verification_enabled,
        "llm_verification_used": llm_used,
    }

    return {
        **state,
        "clustered_keywords": clustered_keywords,
        "scored_keywords": scored_keywords,
        "candidate_keywords": candidate_keywords,
        "aggregated_keywords": final_keywords,
        "llm_verification_result": llm_verification_result,
        "errors": errors,
        "scoring_summary": scoring_summary,
    }


class _NormalizationSettings:
    """
    AggregatorNode에서 사용하는 설정 값을 캡슐화한 자료형.
    """

    def __init__(
        self,
        *,
        similarity_threshold: float,
        min_cluster_size: int,
        provider: str,
        api_key: str | None,
        embedding_model: str,
        embedding_task_type: str,
        embedding_concurrency: int,
        normalize_embeddings: bool,
        evidence_limit: int,
        source_weight: float,
        occurrence_weight: float,
        evidence_weight: float,
        candidate_limit: int,
        top_keywords_count: int,
    llm_verification_enabled: bool,
    llm_max_variants: int,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.provider = provider
        self.api_key = api_key
        self.embedding_model = embedding_model
        self.embedding_task_type = embedding_task_type
        self.embedding_concurrency = embedding_concurrency
        self.normalize_embeddings = normalize_embeddings
        self.evidence_limit = evidence_limit
        self.source_weight = source_weight
        self.occurrence_weight = occurrence_weight
        self.evidence_weight = evidence_weight
        self.candidate_limit = candidate_limit
        self.top_keywords_count = top_keywords_count
        self.llm_verification_enabled = llm_verification_enabled
        self.llm_max_variants = llm_max_variants


def _build_normalization_settings(
    normalization_config: Dict[str, Any],
    output_config: Dict[str, Any],
) -> _NormalizationSettings:
    """
    설정 딕셔너리를 AggregatorNode에서 사용하기 쉬운 형태로 변환합니다.

    Args:
        normalization_config: config.yml의 normalization 섹션
        output_config: config.yml의 output 섹션

    Returns:
        AggregatorNode에서 사용하는 `_NormalizationSettings` 인스턴스
    """
    similarity_threshold = float(normalization_config.get("embedding_threshold", 0.85))
    min_cluster_size = int(normalization_config.get("dbscan_min_samples", 1))

    provider_value = normalization_config.get("embedding_provider", "google")
    provider, api_key = _resolve_embedding_provider(provider_value, normalization_config)

    if provider == "gemini":
        embedding_model = normalization_config.get("embedding_model", DEFAULT_GEMINI_EMBEDDING_MODEL)
        embedding_task_type = normalization_config.get("embedding_task_type", DEFAULT_GEMINI_TASK_TYPE)
    elif provider == "openai":
        embedding_model = normalization_config.get("embedding_model", DEFAULT_OPENAI_EMBEDDING_MODEL)
        embedding_task_type = normalization_config.get("embedding_task_type")
    else:
        embedding_model = normalization_config.get("embedding_model", "keybert")
        embedding_task_type = normalization_config.get("embedding_task_type")

    embedding_concurrency = int(normalization_config.get("embedding_concurrency", 4))
    normalize_embeddings = bool(normalization_config.get("normalize_embeddings", True))

    evidence_limit = int(normalization_config.get("evidence_limit", 3))

    score_weights = normalization_config.get("score_weights", {})
    source_weight = float(score_weights.get("source", 0.1))
    occurrence_weight = float(score_weights.get("occurrence", 0.05))
    evidence_weight = float(score_weights.get("evidence", 0.02))

    top_keywords_count = int(output_config.get("top_keywords_count", 10))

    llm_verification_top_n = normalization_config.get("llm_verification_top_n")
    candidate_multiplier = int(normalization_config.get("candidate_multiplier", 2))

    candidate_limit = (
        int(llm_verification_top_n)
        if llm_verification_top_n is not None
        else max(top_keywords_count * candidate_multiplier, top_keywords_count)
    )

    llm_verification_enabled = bool(normalization_config.get("llm_verification_enabled", True))
    llm_max_variants = int(normalization_config.get("llm_verification_max_variants", 8))

    return _NormalizationSettings(
        similarity_threshold=similarity_threshold,
        min_cluster_size=min_cluster_size,
        provider=provider,
        api_key=api_key,
        embedding_model=embedding_model,
        embedding_task_type=embedding_task_type,
        embedding_concurrency=embedding_concurrency,
        normalize_embeddings=normalize_embeddings,
        evidence_limit=evidence_limit,
        source_weight=source_weight,
        occurrence_weight=occurrence_weight,
        evidence_weight=evidence_weight,
        candidate_limit=candidate_limit,
        top_keywords_count=top_keywords_count,
        llm_verification_enabled=llm_verification_enabled,
        llm_max_variants=llm_max_variants,
    )


def _resolve_embedding_provider(
    provider_value: str,
    normalization_config: Dict[str, Any],
) -> Tuple[str, str | None]:
    """
    임베딩 공급자 값을 normalizer가 사용 가능한 값으로 변환합니다.

    Args:
        provider_value: 설정에 정의된 공급자 문자열
        normalization_config: normalization 설정 딕셔너리

    Returns:
        (provider, api_key) 튜플

    Raises:
        ValueError: 지원되지 않는 공급자가 지정된 경우
    """
    provider_lower = provider_value.lower()

    if provider_lower in {"google", "gemini", "google_genai"}:
        return "gemini", normalization_config.get("embedding_api_key")

    if provider_lower in {"openai"}:
        api_key = (
            normalization_config.get("openai_api_key")
            or normalization_config.get("embedding_api_key")
        )
        return "openai", api_key

    if provider_lower in {"keybert", "local"}:
        return "keybert", None

    raise ValueError(f"지원되지 않는 embedding_provider 값입니다: {provider_value}")


def _log_keyword_list(label: str, keywords: Sequence[MutableMapping[str, Any]]) -> None:
    """
    키워드 리스트를 읽기 쉬운 문자열 형태로 로깅합니다.

    Args:
        label: 로그 라벨
        keywords: 로깅할 키워드 리스트
    """
    if not keywords:
        logger.info("%s: 없음", label)
        return

    serialized = [
        {
            "term": keyword.get("term"),
            "score": keyword.get("score"),
            "sources": keyword.get("sources"),
            "occurrence_count": keyword.get("occurrence_count"),
        }
        for keyword in keywords
    ]

    logger.info(
        "%s: %s",
        label,
        json.dumps(serialized, ensure_ascii=False),
    )


async def _apply_llm_verification(
    *,
    candidate_keywords: Sequence[MutableMapping[str, Any]],
    settings: _NormalizationSettings,
    llm_config: MutableMapping[str, Any],
) -> Tuple[List[MutableMapping[str, Any]], Dict[str, Any]]:
    """
    Gemini를 호출해 동의어 검증을 수행하고 결과를 병합합니다.

    Args:
        candidate_keywords: LLM 검증 대상 후보 키워드 시퀀스.
        settings: AggregatorNode 정규화 설정.
        llm_config: config.yml의 llm 섹션.

    Returns:
        (병합된 키워드 리스트, LLM 응답 딕셔너리) 튜플.
    """
    logger.info(
        "[AggregatorNode] LLM 동의어 검증 시작: candidate_count=%d",
        len(candidate_keywords),
    )

    prompt = build_synonym_verification_prompt(
        candidate_keywords,
        top_n=settings.top_keywords_count,
        max_variants=settings.llm_max_variants,
    )

    logger.debug(
        "[AggregatorNode] 동의어 검증 프롬프트 생성 완료: 길이=%d, 내용=%s",
        len(prompt),
        prompt,
    )

    model = llm_config.get("model", "gemini-2.0-flash")
    temperature = float(llm_config.get("temperature", 0.1))
    max_tokens = int(llm_config.get("max_tokens", 4000))

    gemini_client = GeminiClient(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    response_text = await gemini_client.generate_content_async(
        prompt=prompt,
        response_format="json",
    )

    logger.debug(
        "[AggregatorNode] LLM 검증 응답 수신: 길이=%d, 내용=%s",
        len(response_text),
        response_text,
    )

    # 공통 JSON 파싱 함수 사용 (코드 블록 자동 처리)
    llm_result = parse_json_from_llm_response(
        response_text,
        context="AggregatorNode LLM 동의어 검증 응답"
    )

    merged_keywords = merge_llm_groups_with_keywords(
        candidate_keywords,
        llm_result,
        top_n=settings.top_keywords_count,
        evidence_limit=settings.evidence_limit,
    )

    logger.info(
        "[AggregatorNode] LLM 동의어 검증 완료: 반환 키워드 수=%d",
        len(merged_keywords),
    )

    return merged_keywords, llm_result


def _select_top_keywords(
    scored_keywords: Sequence[MutableMapping[str, Any]],
    *,
    limit: int,
    include_ties: bool,
) -> List[MutableMapping[str, Any]]:
    """
    점수 기반으로 상위 키워드를 선정하고 순위를 부여합니다.

    Args:
        scored_keywords: 점수와 메타데이터를 포함한 키워드 시퀀스.
        limit: 기본적으로 선택할 키워드 개수.
        include_ties: True일 경우 마지막 순위와 동점인 항목을 모두 포함합니다.

    Returns:
        순위(`rank`)가 포함된 키워드 사전 리스트.

    Raises:
        ValueError: limit가 1 미만일 때.
    """
    if limit < 1:
        raise ValueError("limit 값은 1 이상이어야 합니다.")

    if not scored_keywords:
        return []

    sorted_keywords = sorted(
        (dict(keyword) for keyword in scored_keywords),
        key=lambda item: float(item.get("score", 0.0) or 0.0),
        reverse=True,
    )

    ranked_keywords: List[MutableMapping[str, Any]] = []

    last_score: float | None = None
    last_rank = 0

    for index, keyword in enumerate(sorted_keywords):
        score = float(keyword.get("score", 0.0) or 0.0)

        if last_score is None or score < last_score:
            last_rank = index + 1
            last_score = score

        keyword["rank"] = last_rank

        ranked_keywords.append(keyword)

    base_selection = ranked_keywords[:limit]

    if not include_ties:
        return base_selection

    if len(base_selection) == len(ranked_keywords):
        return base_selection

    cutoff_rank = base_selection[-1]["rank"]

    tie_extension = [
        keyword
        for keyword in ranked_keywords[limit:]
        if keyword["rank"] == cutoff_rank
    ]

    return base_selection + tie_extension



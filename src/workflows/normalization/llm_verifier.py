"""
LLM 기반 동의어 검증 유틸리티.

LangGraph AggregatorNode의 2차 정제 단계에서 Gemini 응답을
기존 키워드 구조에 병합하고 정규화하는 기능을 제공합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence

logger = logging.getLogger(__name__)


def merge_llm_groups_with_keywords(
    candidate_keywords: Sequence[Mapping[str, object]],
    llm_result: Mapping[str, object] | None,
    *,
    top_n: int | None = None,
    evidence_limit: int = 3,
) -> List[Dict[str, object]]:
    """
    LLM 검증 결과를 기존 후보 키워드 구조에 병합합니다.

    Args:
        candidate_keywords: AggregatorNode에서 전달된 후보 키워드 시퀀스.
        llm_result: Gemini 응답(JSON)을 파싱한 결과. ``groups``와 ``standalone`` 필드를 기대합니다.
        top_n: 최종으로 유지할 키워드 개수 상한. ``None``이면 전체를 반환합니다.
        evidence_limit: 병합 후 유지할 증거 문장 최대 개수.

    Returns:
        LLM 검증 결과가 반영된 키워드 리스트. ``original_variants`` 필드가 보존·확장됩니다.

    Raises:
        ValueError: 입력 검증 실패 시.
    """
    if top_n is not None and top_n < 1:
        raise ValueError("top_n 값은 1 이상이거나 None 이어야 합니다.")

    if not candidate_keywords:
        return []

    normalized_candidates = _normalize_candidates(candidate_keywords)

    groups = _safe_get_groups(llm_result)
    standalone_terms = _safe_get_standalone(llm_result)

    logger.info(
        "[LLMVerifier] LLM 병합 시작: candidates=%d, groups=%d, standalone=%d",
        len(normalized_candidates),
        len(groups),
        len(standalone_terms),
    )

    merged_keywords: List[Dict[str, object]] = []
    processed_terms: set[str] = set()

    for group in groups:
        merged_entry = _merge_group(group, normalized_candidates.values(), evidence_limit)

        if not merged_entry:
            continue

        merged_keywords.append(merged_entry)
        processed_terms.update(merged_entry["llm_metadata"]["variants"])  # type: ignore[index]

    fallback_entries = _collect_unprocessed_candidates(
        normalized_candidates,
        processed_terms,
        standalone_terms,
        evidence_limit,
    )

    merged_keywords.extend(fallback_entries)

    ranked_keywords = _rank_and_trim(merged_keywords, top_n)

    logger.info(
        "[LLMVerifier] LLM 병합 완료: returned=%d, top_n=%s",
        len(ranked_keywords),
        top_n if top_n is not None else "(all)",
    )

    logger.debug(
        "[LLMVerifier] 병합 결과 샘플: %s",
        json.dumps(ranked_keywords[:3], ensure_ascii=False),
    )

    return ranked_keywords


def _normalize_candidates(
    candidates: Sequence[Mapping[str, object]],
) -> Dict[str, Dict[str, object]]:
    """
    후보 키워드를 용어 기준 딕셔너리로 정규화합니다.
    """
    normalized: Dict[str, Dict[str, object]] = {}

    for item in candidates:
        term = str(item.get("term", "")).strip()

        if not term:
            continue

        normalized[term] = dict(item)

    logger.debug(
        "[LLMVerifier] 후보 정규화 완료: normalized_terms=%s",
        list(normalized.keys()),
    )

    return normalized


def _safe_get_groups(llm_result: Mapping[str, object] | None) -> List[Mapping[str, object]]:
    """
    LLM 응답에서 그룹 정보를 안전하게 추출합니다.
    """
    if not llm_result:
        return []

    groups = llm_result.get("groups", [])

    if not isinstance(groups, Iterable):
        return []

    return [group for group in groups if isinstance(group, Mapping)]


def _safe_get_standalone(llm_result: Mapping[str, object] | None) -> List[str]:
    """
    LLM 응답에서 standalone 용어를 추출합니다.
    """
    if not llm_result:
        return []

    entries = llm_result.get("standalone", [])

    if not isinstance(entries, Iterable):
        return []

    normalized: List[str] = []

    for entry in entries:
        term = str(entry).strip()

        if term:
            normalized.append(term)

    return normalized


def _merge_group(
    group: Mapping[str, object],
    candidates: Iterable[Mapping[str, object]],
    evidence_limit: int,
) -> Dict[str, object] | None:
    """
    단일 그룹 정보를 바탕으로 키워드 메타데이터를 병합합니다.
    """
    canonical = str(group.get("canonical", "")).strip()
    variants = _normalize_variants(group.get("variants"))

    if not canonical:
        return None

    if not variants:
        variants = [canonical]

    candidate_map: Dict[str, MutableMapping[str, object]] = {
        str(candidate.get("term", "")).strip(): dict(candidate)
        for candidate in candidates
        if str(candidate.get("term", "")).strip()
    }

    matched_candidates = [candidate_map[variant] for variant in variants if variant in candidate_map]

    if not matched_candidates and canonical in candidate_map:
        matched_candidates = [candidate_map[canonical]]

    if not matched_candidates:
        logger.debug(
            "[LLMVerifier] 그룹에 매칭된 후보가 없습니다: canonical=%s, variants=%s",
            canonical,
            variants,
        )
        return None

    combined_terms = _collect_original_variants(matched_candidates, canonical, variants)

    combined_sources = _collect_sources(matched_candidates)

    combined_evidence = _collect_evidence(matched_candidates, evidence_limit)

    combined_scores = _collect_scores(matched_candidates)

    combined_occurrence = sum(int(item.get("occurrence_count", 1) or 1) for item in matched_candidates)

    representative_term = canonical if canonical in combined_terms else matched_candidates[0].get("term", canonical)

    final_score = max(combined_scores) if combined_scores else 0.0

    llm_confidence = float(group.get("confidence", 0.0) or 0.0)
    llm_rationale = str(group.get("rationale", "")).strip()

    merged_entry: Dict[str, object] = {
        "term": representative_term,
        "original_variants": combined_terms,
        "score": final_score,
        "evidence_ids": combined_evidence,  # evidence_ids 리스트
        "sources": combined_sources,
        "occurrence_count": combined_occurrence,
        "llm_metadata": {
            "canonical": canonical,
            "variants": variants,
            "confidence": llm_confidence,
            "rationale": llm_rationale,
        },
        "score_breakdown": {
            "raw_scores": combined_scores,
            "llm_confidence": llm_confidence,
        },
    }

    return merged_entry


def _collect_unprocessed_candidates(
    normalized_candidates: Mapping[str, Dict[str, object]],
    processed_terms: Iterable[str],
    standalone_terms: Iterable[str],
    evidence_limit: int,
) -> List[Dict[str, object]]:
    """
    LLM에서 다루지 않은 후보들을 그대로 유지합니다.
    """
    remaining_terms = {term for term in normalized_candidates.keys() if term not in processed_terms}
    standalone_set = {term for term in standalone_terms}

    preserved_terms = remaining_terms | standalone_set

    preserved_keywords: List[Dict[str, object]] = []

    for term in preserved_terms:
        candidate = normalized_candidates.get(term)

        if not candidate:
            continue

        preserved_entry = dict(candidate)

        preserved_entry["original_variants"] = _collect_original_variants([candidate], term, [])
        preserved_entry["evidence_ids"] = _collect_evidence([candidate], evidence_limit)
        preserved_entry["sources"] = _collect_sources([candidate])

        preserved_keywords.append(preserved_entry)

    return preserved_keywords


def _normalize_variants(raw_variants: object) -> List[str]:
    """
    변형 용어 목록을 중복 제거하며 정규화합니다.
    딕셔너리나 복잡한 객체는 제외합니다.
    """
    if not isinstance(raw_variants, Iterable):
        return []

    normalized: List[str] = []

    for variant in raw_variants:
        # 딕셔너리, 리스트, 튜플 등 복잡한 객체는 건너뛰기
        if isinstance(variant, (dict, list, tuple)):
            continue

        term = str(variant).strip()

        # str(dict) 형태로 변환된 것도 필터링 ('{' 또는 '[' 로 시작)
        if term and term not in normalized and not term.startswith(('{', '[')):
            normalized.append(term)

    return normalized


def _collect_original_variants(
    matched_candidates: Sequence[Mapping[str, object]],
    canonical: str,
    variants: Sequence[str],
) -> List[str]:
    """
    대표 용어와 변형 정보를 결합하여 original_variants를 구성합니다.

    문자열만 포함하도록 필터링하여 딕셔너리/복잡한 객체를 제외합니다.
    """
    ordered_terms: List[str] = []

    def _append_distinct(items: Iterable[str]) -> None:
        for item in items:
            value = item.strip()

            if value and value not in ordered_terms:
                ordered_terms.append(value)

    def _is_valid_string(value: object) -> bool:
        """
        유효한 문자열인지 확인합니다.
        딕셔너리, 리스트 등 복잡한 객체를 걸러냅니다.
        """
        if not isinstance(value, str):
            return False
        # str(dict)는 '{'로 시작하므로 이를 필터링
        if value.strip().startswith('{') or value.strip().startswith('['):
            return False
        return True

    _append_distinct([canonical])
    _append_distinct(variants)

    for candidate in matched_candidates:
        candidate_term = str(candidate.get("term", "")).strip()
        _append_distinct([candidate_term])

        original_variants = candidate.get("original_variants", [])
        if isinstance(original_variants, Iterable):
            # 문자열만 필터링하여 추가
            valid_variants = []
            for value in original_variants:
                # 딕셔너리나 복잡한 객체는 건너뛰기
                if isinstance(value, (dict, list, tuple)):
                    continue
                # 문자열만 추가
                if isinstance(value, str) and not value.strip().startswith(('{', '[')):
                    valid_variants.append(value)
            _append_distinct(valid_variants)

    return ordered_terms


def _collect_sources(
    matched_candidates: Sequence[Mapping[str, object]],
) -> List[str]:
    """
    후보 키워드들의 출처를 합집합으로 정규화합니다.
    """
    sources: List[str] = []

    for candidate in matched_candidates:
        candidate_sources = candidate.get("sources", [])

        if not isinstance(candidate_sources, Iterable):
            continue

        for source in candidate_sources:
            value = str(source).strip()

            if value and value not in sources:
                sources.append(value)

    return sources


def _collect_evidence(
    matched_candidates: Sequence[Mapping[str, object]],
    evidence_limit: int,
) -> List[int]:
    """
    evidence_ids를 순서를 유지하며 제한 개수만큼 모읍니다.
    
    Args:
        matched_candidates: 매칭된 후보 키워드 시퀀스
        evidence_limit: 수집할 evidence_ids 최대 개수
    
    Returns:
        evidence_ids 리스트 (정수 ID 리스트)
    """
    evidence_ids: List[int] = []

    for candidate in matched_candidates:
        # evidence_ids 필드 확인 (evidence 필드는 무시)
        candidate_evidence_ids = candidate.get("evidence_ids", [])
        
        # 하위 호환성: evidence 필드가 있으면 경고하고 무시
        if not candidate_evidence_ids and "evidence" in candidate:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"[_collect_evidence] 후보 키워드에 'evidence' 필드가 있지만 "
                f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
            )

        if not isinstance(candidate_evidence_ids, Iterable):
            continue

        for item in candidate_evidence_ids:
            # ID가 정수인지 확인
            if isinstance(item, int):
                evidence_id = item
            else:
                try:
                    evidence_id = int(item)
                except (ValueError, TypeError):
                    continue

            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)

            if len(evidence_ids) >= evidence_limit:
                return evidence_ids

    return evidence_ids


def _collect_scores(
    matched_candidates: Sequence[Mapping[str, object]],
) -> List[float]:
    """
    후보 점수 목록을 float로 변환하여 반환합니다.
    """
    scores: List[float] = []

    for candidate in matched_candidates:
        try:
            score = float(candidate.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue

        scores.append(score)

    return scores


def _rank_and_trim(
    keywords: Sequence[Mapping[str, object]],
    top_n: int | None,
) -> List[Dict[str, object]]:
    """
    점수 기준으로 정렬하고 필요한 경우 상위 N개만 반환합니다.
    """
    sorted_keywords = sorted(
        (dict(keyword) for keyword in keywords),
        key=lambda item: (
            float(item.get("score", 0.0) or 0.0),
            str(item.get("term", "")),
        ),
        reverse=True,
    )

    for index, keyword in enumerate(sorted_keywords, start=1):
        keyword["rank"] = index

    if top_n is not None:
        return sorted_keywords[:top_n]

    return sorted_keywords

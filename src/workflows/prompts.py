"""
프롬프트 템플릿 모듈

LLM 파이프라인에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

from __future__ import annotations

import json
import re
import logging
from typing import Dict, List, Mapping, Sequence, Tuple, Optional, Any

logger = logging.getLogger(__name__)


def parse_json_from_llm_response(response_text: str, context: str = "LLM 응답") -> Dict[str, object]:
    """
    LLM 응답에서 JSON을 추출하고 파싱합니다.
    
    마크다운 코드 블록(```json ... ```) 형식의 응답도 처리합니다.
    불완전한 JSON(응답이 잘린 경우)도 감지합니다.
    
    Args:
        response_text: LLM 응답 텍스트
        context: 에러 메시지에 사용할 컨텍스트 (기본값: "LLM 응답")
    
    Returns:
        파싱된 JSON 딕셔너리
    
    Raises:
        ValueError: JSON 파싱 실패 시 (불완전한 JSON 포함)
    """
    sanitized_text = response_text.strip()
    
    # 마크다운 코드 블록 제거
    if sanitized_text.startswith("```"):
        start_idx = sanitized_text.find("```")
        end_idx = sanitized_text.find("```", start_idx + 3)
        
        if end_idx != -1:
            sanitized_text = sanitized_text[start_idx + 3 : end_idx].strip()
            
            # "json" 접두사 제거
            if sanitized_text.startswith("json"):
                sanitized_text = sanitized_text[4:].strip()
        else:
            # 코드 블록이 닫히지 않음 (응답이 잘렸을 가능성)
            sanitized_text = sanitized_text[start_idx + 3 :].strip()
            if sanitized_text.startswith("json"):
                sanitized_text = sanitized_text[4:].strip()
    
    # 불완전한 JSON 감지: 닫는 중괄호가 없거나 불균형
    open_braces = sanitized_text.count("{")
    close_braces = sanitized_text.count("}")
    open_brackets = sanitized_text.count("[")
    close_brackets = sanitized_text.count("]")
    
    is_truncated = (
        open_braces > close_braces or
        open_brackets > close_brackets or
        (sanitized_text.rstrip().endswith(",") and not sanitized_text.rstrip().endswith("}"))
    )
    
    # JSON 파싱 시도
    result = None
    try:
        result = json.loads(sanitized_text)
    except json.JSONDecodeError as error:
        # 불완전한 JSON인 경우 명확한 에러 메시지 제공
        if is_truncated:
            raise ValueError(
                f"{context} 파싱 실패: 응답이 잘렸습니다 (불완전한 JSON). "
                f"max_tokens 제한으로 인해 응답이 중간에 잘렸을 가능성이 있습니다.\n"
                f"에러: {error}\n"
                f"응답 길이: {len(sanitized_text)}자\n"
                f"응답 끝부분 (마지막 200자): {sanitized_text[-200:]}"
            ) from error
        
        # JSON 객체를 정규식으로 찾아서 파싱 시도
        json_match = re.search(r"\{.*\}", sanitized_text, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError as nested_error:
                raise ValueError(
                    f"{context} 파싱 실패: {nested_error}\n"
                    f"응답 텍스트 (처음 500자): {sanitized_text[:500]}\n"
                    f"응답 텍스트 (마지막 200자): {sanitized_text[-200:]}"
                ) from nested_error
        else:
            raise ValueError(
                f"{context}에서 JSON을 찾을 수 없습니다: {error}\n"
                f"응답 텍스트 (처음 500자): {sanitized_text[:500]}\n"
                f"응답 텍스트 (마지막 200자): {sanitized_text[-200:]}"
            ) from error
    
    if not isinstance(result, dict):
        raise ValueError(f"{context}가 딕셔너리가 아닙니다: {type(result)}")
    
    return result


def build_keyword_extraction_prompt(chunk: List[Dict[str, object]]) -> str:
    """
    키워드 추출을 위한 프롬프트를 구성합니다.

    LLM 파이프라인 문서의 섹션 3.2를 참조하여 구현되었습니다.
    각 레코드에는 "id" 필드가 포함되어 있으며, evidence는 ID 리스트로 반환됩니다.

    Args:
        chunk: ID가 부여된 정규화된 데이터 레코드 리스트 (Dict 형식).
            각 레코드는 다음 형식을 가져야 합니다:
            {
                "id": 123,  # 고유 ID (정수)
                "source": "rss" | "telegram",
                "timestamp": "ISO 8601 형식 문자열",
                "text": "원본 텍스트",
                "meta": {
                    "title": "기사 제목 또는 메시지 요약",
                    "url": "기사 링크 (RSS만)",
                    "channel": "텔레그램 채널명 (Telegram만)"
                }
            }

    Returns:
        구성된 프롬프트 문자열.
    """
    chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 디지털 자산 시장의 내러티브 분석 전문가입니다.\n"
        "주어진 텍스트에서 시장에 영향을 미칠 수 있는 핵심 키워드를 추출하세요."
    )

    user_prompt = (
        "다음은 RSS 기사와 텔레그램 메시지에서 수집한 텍스트입니다.\n"
        "각 레코드는 고유한 \"id\" 필드를 가지고 있습니다:\n\n"
        f"{chunk_json}\n\n"
        "요구사항:\n"
        "1. 상위 10개의 중요한 키워드를 추출하세요\n"
        "2. 각 키워드에 대해 다음 정보를 제공하세요:\n"
        "   - 키워드: (용어)\n"
        "   - 중요도 점수: (0-100)\n"
        "   - 증거 ID: (해당 키워드를 지지하는 레코드의 id 값 리스트, 2-3개)\n"
        "   - 출처: (RSS 기사 제목 또는 텔레그램 채널명)\n\n"
        "중요: evidence 필드에는 원문 문장이 아닌 레코드의 id 값만 포함하세요.\n"
        "예를 들어, id가 123, 456, 789인 레코드가 키워드를 지지한다면, evidence_ids는 [123, 456, 789]입니다.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        '  "keywords": [\n'
        "    {\n"
        '      "term": "키워드",\n'
        '      "score": 85,\n'
        '      "evidence_ids": [123, 456, 789],\n'
        '      "sources": ["출처1", "출처2"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    return full_prompt


def parse_keyword_extraction_response(
    response_text: str,
    id_mapping: Optional[Dict[int, Dict[str, Any]]] = None
) -> Dict[str, object]:
    """
    키워드 추출 응답을 파싱하고 검증합니다.
    
    evidence_ids를 검증하고, 유효하지 않은 ID는 제거하며 로그에 기록합니다.

    Args:
        response_text: Gemini API 응답 텍스트.
        id_mapping: ID 매핑 딕셔너리 (디버깅 및 검증용, 선택적).

    Returns:
        파싱된 키워드 딕셔너리.
        {
            "keywords": [
                {
                    "term": "키워드",
                    "score": 85,
                    "evidence_ids": [123, 456, 789],  # ID 리스트
                    "sources": ["출처1", "출처2"]
                }
            ]
        }

    Raises:
        ValueError: 응답 구조가 예상과 다를 때.
    """
    logger = logging.getLogger(__name__)
    
    result = parse_json_from_llm_response(response_text, context="키워드 추출 응답")

    if "keywords" not in result:
        raise ValueError("키워드 추출 응답에 'keywords' 필드가 없습니다.")

    if not isinstance(result["keywords"], list):
        raise ValueError("키워드 추출 응답의 'keywords' 필드가 리스트가 아닙니다.")

    # evidence_ids 검증 및 정리
    for index, keyword in enumerate(result["keywords"], start=1):
        if not isinstance(keyword, dict):
            raise ValueError(f"키워드 {index}이 딕셔너리가 아닙니다: {type(keyword)}")

        required_fields = ("term", "score")

        for field in required_fields:
            if field not in keyword:
                raise ValueError(f"키워드 {index}에 필수 필드 '{field}'가 없습니다.")

        # evidence_ids 필드 확인 (하위 호환성을 위해 evidence도 확인)
        evidence_ids = keyword.get("evidence_ids", [])
        
        # 하위 호환성: evidence 필드가 있으면 무시하고 경고
        if "evidence" in keyword and not evidence_ids:
            logger.warning(
                f"[parse_keyword_extraction_response] 키워드 {index}에 'evidence' 필드가 있지만 "
                f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
            )
        
        # evidence_ids가 없으면 빈 리스트로 설정
        if not evidence_ids:
            keyword["evidence_ids"] = []
        elif not isinstance(evidence_ids, list):
            logger.warning(
                f"[parse_keyword_extraction_response] 키워드 {index}의 'evidence_ids'가 리스트가 아닙니다: "
                f"{type(evidence_ids)}. 빈 리스트로 설정합니다."
            )
            keyword["evidence_ids"] = []
        else:
            # 유효한 ID만 필터링
            valid_ids = []
            invalid_ids = []
            
            for evidence_id in evidence_ids:
                # ID가 정수인지 확인
                if not isinstance(evidence_id, int):
                    try:
                        evidence_id = int(evidence_id)
                    except (ValueError, TypeError):
                        invalid_ids.append(evidence_id)
                        continue
                
                # ID 매핑이 제공된 경우, 유효성 검증
                if id_mapping is not None:
                    if evidence_id not in id_mapping:
                        invalid_ids.append(evidence_id)
                        continue
                
                valid_ids.append(evidence_id)
            
            # 유효하지 않은 ID가 있으면 로그에 기록
            if invalid_ids:
                logger.warning(
                    f"[parse_keyword_extraction_response] 키워드 {index} ('{keyword.get('term', 'unknown')}')에 "
                    f"유효하지 않은 evidence_ids가 있습니다: {invalid_ids}\n"
                    f"키워드 정보: term={keyword.get('term')}, score={keyword.get('score')}, "
                    f"전체 evidence_ids={evidence_ids}\n"
                    f"ID 매핑 통계: 총 레코드 수={len(id_mapping) if id_mapping else 'N/A'}, "
                    f"유효한 ID 범위={f'{min(id_mapping.keys())}-{max(id_mapping.keys())}' if id_mapping and id_mapping.keys() else 'N/A'}"
                )
            
            keyword["evidence_ids"] = valid_ids
        
        keyword.setdefault("sources", [])

    return result


def build_synonym_verification_prompt(
    candidate_keywords: Sequence[Mapping[str, object]],
    *,
    top_n: int,
    max_variants: int = 8,
) -> str:
    """
    상위 후보 키워드를 기반으로 LLM 동의어 검증 프롬프트를 구성합니다.

    Args:
        candidate_keywords: AggregatorNode에서 전달된 후보 키워드 시퀀스.
        top_n: 최종 노출 목표 키워드 개수 (N). 프롬프트에서 2N 후보를 검증합니다.
        max_variants: 프롬프트에 포함할 대표 변형(term) 최대 개수.

    Returns:
        동의어 검증에 사용할 프롬프트 문자열.

    Raises:
        ValueError: 입력 검증 실패 시.
    """
    if top_n < 1:
        raise ValueError("top_n 값은 1 이상이어야 합니다.")

    if not candidate_keywords:
        raise ValueError("동의어 검증 후보 키워드가 비어 있습니다.")

    payload = _build_candidate_payload(
        candidate_keywords=candidate_keywords,
        max_variants=max_variants,
    )

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 디지털 자산 시장의 용어 정규화 전문가입니다.\n"
        "주어진 후보 키워드들의 의미적 동등성을 검증하고, 신뢰도와 근거를 명확히 제시하세요."
    )

    user_prompt = (
        f"다음은 임베딩 및 스코어 재계산 단계를 거친 상위 후보 키워드입니다 "
        f"(최종 상위 {top_n}개 선정을 위한 2N 후보 풀):\n\n{payload_json}\n\n"
        "요구사항:\n"
        "1. 의미적으로 동일하거나 동일 자산을 지칭하는 용어를 그룹으로 묶으세요.\n"
        "2. 각 그룹은 대표 용어(canonical) 1개와 변형 목록(variants)을 포함해야 합니다.\n"
        "3. 판단 근거와 확신도(confidence: 0.0~1.0)를 필수로 제시하세요.\n"
        "4. 불확실한 경우에는 그룹핑하지 말고 standalone 목록에 유지하세요.\n"
        "5. 동일 그룹 내 변형 용어의 원형 정보를 유지하여 후속 단계에서 `original_variants`를 갱신할 수 있도록 하세요.\n"
        "6. 응답은 반드시 JSON만 출력하세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        '  "groups": [\n'
        "    {\n"
        '      "canonical": "대표 용어",\n'
        '      "variants": ["대표 용어", "동의어1", "동의어2"],\n'
        '      "confidence": 0.92,\n'
        '      "rationale": "묶은 이유와 증거 요약"\n'
        "    }\n"
        "  ],\n"
        '  "standalone": ["그룹화되지 않은 용어1", "용어2"]\n'
        "}"
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    return full_prompt


def _build_candidate_payload(
    *,
    candidate_keywords: Sequence[Mapping[str, object]],
    max_variants: int,
) -> List[Dict[str, object]]:
    """
    LLM 프롬프트에 포함할 후보 키워드 정보를 정규화합니다.

    Args:
        candidate_keywords: AggregatorNode 후보 키워드 시퀀스.
        max_variants: 각 키워드의 변형 용어 최대 개수.

    Returns:
        프롬프트에 포함할 정규화된 후보 정보 리스트.
    """
    payload: List[Dict[str, object]] = []

    for keyword in candidate_keywords:
        term = str(keyword.get("term", "")).strip()
        score = float(keyword.get("score", 0.0) or 0.0)

        original_variants = [
            str(value).strip()
            for value in keyword.get("original_variants", [])
            if str(value).strip()
        ]

        unique_variants = list(dict.fromkeys([term, *original_variants]))
        trimmed_variants = unique_variants[:max_variants]

        sources = sorted(
            {
                str(value).strip()
                for value in keyword.get("sources", [])
                if str(value).strip()
            }
        )

        # evidence_ids 처리 (evidence 필드는 무시)
        evidence_ids = keyword.get("evidence_ids", [])
        if not evidence_ids and "evidence" in keyword:
            # 하위 호환성: evidence 필드가 있으면 경고하고 무시
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"[_build_candidate_payload] 키워드 '{term}'에 'evidence' 필드가 있지만 "
                f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
            )

        # 동의어 검증에는 evidence_ids가 필요 없으므로 제외 (토큰 절감)
        payload.append(
            {
                "term": term,
                "score": score,
                "rank": int(keyword.get("rank", 0) or 0),
                "original_variants": trimmed_variants,
                "sources": sources,
                "occurrence_count": int(keyword.get("occurrence_count", 1) or 1),
            }
        )

    return payload


def prepare_insight_prompt_inputs(
    aggregated_keywords: Sequence[Mapping[str, object]],
    raw_records: Sequence[Mapping[str, object]],
    *,
    summary_paragraphs: int = 4,
    max_sources: int = 5,
    include_excerpts: bool = True,
    id_mapping: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, object]:
    """
    InsightNode 프롬프트 구성을 위한 입력 데이터를 정규화합니다.

    Args:
        aggregated_keywords: AggregatorNode에서 전달된 최종 키워드 시퀀스.
        raw_records: CollectorNode 입력 원본 레코드 시퀀스.
        summary_paragraphs: 내러티브 요약 문단 목표 개수.
        max_sources: 강조할 핵심 출처 최대 개수.
        include_excerpts: 출처 하이라이트에 발췌문을 포함할지 여부.
        id_mapping: ID 매핑 딕셔너리 (evidence_ids를 원본 텍스트로 복원하기 위해, 선택적).

    Returns:
        프롬프트에 바로 사용할 수 있도록 정규화된 데이터 딕셔너리.

    Raises:
        ValueError: 필수 입력이 비어 있거나 유효하지 않은 경우.
    """
    if not aggregated_keywords:
        raise ValueError("aggregated_keywords가 비어 있습니다.")

    if summary_paragraphs < 1:
        raise ValueError("summary_paragraphs 값은 1 이상이어야 합니다.")

    if max_sources < 1:
        raise ValueError("max_sources 값은 1 이상이어야 합니다.")

    normalized_summary_count = max(3, min(summary_paragraphs, 5))

    keyword_payload = _sanitize_aggregated_keywords(aggregated_keywords, id_mapping=id_mapping)
    source_highlights = _build_source_highlights(
        keyword_payload,
        raw_records,
        max_sources=max_sources,
        include_excerpts=include_excerpts,
    )

    return {
        "keywords": keyword_payload,
        "source_highlights": source_highlights,
        "summary_paragraphs": normalized_summary_count,
    }


def build_insight_prompt(
    aggregated_keywords: Sequence[Mapping[str, object]],
    raw_records: Sequence[Mapping[str, object]],
    *,
    summary_paragraphs: int = 4,
    max_sources: int = 5,
    include_excerpts: bool = True,
    prepared_inputs: Mapping[str, object] | None = None,
    id_mapping: Optional[Dict[int, Dict[str, Any]]] = None,
) -> str:
    """
    InsightNode에서 사용할 내러티브/인사이트 생성 프롬프트를 구성합니다.

    Args:
        aggregated_keywords: AggregatorNode가 반환한 최종 키워드 시퀀스.
        raw_records: CollectorNode 입력 원본 레코드 시퀀스.
        summary_paragraphs: 내러티브 요약 목표 문단 수.
        max_sources: 하이라이트할 핵심 출처 최대 개수.
        include_excerpts: 출처 하이라이트에 발췌문을 포함할지 여부.
        prepared_inputs: 사전 계산된 입력(prepare_insight_prompt_inputs 반환값).
        id_mapping: ID 매핑 딕셔너리 (evidence_ids를 원본 텍스트로 복원하기 위해, 선택적).

    Returns:
        Gemini API 호출에 사용할 전체 프롬프트 문자열.
    """
    if prepared_inputs is None:
        prepared_inputs = prepare_insight_prompt_inputs(
            aggregated_keywords,
            raw_records,
            summary_paragraphs=summary_paragraphs,
            max_sources=max_sources,
            include_excerpts=include_excerpts,
            id_mapping=id_mapping,
        )

    keywords_payload = prepared_inputs.get("keywords")
    source_highlights = prepared_inputs.get("source_highlights")
    normalized_summary_count = int(prepared_inputs.get("summary_paragraphs", 3))

    keywords_json = json.dumps(keywords_payload, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 디지털 자산 시장 분석가입니다.\n"
        "추출된 키워드를 기반으로 시장 내러티브를 요약하고 거래 인사이트를 제공하세요."
    )

    user_prompt = (
        "다음은 AggregatorNode에서 통합한 최종 키워드 리스트입니다:\n\n"
        f"{keywords_json}\n\n"
        f"참고용 주요 출처 하이라이트(최대 {max_sources}개):\n\n"
        f"{sources_json}\n\n"
        "요구사항:\n"
        f"1. 시장 내러티브 요약을 {normalized_summary_count}개 문단으로 작성하세요.\n"
        "   - 각 문단은 간결하게 작성하세요 (문단당 100~150자, 핵심 정보만 포함).\n"
        "   - 현재 시장에서 가장 주목받는 이슈와 키워드 간 연결성을 강조하세요.\n"
        "   - 시간적 흐름(최근 트렌드 변화)을 포함하되, 불필요한 설명은 생략하세요.\n"
        "   - 장황한 설명이나 반복적인 표현을 피하고, 핵심 내용만 압축하여 작성하세요.\n"
        "2. 거래 시사점을 기회(opportunities)와 위험(risks)으로 구분하여 작성하세요.\n"
        "   - 각 목록에는 최소 2개의 구체적인 항목을 포함하세요.\n"
        "   - 시장 심리를 두 가지 측면으로 분석하세요:\n"
        "     a) direction_sentiment (방향성 심리): 강한상승/상승/중립/하락/강한하락 중 하나\n"
        "     b) volatility_sentiment (변동성 심리): 급격한증가/증가/안정/감소/급격한감소 중 하나\n"
        "   - 각 심리 판단에 대해 신뢰도(0-100)와 근거 키워드(최대 3개)를 함께 제시하세요.\n"
        "3. 주요 출처 하이라이트 3~5개를 선택하여 제목, 링크(가능한 경우), 연관 키워드를 제시하세요.\n"
        "4. 모든 응답은 반드시 JSON 형식으로만 출력하세요.\n"
        "5. 근거와 정량 정보(점수, 출처)를 활용해 분석의 신뢰도를 높이세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        '  "narrative_summary": ["문단1", "문단2", "문단3"],\n'
        '  "trading_insights": {\n'
        '    "opportunities": ["인사이트1", "인사이트2"],\n'
        '    "risks": ["위험1", "위험2"],\n'
        '    "direction_sentiment": {\n'
        '      "value": "상승",\n'
        '      "confidence": 85,\n'
        '      "rationale_keywords": ["키워드1", "키워드2", "키워드3"]\n'
        '    },\n'
        '    "volatility_sentiment": {\n'
        '      "value": "증가",\n'
        '      "confidence": 72,\n'
        '      "rationale_keywords": ["키워드1", "키워드2"]\n'
        '    }\n'
        "  },\n"
        '  "key_sources": [\n'
        "    {\n"
        '      "title": "기사 제목 또는 메시지 요약",\n'
        '      "url": "링크 (RSS의 경우)",\n'
        '      "relevance": ["관련 키워드"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    return f"{system_prompt}\n\n{user_prompt}"


def parse_insight_response(response_text: str) -> Dict[str, object]:
    """
    InsightNode가 수신한 LLM 응답(JSON)을 파싱하고 검증합니다.

    Args:
        response_text: Gemini API에서 반환된 원본 텍스트.

    Returns:
        내러티브 요약 및 거래 인사이트가 포함된 정규화된 딕셔너리.

    Raises:
        ValueError: 응답 구조가 예상과 다를 때.
    """
    result = parse_json_from_llm_response(response_text, context="Insight 응답")

    if "narrative_summary" not in result:
        raise ValueError("Insight 응답에 'narrative_summary' 필드가 없습니다.")

    narrative_summary = result.get("narrative_summary")
    if not isinstance(narrative_summary, list) or not narrative_summary:
        raise ValueError("'narrative_summary'는 비어있지 않은 리스트여야 합니다.")

    normalized_summary = [str(paragraph).strip() for paragraph in narrative_summary if str(paragraph).strip()]
    if not normalized_summary:
        raise ValueError("'narrative_summary'에 유효한 문단이 없습니다.")

    trading_insights_raw = result.get("trading_insights", {})
    if not isinstance(trading_insights_raw, Mapping):
        raise ValueError("'trading_insights'는 딕셔너리여야 합니다.")

    opportunities = trading_insights_raw.get("opportunities", [])
    risks = trading_insights_raw.get("risks", [])

    # 방향성 심리 파싱
    direction_sentiment_raw = trading_insights_raw.get("direction_sentiment", {})
    if isinstance(direction_sentiment_raw, Mapping):
        direction_sentiment = {
            "value": str(direction_sentiment_raw.get("value", "중립")).strip() or "중립",
            "confidence": int(direction_sentiment_raw.get("confidence", 50) or 50),
            "rationale_keywords": [
                str(kw).strip() for kw in direction_sentiment_raw.get("rationale_keywords", [])
                if str(kw).strip()
            ][:3]  # 최대 3개
        }
    else:
        # 하위 호환성: 문자열로 전달된 경우
        direction_sentiment = {
            "value": str(direction_sentiment_raw).strip() or "중립",
            "confidence": 50,
            "rationale_keywords": []
        }

    # 변동성 심리 파싱
    volatility_sentiment_raw = trading_insights_raw.get("volatility_sentiment", {})
    if isinstance(volatility_sentiment_raw, Mapping):
        volatility_sentiment = {
            "value": str(volatility_sentiment_raw.get("value", "안정")).strip() or "안정",
            "confidence": int(volatility_sentiment_raw.get("confidence", 50) or 50),
            "rationale_keywords": [
                str(kw).strip() for kw in volatility_sentiment_raw.get("rationale_keywords", [])
                if str(kw).strip()
            ][:3]  # 최대 3개
        }
    else:
        # 하위 호환성: 문자열로 전달된 경우
        volatility_sentiment = {
            "value": str(volatility_sentiment_raw).strip() or "안정",
            "confidence": 50,
            "rationale_keywords": []
        }

    # 하위 호환성: 기존 market_sentiment 필드가 있는 경우
    if "market_sentiment" in trading_insights_raw and "direction_sentiment" not in trading_insights_raw:
        old_sentiment = str(trading_insights_raw.get("market_sentiment", "중립적")).strip()
        # 기존 값을 방향성으로 매핑
        sentiment_mapping = {
            "긍정적": "상승",
            "부정적": "하락",
            "중립적": "중립",
        }
        direction_sentiment = {
            "value": sentiment_mapping.get(old_sentiment, "중립"),
            "confidence": 50,
            "rationale_keywords": []
        }

    normalized_opportunities = [str(item).strip() for item in opportunities if str(item).strip()] if isinstance(opportunities, list) else []
    normalized_risks = [str(item).strip() for item in risks if str(item).strip()] if isinstance(risks, list) else []

    key_sources_raw = result.get("key_sources", [])
    if not isinstance(key_sources_raw, list):
        raise ValueError("'key_sources'는 리스트여야 합니다.")

    normalized_sources: List[Dict[str, object]] = []
    for item in key_sources_raw:
        if not isinstance(item, Mapping):
            raise ValueError("각 key_sources 항목은 딕셔너리여야 합니다.")

        title = str(item.get("title", "")).strip()
        if not title:
            raise ValueError("key_sources 항목에 'title'이 필요합니다.")

        url = item.get("url")
        relevance_raw = item.get("relevance", [])

        relevance = (
            [str(keyword).strip() for keyword in relevance_raw if str(keyword).strip()]
            if isinstance(relevance_raw, list)
            else []
        )

        normalized_sources.append(
            {
                "title": title,
                "url": str(url).strip() if isinstance(url, str) and url.strip() else None,
                "relevance": relevance,
            }
        )

    return {
        "narrative_summary": normalized_summary,
        "trading_insights": {
            "opportunities": normalized_opportunities,
            "risks": normalized_risks,
            "direction_sentiment": direction_sentiment,
            "volatility_sentiment": volatility_sentiment,
        },
        "key_sources": normalized_sources,
    }


def _sanitize_aggregated_keywords(
    aggregated_keywords: Sequence[Mapping[str, object]],
    id_mapping: Optional[Dict[int, Dict[str, Any]]] = None,
) -> List[Dict[str, object]]:
    """
    Insight 프롬프트에 포함할 키워드 정보를 정규화합니다.
    
    evidence_ids를 원본 텍스트로 복원합니다 (프롬프트에 포함하기 위해).

    Args:
        aggregated_keywords: AggregatorNode 최종 키워드 시퀀스.
        id_mapping: ID 매핑 딕셔너리 (evidence_ids를 원본 텍스트로 복원하기 위해).

    Returns:
        프롬프트에 포함할 정규화된 키워드 리스트.
    """
    sanitized: List[Dict[str, object]] = []

    for index, keyword in enumerate(aggregated_keywords, start=1):
        term = str(keyword.get("term", "")).strip()
        if not term:
            raise ValueError(f"aggregated_keywords[{index}]에 term 값이 없습니다.")

        score = float(keyword.get("score", 0.0) or 0.0)
        occurrence_count = int(keyword.get("occurrence_count", 1) or 1)

        original_variants = [
            str(value).strip() for value in keyword.get("original_variants", []) if str(value).strip()
        ]
        unique_variants = list(dict.fromkeys([term, *original_variants]))

        # evidence_ids를 원본 텍스트로 복원
        evidence_ids = keyword.get("evidence_ids", [])
        if not evidence_ids and "evidence" in keyword:
            logger.warning(
                f"[_sanitize_aggregated_keywords] 키워드 '{term}'에 'evidence' 필드가 있지만 "
                f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
            )
        
        evidence_texts = []
        if id_mapping and evidence_ids:
            for evidence_id in evidence_ids[:3]:  # 최대 3개만
                if isinstance(evidence_id, int) and evidence_id in id_mapping:
                    record = id_mapping[evidence_id]
                    text = str(record.get("text", "")).strip()
                    if text:
                        evidence_texts.append(text)
                else:
                    logger.warning(
                        f"[_sanitize_aggregated_keywords] 키워드 '{term}'의 evidence_id {evidence_id}가 "
                        f"ID 매핑에 없습니다. ID 매핑 통계: 총 레코드 수={len(id_mapping) if id_mapping else 'N/A'}"
                    )
        
        sources_values = [
            str(value).strip() for value in keyword.get("sources", []) if str(value).strip()
        ]

        sanitized.append(
            {
                "term": term,
                "score": score,
                "rank": int(keyword.get("rank", index) or index),
                "original_variants": unique_variants,
                "evidence": evidence_texts,  # 프롬프트에는 원본 텍스트 포함 (최대 3개)
                "sources": sources_values,
                "occurrence_count": occurrence_count,
            }
        )

    return sanitized


def _build_source_highlights(
    keyword_payload: Sequence[Mapping[str, object]],
    raw_records: Sequence[Mapping[str, object]],
    *,
    max_sources: int,
    include_excerpts: bool,
) -> List[Dict[str, object]]:
    """
    Insight 프롬프트에 포함할 핵심 출처 하이라이트를 구성합니다.

    Args:
        keyword_payload: 정규화된 키워드 리스트.
        raw_records: CollectorNode 입력 원본 레코드.
        max_sources: 최대 반환할 출처 수.
        include_excerpts: 발췌문 포함 여부.

    Returns:
        하이라이트 정보 리스트.
    """
    keyword_to_score: Dict[str, float] = {
        str(keyword["term"]).lower(): float(keyword.get("score", 0.0))
        for keyword in keyword_payload
    }

    variant_map: Dict[str, str] = {}
    for keyword in keyword_payload:
        canonical = str(keyword["term"]).strip()
        for variant in keyword.get("original_variants", []):
            variant_map[str(variant).strip().lower()] = canonical
        variant_map[canonical.lower()] = canonical

    highlights: List[Dict[str, object]] = []

    for record in raw_records:
        text = str(record.get("text", "") or "")
        meta = record.get("meta", {})
        meta_mapping: Mapping[str, object] = meta if isinstance(meta, Mapping) else {}

        title = str(meta_mapping.get("title", "") or "").strip()
        url = str(meta_mapping.get("url", "") or "").strip()
        channel = str(meta_mapping.get("channel", "") or "").strip()
        timestamp = str(record.get("timestamp", "") or "").strip()

        combined_content = " ".join(
            value
            for value in (
                text,
                title,
                channel,
                str(meta_mapping.get("summary", "") or ""),
                str(meta_mapping.get("description", "") or ""),
            )
            if isinstance(value, str)
        )
        lowered_content = combined_content.lower()

        matched_terms: Dict[str, float] = {}
        for variant_lower, canonical in variant_map.items():
            if variant_lower and variant_lower in lowered_content:
                score = keyword_to_score.get(canonical.lower(), 0.0)
                matched_terms[canonical] = matched_terms.get(canonical, 0.0) + max(score, 0.0)

        if not matched_terms:
            continue

        excerpt = text.strip()
        if include_excerpts:
            excerpt = excerpt[:400] if excerpt else ""
        else:
            excerpt = ""

        highlight_entry: Dict[str, object] = {
            "title": title or channel or "Unknown source",
            "url": url or None,
            "timestamp": timestamp,
            "matched_keywords": sorted(matched_terms.keys()),
            "score": round(sum(matched_terms.values()), 4),
        }

        if include_excerpts and excerpt:
            highlight_entry["excerpt"] = excerpt

        highlights.append(highlight_entry)

    # 점수와 매칭 키워드 수 기준 내림차순 정렬
    highlights.sort(
        key=lambda item: (
            float(item.get("score", 0.0)),
            len(item.get("matched_keywords", [])),
        ),
        reverse=True,
    )

    unique_highlights: List[Dict[str, object]] = []
    seen_keys: set[Tuple[str | None, str | None]] = set()
    for entry in highlights:
        dedup_key = (entry.get("title"), entry.get("url"))
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        unique_highlights.append(entry)

        if len(unique_highlights) >= max_sources:
            break

    return unique_highlights


# ============================================================================
# 세분화된 내러티브 프롬프트 (Macro / Crypto Native / Crypto-Macro)
# ============================================================================

def build_macro_narrative_prompt(
    keywords: List[Dict[str, Any]],
    source_highlights: List[Dict[str, Any]],
    num_paragraphs: int = 2
) -> str:
    """
    Macro 내러티브 프롬프트를 생성합니다.

    거시경제 요인(금리, 인플레이션, 주식시장, 규제 등)에 집중한 내러티브를 생성합니다.

    Args:
        keywords: Macro 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        num_paragraphs: 생성할 문단 수

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    import json

    keywords_json = json.dumps(keywords, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 거시경제 전문 분석가입니다.\n"
        "글로벌 금융시장, 중앙은행 정책, 경제 지표, 규제 동향 등 거시경제 요인이 "
        "금리, 주식, 환율, Commodity, 암호화폐 시장에 미치는 영향을 분석하세요."
    )

    user_prompt = (
        "다음은 거시경제 관련 키워드입니다:\n\n"
        f"{keywords_json}\n\n"
        f"참고용 주요 출처:\n\n{sources_json}\n\n"
        "요구사항:\n"
        f"1. Macro(거시경제) 내러티브를 {num_paragraphs}개 문단으로 작성하세요.\n"
        "   - 각 문단은 간결하게 작성하세요 (문단당 100~150자).\n"
        "   - 금리, 경제 지표, 인플레이션, 주식시장, 환율, 규제 등 전통 금융 요인에 집중하세요.\n"
        "   - 중앙은행 정책(연준, ECB 등)의 변화와 시장 반응을 포함하세요.\n"
        "   - 정량적 데이터(금리 %, 지수 변화, 경제지표 발표 등)를 가능한 포함하세요.\n"
        "   - 시장의 Event들을 정리하고 그 Event들이 금리/주식/환율/Commodity 시장에 미칠 영향을 분석하세요.\n"
        "   - 금리/주식/환율/Commodity등 각 시장이 서로에게 미칠 수 있는 원인들을 분석하세요.\n"
        "   - 시장에 미칠 영향은 근거를 명확하게 작성해주세요.\n"
        "2. 모든 응답은 반드시 JSON 형식으로만 출력하세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        f'  "narrative": ["문단1", "문단2"{", ..." if num_paragraphs > 2 else ""}]\n'
        "}"
    )

    return f"{system_prompt}\n\n{user_prompt}"


def build_crypto_native_narrative_prompt(
    keywords: List[Dict[str, Any]],
    source_highlights: List[Dict[str, Any]],
    num_paragraphs: int = 2
) -> str:
    """
    Crypto Native 내러티브 프롬프트를 생성합니다.

    블록체인 기술, DeFi, NFT, 프로토콜 업데이트 등 암호화폐 고유 동향에 집중합니다.

    Args:
        keywords: Crypto Native 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        num_paragraphs: 생성할 문단 수

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    import json

    keywords_json = json.dumps(keywords, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 월스트리트의 최고 투자 책임자(CIO)에게 보고하는 최고 수준의 가상자산 시장 전략가입니다. \n"
        "당신의 목표는 제공된 데이터(뉴스 기사 및 텔레그램 대화)에서 현재 시장을 움직이는 핵심 내러티브를 추출하고, \n"
        "이를 바탕으로 시장 심리와 전망을 분석하는 것입니다."
    )

    user_prompt = (
        "다음은 Crypto Native 관련 키워드입니다:\n\n"
        f"{keywords_json}\n\n"
        f"참고용 주요 출처:\n\n{sources_json}\n\n"
        "요구사항:\n"
        f"1. 당신은 다음 단계의 분석을 반드시 수행해야 합니다.\n"
        "   - 데이터 필터링 및 정량화: 모든 데이터를 스캔하여 가장 빈번하게 언급된 키워드/주제 상위 10개를 추출하고, 각 키워드에 대한 언급량(빈도수)을 대략적으로 파악합니다.\n"
        "   - 핵심 내러티브 도출: 빈도수와 내용의 중요성을 종합하여, 현재 시장 참여자들의 집단 심리를 가장 강력하게 지배하는 상위 5가지 이내의 핵심 내러티브를 도출하십시오.\n"
        "   - 각 내러티브의 근거 제시: 도출된 각 내러티브에 대해, 뉴스(기관/규제 동향)와 텔레그램 대화(개인 투자자 심리)에서 발견된 가장 결정적인 2~3가지 근거 문장을 인용하여 제시하십시오.\n"
        "   - 시장 심리 분석: 각 내러티브의 성격(긍정적/부정적/중립적)을 종합하여 현재 시장의 전반적인 심리 상태를 낙관(Bullish), 중립(Neutral), 비관(Bearish) 중 하나로 명확히 판단하십시오.\n"
        "2. Crypto Native(암호화폐 고유 동향) 내러티브를 {num_paragraphs}개 문단으로 작성하세요.\n"
        "   - 각 문단은 간결하게 작성하세요 (문단당 100~200자).\n"
        "   - 첫 번째 문단은, 핵심 성장 동력 분석.\n"
        "       - 현재 가장 강력하게 시장 성장을 견인하는 Crypto Native 트렌드 (예: L2 경쟁 심화, 특정 RWA 프로토콜의 급부상) 하나를 집중 분석하고, 해당 트렌드의 온체인 근거 (TVL 급증, 트랜잭션 수 증가 등)를 명확히 제시하며 시장 전반의 긍정적 기대감을 서술하세요..\n"
        "   - 두 번째 문단은, 주요 체인 영향 및 연관관계 분석.\n"
        "       - 문단 1에서 분석한 트렌드와 기술적/네트워크적 이벤트 (프로토콜 업데이트, 대형 에어드롭 스냅샷 등)를 연결하여, 이것이 BTC/ETH 등 주요 코인의 펀더멘털 및 관련 L1/L2 체인의 생태계 활성화에 미치는 영향을 구체적으로 분석하세요. (예: L2 활성화가 ETH 가치에 미치는 긍정적 영향).\n"
        "   - 세 번째 문단은, 리스크와 심리적 불안 요인 분석.\n"
        "       - 해킹, 러그풀, FUD 등 부정적인 내용 중에서도 시장 참여자들의 심리를 가장 위축시킨 핵심 리스크를 선정하여 분석하세요. 이 리스크가 투자자들의 리스크 회피 심리와 단기 매도 압력에 미치는 영향을 강조하여 서술하세요.\n"
        "3. 모든 응답은 반드시 JSON 형식으로만 출력하세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        f'  "narrative": ["문단1", "문단2"{", ..." if num_paragraphs > 2 else ""}]\n'
        "}"
    )

    return f"{system_prompt}\n\n{user_prompt}"


def build_crypto_macro_narrative_prompt(
    keywords: List[Dict[str, Any]],
    source_highlights: List[Dict[str, Any]],
    num_paragraphs: int = 2
) -> str:
    """
    Crypto-Macro 내러티브 프롬프트를 생성합니다.

    ETF, 기관 투자, 규제, 메인스트림 채택 등 교차 영향을 분석합니다.

    Args:
        keywords: Crypto-Macro 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        num_paragraphs: 생성할 문단 수

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    import json

    keywords_json = json.dumps(keywords, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)

    system_prompt = (
        "당신은 암호화폐와 전통 금융의 교차점을 분석하는 전문가입니다.\n"
        "기관 투자, ETF, 규제, 메인스트림 채택 등 두 세계가 만나는 영역의 "
        "동향과 그 영향을 분석하세요."
    )

    user_prompt = (
        "다음은 Crypto-Macro(교차 영향) 관련 키워드입니다:\n\n"
        f"{keywords_json}\n\n"
        f"참고용 주요 출처:\n\n{sources_json}\n\n"
        "요구사항:\n"
        f"1. Crypto-Macro(교차 영향) 내러티브를 {num_paragraphs}개 문단으로 작성하세요.\n"
        "   - 각 문단은 간결하게 작성하세요 (문단당 100~150자).\n"
        "   - ETF 승인, 기관 투자 유입, 상장 등 자본 흐름에 집중하세요.\n"
        "   - SEC, CFTC 등 규제 당국의 움직임과 법적 판결을 분석하세요.\n"
        "   - 전통 금융 기관(블랙록, 피델리티 등)의 암호화폐 진출을 다루세요.\n"
        "   - 메인스트림 채택(결제, CBDC 등) 동향을 포함하세요.\n"
        "2. 모든 응답은 반드시 JSON 형식으로만 출력하세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        f'  "narrative": ["문단1", "문단2"{", ..." if num_paragraphs > 2 else ""}]\n'
        "}"
    )

    return f"{system_prompt}\n\n{user_prompt}"


def build_integrated_narrative_prompt(
    macro_narrative: List[str],
    crypto_native_narrative: List[str],
    crypto_macro_narrative: List[str],
    all_keywords: List[Dict[str, Any]],
    num_paragraphs: int = 3
) -> str:
    """
    통합 내러티브 프롬프트를 생성합니다.

    3개 카테고리의 내러티브를 종합하여 전체 시장 그림을 그립니다.

    Args:
        macro_narrative: Macro 내러티브 문단 리스트
        crypto_native_narrative: Crypto Native 내러티브 문단 리스트
        crypto_macro_narrative: Crypto-Macro 내러티브 문단 리스트
        all_keywords: 전체 키워드 리스트
        num_paragraphs: 생성할 문단 수

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    import json

    keywords_json = json.dumps(all_keywords[:15], ensure_ascii=False, indent=2)  # 상위 15개만

    system_prompt = (
        "당신은 디지털 자산 시장 전체를 조망하는 수석 분석가입니다.\n"
        "거시경제, 암호화폐 고유 동향, 두 세계의 교차점을 모두 고려하여 "
        "통합적인 시장 전망을 제시하세요."
    )

    macro_text = "\n".join(f"- {p}" for p in macro_narrative)
    crypto_native_text = "\n".join(f"- {p}" for p in crypto_native_narrative)
    crypto_macro_text = "\n".join(f"- {p}" for p in crypto_macro_narrative)

    user_prompt = (
        "다음은 카테고리별로 분석된 내러티브입니다:\n\n"
        "**Macro (거시경제)**:\n"
        f"{macro_text}\n\n"
        "**Crypto Native (암호화폐 고유 동향)**:\n"
        f"{crypto_native_text}\n\n"
        "**Crypto-Macro (교차 영향)**:\n"
        f"{crypto_macro_text}\n\n"
        f"**주요 키워드**:\n{keywords_json}\n\n"
        "요구사항:\n"
        f"1. 위 3개 카테고리를 종합한 통합 내러티브를 {num_paragraphs}개 문단으로 작성하세요.\n"
        "   - 각 문단은 간결하게 작성하세요 (문단당 100~150자).\n"
        "   - 거시경제, 암호화폐 고유 동향, 교차 영향을 유기적으로 연결하세요.\n"
        "   - 전체 시장의 큰 그림과 주요 투자 테마를 제시하세요.\n"
        "   - 단순 요약이 아닌, 카테고리 간 상호작용과 시너지를 분석하세요.\n"
        "   - 투자자 관점에서 실용적인 시사점을 도출하세요.\n"
        "2. 모든 응답은 반드시 JSON 형식으로만 출력하세요.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        f'  "narrative": ["문단1", "문단2", "문단3"{", ..." if num_paragraphs > 3 else ""}]\n'
        "}"
    )

    return f"{system_prompt}\n\n{user_prompt}"


def parse_narrative_response(response_text: str, category: str) -> List[str]:
    """
    카테고리별 내러티브 응답을 파싱합니다.

    Args:
        response_text: LLM 응답 텍스트
        category: 카테고리 이름 (에러 메시지용)

    Returns:
        내러티브 문단 리스트

    Raises:
        ValueError: 응답 구조가 예상과 다를 때
    """
    result = parse_json_from_llm_response(response_text, context=f"{category} Narrative 응답")

    if "narrative" not in result:
        raise ValueError(f"{category} Narrative 응답에 'narrative' 필드가 없습니다.")

    narrative = result.get("narrative")
    if not isinstance(narrative, list) or not narrative:
        raise ValueError(f"'{category} narrative'는 비어있지 않은 리스트여야 합니다.")

    normalized_narrative = [str(paragraph).strip() for paragraph in narrative if str(paragraph).strip()]
    if not normalized_narrative:
        raise ValueError(f"'{category} narrative'에 유효한 문단이 없습니다.")

    return normalized_narrative

"""
프롬프트 템플릿 모듈

LLM 파이프라인에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any


logger = logging.getLogger(__name__)


def parse_json_from_llm_response(
    response_text: str, context: str = "LLM 응답"
) -> dict[str, object]:
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
        open_braces > close_braces
        or open_brackets > close_brackets
        or (
            sanitized_text.rstrip().endswith(",")
            and not sanitized_text.rstrip().endswith("}")
        )
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


def build_keyword_extraction_prompt(
    chunk: list[dict[str, object]],
    economic_events: list[dict[str, Any]] | None = None,
) -> str:
    """
    카테고리별 키워드 추출을 위한 개선된 프롬프트를 구성합니다.

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
        economic_events: Economic Calendar 이벤트 리스트 (선택적).
            Macro 카테고리 키워드 추출에 활용됩니다.

    Returns:
        구성된 프롬프트 문자열.
    """
    chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)

    # Economic Calendar 컨텍스트 생성
    ec_context = ""
    if economic_events:
        # 최근 중요 이벤트만 필터링 (최대 20개)
        filtered_events = [
            {
                "event": e.get("text", ""),
                "importance": e.get("meta", {}).get("importance", ""),
                "country": e.get("meta", {}).get("country", ""),
            }
            for e in economic_events[:20]
        ]
        ec_json = json.dumps(filtered_events, ensure_ascii=False, indent=2)
        ec_context = (
            "\n\n**참고: 최근 주요 경제 일정 (Economic Calendar)**\n"
            f"{ec_json}\n"
            "위 경제 지표 발표 일정을 참고하여 Macro 카테고리 키워드를 추출하는 데 활용하세요.\n"
        )

    system_prompt = (
        "당신은 디지털 자산 시장의 내러티브 분석 전문가입니다.\n"
        "주어진 텍스트에서 시장에 영향을 미칠 수 있는 핵심 키워드를 카테고리별로 추출하세요."
    )

    user_prompt = (
        "다음은 RSS 기사와 텔레그램 메시지에서 수집한 텍스트입니다.\n"
        '각 레코드는 고유한 "id" 필드를 가지고 있습니다:\n\n'
        f"{chunk_json}{ec_context}\n\n"
        "**중요: 각 카테고리별로 최소 3개 이상의 키워드를 반드시 추출하세요.**\n\n"
        "요구사항:\n"
        "1. 다음 3개 카테고리별로 키워드를 구조적으로 추출하세요:\n"
        "   - **macro_keywords** (거시경제): 금리, 연준(Fed), BOJ(일본은행), ECB(유럽중앙은행), BOE(영란은행), 중앙은행 정책, 인플레이션, CPI, GDP, 경제지표, 고용, 실업률, PMI, 주식시장(나스닥, S&P500), 환율(달러-엔, 달러-원), 채권, 경기침체, 양적완화 등 전통 금융시장 관련 키워드\n"
        "   - **crypto_native_keywords** (암호화폐 고유): 비트코인, 이더리움, 알트코인, DeFi, NFT, 블록체인 기술, 온체인 데이터, 스마트컨트랙트, Web3, 토큰이코노미, PoS, PoW 등 암호화폐 생태계 고유 키워드\n"
        "   - **crypto_macro_keywords** (교차 영향): 비트코인 ETF, 기관투자, 규제(SEC, CFTC), 상장, 거래소, CBDC, 결제, 스테이블코인, 상관관계, 헤지 등 전통 금융과 암호화폐의 교차점 키워드\n\n"
        "   **중요**: 각 중앙은행(Fed, BOJ, ECB, BOE 등)의 금리 결정이나 정책 발표가 있을 경우, 해당 중앙은행을 개별 키워드로 추출하세요.\n\n"
        "2. 각 카테고리당 최소 3개, 권장 5~10개의 키워드를 추출하세요.\n"
        "   - 데이터에 직접 언급이 부족하더라도, 간접적으로 연관된 키워드도 포함하여 각 카테고리를 채우세요.\n"
        "   - 예: '고용 둔화' → 'GDP 전망', '경기 둔화' 등으로 확장\n\n"
        "3. 각 키워드에 대해 다음 정보를 제공하세요:\n"
        "   - term: 키워드 용어\n"
        "   - score: 중요도 점수 (0-100, 50점 이상만 포함)\n"
        "   - evidence_ids: 해당 키워드를 지지하는 레코드의 id 값 리스트 (1~3개)\n"
        "   - sources: RSS 기사 제목 또는 텔레그램 채널명 (1~3개)\n\n"
        "중요: evidence_ids 필드에는 원문 문장이 아닌 레코드의 id 값만 포함하세요.\n"
        "예를 들어, id가 123, 456, 789인 레코드가 키워드를 지지한다면, evidence_ids는 [123, 456, 789]입니다.\n\n"
        "응답 형식 (JSON):\n"
        "{\n"
        '  "macro_keywords": [\n'
        '    {"term": "연준(Fed)", "score": 90, "evidence_ids": [1, 2, 3], "sources": ["출처1", "출처2"]},\n'
        '    {"term": "BOJ(일본은행)", "score": 88, "evidence_ids": [4, 5], "sources": ["출처3"]},\n'
        '    {"term": "고용지표", "score": 85, "evidence_ids": [6, 7], "sources": ["출처4"]}\n'
        "  ],\n"
        '  "crypto_native_keywords": [\n'
        '    {"term": "비트코인(BTC)", "score": 95, "evidence_ids": [6, 7, 8], "sources": ["출처4", "출처5"]},\n'
        '    {"term": "이더리움(ETH)", "score": 88, "evidence_ids": [9, 10], "sources": ["출처6"]}\n'
        "  ],\n"
        '  "crypto_macro_keywords": [\n'
        '    {"term": "비트코인 ETF", "score": 92, "evidence_ids": [11, 12], "sources": ["출처7", "출처8"]},\n'
        '    {"term": "기관투자", "score": 80, "evidence_ids": [13], "sources": ["출처9"]}\n'
        "  ]\n"
        "}"
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    return full_prompt


def parse_keyword_extraction_response(
    response_text: str, id_mapping: dict[int, dict[str, Any]] | None = None
) -> dict[str, object]:
    """
    카테고리별 키워드 추출 응답을 파싱하고 검증합니다.

    새로운 구조화된 응답 형식을 지원합니다:
    {
      "macro_keywords": [...],
      "crypto_native_keywords": [...],
      "crypto_macro_keywords": [...]
    }

    각 카테고리의 키워드를 단일 리스트로 병합하며, category 필드를 자동으로 추가합니다.
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
                    "category": "macro",
                    "score": 85,
                    "evidence_ids": [123, 456, 789],
                    "sources": ["출처1", "출처2"]
                }
            ]
        }

    Raises:
        ValueError: 응답 구조가 예상과 다를 때.
    """
    logger = logging.getLogger(__name__)

    result = parse_json_from_llm_response(response_text, context="키워드 추출 응답")

    # 새로운 구조화된 응답 형식 확인
    category_fields = [
        "macro_keywords",
        "crypto_native_keywords",
        "crypto_macro_keywords",
    ]
    has_structured_format = any(field in result for field in category_fields)

    all_keywords = []

    if has_structured_format:
        # 새로운 형식: 카테고리별 키워드 처리
        logger.info(
            "[parse_keyword_extraction_response] 구조화된 카테고리별 응답 형식 감지"
        )

        for category_field in category_fields:
            category_keywords = result.get(category_field, [])

            if not isinstance(category_keywords, list):
                logger.warning(
                    f"[parse_keyword_extraction_response] '{category_field}'가 리스트가 아닙니다: "
                    f"{type(category_keywords)}. 건너뜁니다."
                )
                continue

            # 카테고리명 추출 (macro_keywords → macro)
            category_name = category_field.replace("_keywords", "")

            logger.info(
                f"[parse_keyword_extraction_response] {category_field}: {len(category_keywords)}개 키워드"
            )

            # 최소 개수 검증
            if len(category_keywords) < 3:
                logger.warning(
                    f"[parse_keyword_extraction_response] {category_field}가 최소 개수(3개) 미만: "
                    f"{len(category_keywords)}개"
                )

            # 각 키워드에 category 필드 추가
            for kw in category_keywords:
                if isinstance(kw, dict):
                    kw["category"] = category_name
                    # 스코어 필터링 (50점 미만 제외)
                    if kw.get("score", 0) >= 50:
                        all_keywords.append(kw)
                    else:
                        logger.debug(
                            f"[parse_keyword_extraction_response] 스코어 부족으로 제외: "
                            f"{kw.get('term', 'unknown')} (score={kw.get('score', 0)})"
                        )

        logger.info(
            f"[parse_keyword_extraction_response] 총 {len(all_keywords)}개 키워드 (스코어 50+ 필터 적용)"
        )

    else:
        # 기존 형식: keywords 배열 (하위 호환성)
        if "keywords" not in result:
            raise ValueError(
                "키워드 추출 응답에 'keywords' 또는 카테고리별 필드가 없습니다."
            )

        if not isinstance(result["keywords"], list):
            raise ValueError("키워드 추출 응답의 'keywords' 필드가 리스트가 아닙니다.")

        all_keywords = result["keywords"]
        logger.info(
            "[parse_keyword_extraction_response] 기존 형식 (keywords 배열) 사용"
        )

    # evidence_ids 검증 및 정리
    for index, keyword in enumerate(all_keywords, start=1):
        if not isinstance(keyword, dict):
            raise ValueError(f"키워드 {index}이 딕셔너리가 아닙니다: {type(keyword)}")

        required_fields = ("term", "score")

        for field in required_fields:
            if field not in keyword:
                raise ValueError(f"키워드 {index}에 필수 필드 '{field}'가 없습니다.")

        # category 필드 검증
        if "category" in keyword:
            category = keyword.get("category")
            valid_categories = ("macro", "crypto_native", "crypto_macro")
            if category not in valid_categories:
                logger.warning(
                    f"[parse_keyword_extraction_response] 키워드 {index} ('{keyword.get('term', 'unknown')}')의 "
                    f"카테고리 '{category}'가 유효하지 않습니다. 유효한 값: {valid_categories}"
                )

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

    # 최종 결과를 keywords 배열로 반환
    return {"keywords": all_keywords}


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
) -> list[dict[str, object]]:
    """
    LLM 프롬프트에 포함할 후보 키워드 정보를 정규화합니다.

    Args:
        candidate_keywords: AggregatorNode 후보 키워드 시퀀스.
        max_variants: 각 키워드의 변형 용어 최대 개수.

    Returns:
        프롬프트에 포함할 정규화된 후보 정보 리스트.
    """
    payload: list[dict[str, object]] = []

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
    id_mapping: dict[int, dict[str, Any]] | None = None,
) -> dict[str, object]:
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

    keyword_payload = _sanitize_aggregated_keywords(
        aggregated_keywords, id_mapping=id_mapping
    )
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
    id_mapping: dict[int, dict[str, Any]] | None = None,
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
        "    },\n"
        '    "volatility_sentiment": {\n'
        '      "value": "증가",\n'
        '      "confidence": 72,\n'
        '      "rationale_keywords": ["키워드1", "키워드2"]\n'
        "    }\n"
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


def parse_insight_response(response_text: str) -> dict[str, object]:
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

    normalized_summary = [
        str(paragraph).strip()
        for paragraph in narrative_summary
        if str(paragraph).strip()
    ]
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
            "value": str(direction_sentiment_raw.get("value", "중립")).strip()
            or "중립",
            "confidence": int(direction_sentiment_raw.get("confidence", 50) or 50),
            "rationale_keywords": [
                str(kw).strip()
                for kw in direction_sentiment_raw.get("rationale_keywords", [])
                if str(kw).strip()
            ][
                :3
            ],  # 최대 3개
        }
    else:
        # 하위 호환성: 문자열로 전달된 경우
        direction_sentiment = {
            "value": str(direction_sentiment_raw).strip() or "중립",
            "confidence": 50,
            "rationale_keywords": [],
        }

    # 변동성 심리 파싱
    volatility_sentiment_raw = trading_insights_raw.get("volatility_sentiment", {})
    if isinstance(volatility_sentiment_raw, Mapping):
        volatility_sentiment = {
            "value": str(volatility_sentiment_raw.get("value", "안정")).strip()
            or "안정",
            "confidence": int(volatility_sentiment_raw.get("confidence", 50) or 50),
            "rationale_keywords": [
                str(kw).strip()
                for kw in volatility_sentiment_raw.get("rationale_keywords", [])
                if str(kw).strip()
            ][
                :3
            ],  # 최대 3개
        }
    else:
        # 하위 호환성: 문자열로 전달된 경우
        volatility_sentiment = {
            "value": str(volatility_sentiment_raw).strip() or "안정",
            "confidence": 50,
            "rationale_keywords": [],
        }

    # 하위 호환성: 기존 market_sentiment 필드가 있는 경우
    if (
        "market_sentiment" in trading_insights_raw
        and "direction_sentiment" not in trading_insights_raw
    ):
        old_sentiment = str(
            trading_insights_raw.get("market_sentiment", "중립적")
        ).strip()
        # 기존 값을 방향성으로 매핑
        sentiment_mapping = {
            "긍정적": "상승",
            "부정적": "하락",
            "중립적": "중립",
        }
        direction_sentiment = {
            "value": sentiment_mapping.get(old_sentiment, "중립"),
            "confidence": 50,
            "rationale_keywords": [],
        }

    normalized_opportunities = (
        [str(item).strip() for item in opportunities if str(item).strip()]
        if isinstance(opportunities, list)
        else []
    )
    normalized_risks = (
        [str(item).strip() for item in risks if str(item).strip()]
        if isinstance(risks, list)
        else []
    )

    key_sources_raw = result.get("key_sources", [])
    if not isinstance(key_sources_raw, list):
        raise ValueError("'key_sources'는 리스트여야 합니다.")

    normalized_sources: list[dict[str, object]] = []
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
                "url": (
                    str(url).strip() if isinstance(url, str) and url.strip() else None
                ),
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
    id_mapping: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, object]]:
    """
    Insight 프롬프트에 포함할 키워드 정보를 정규화합니다.

    evidence_ids를 원본 텍스트로 복원합니다 (프롬프트에 포함하기 위해).

    Args:
        aggregated_keywords: AggregatorNode 최종 키워드 시퀀스.
        id_mapping: ID 매핑 딕셔너리 (evidence_ids를 원본 텍스트로 복원하기 위해).

    Returns:
        프롬프트에 포함할 정규화된 키워드 리스트.
    """
    sanitized: list[dict[str, object]] = []

    for index, keyword in enumerate(aggregated_keywords, start=1):
        term = str(keyword.get("term", "")).strip()
        if not term:
            raise ValueError(f"aggregated_keywords[{index}]에 term 값이 없습니다.")

        score = float(keyword.get("score", 0.0) or 0.0)
        occurrence_count = int(keyword.get("occurrence_count", 1) or 1)

        original_variants = [
            str(value).strip()
            for value in keyword.get("original_variants", [])
            if str(value).strip()
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
            str(value).strip()
            for value in keyword.get("sources", [])
            if str(value).strip()
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
) -> list[dict[str, object]]:
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
    keyword_to_score: dict[str, float] = {
        str(keyword["term"]).lower(): float(keyword.get("score", 0.0))
        for keyword in keyword_payload
    }

    variant_map: dict[str, str] = {}
    for keyword in keyword_payload:
        canonical = str(keyword["term"]).strip()
        for variant in keyword.get("original_variants", []):
            variant_map[str(variant).strip().lower()] = canonical
        variant_map[canonical.lower()] = canonical

    highlights: list[dict[str, object]] = []

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

        matched_terms: dict[str, float] = {}
        for variant_lower, canonical in variant_map.items():
            if variant_lower and variant_lower in lowered_content:
                score = keyword_to_score.get(canonical.lower(), 0.0)
                matched_terms[canonical] = matched_terms.get(canonical, 0.0) + max(
                    score, 0.0
                )

        if not matched_terms:
            continue

        excerpt = text.strip()
        excerpt = (excerpt[:400] if excerpt else "") if include_excerpts else ""

        highlight_entry: dict[str, object] = {
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

    unique_highlights: list[dict[str, object]] = []
    seen_keys: set[tuple[str | None, str | None]] = set()
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


def _build_macro_prompt_base(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> tuple[str, str]:
    """
    Macro 프롬프트의 공통 부분을 구성합니다.

    이 헬퍼 함수는 system_prompt와 user_prompt_base(데이터 섹션 + 작성 원칙)를 반환합니다.
    Key Points 프롬프트와 Narrative 프롬프트에서 재사용됩니다.

    Args:
        keywords: Macro 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        economic_events: Economic Calendar 이벤트 리스트 (선택)

    Returns:
        (system_prompt, user_prompt_base) 튜플
        - system_prompt: 역할 정의
        - user_prompt_base: 데이터 섹션 + 공통 작성 원칙
    """
    keywords_json = json.dumps(keywords, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)

    # Economic Calendar 과거/미래 분리
    past_events_text, future_events_text = format_economic_calendar_split(
        economic_events
    )

    system_prompt = (
        "당신은 거시경제 전문 분석가이자 현업 트레이더입니다.\n"
        "글로벌 금융시장, 중앙은행 정책, 경제 지표, 규제 동향 등 거시경제 요인이 \n"
        "금리, 주식, 환율, Commodity시장에 미치는 영향을 분석하세요.\n"
        "\n"
        "당신의 목표는 주기적으로 시황을 작성하는 것이며, 근거를 기반으로 명확한 현황 분석 및 전망을 제시하는 것입니다.\n"
        "당신은 트레이더이기 때문에, 실제 매매에 활용할 수 있는 분석을 제공하세요."
    )

    user_prompt_parts = []

    # ========================================
    # 1. 데이터 제공 섹션
    # ========================================
    user_prompt_parts.append(
        "## 제공된 데이터\n\n"
        "### 키워드\n"
        f"{keywords_json}\n\n"
        "### 주요 출처\n"
        f"{sources_json}\n\n"
    )

    # Economic Calendar (과거/미래 분리)
    if past_events_text:
        user_prompt_parts.append(
            "### 발표된 경제 지표 (과거)\n" f"{past_events_text}\n\n"
        )

    if future_events_text:
        user_prompt_parts.append(
            "### 예정된 경제 지표 발표 일정 (미래)\n" f"{future_events_text}\n\n"
        )

    # ========================================
    # 2. 공통 작성 원칙
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 공통 작성 원칙\n\n"
        "### 인과관계 작성 시 주의사항\n"
        "- ✅ 원인과 결과를 논리적으로 연결: 'A로 인해 B 발생', 'A가 B를 견인'\n"
        "- ✅ 각 단계의 전달 경로 명확히: A → B → C\n"
        "- ✅ '~에도 불구하고'는 역접(반대) 상황에만 사용\n"
        "- ✅ **방향성 정확히 구분**:\n"
        "  • 매파 = 금리 인상 성향 → 달러 강세 압력\n"
        "  • 비둘기파 = 금리 인하 성향 → 달러 약세 압력\n"
        "  • 금리 인상 → 달러 강세, 금리 인하 → 달러 약세\n"
        "  • 강세/약세, 상승/하락, 우려/기대 등 반대 의미 용어 혼동 금지\n"
        "- ✅ 불확실한 인과관계는 단정 금지: '~할 가능성', '~로 해석됨' 등으로 표현\n\n"
        "### 긍정/부정 요인 구분\n"
        "상반된 요인이 있다면 명확히 구분하여 서술:\n"
        "- 긍정적 요인(금리 하락, 주가 상승 압력): ...\n"
        "- 부정적 요인(금리 상승, 주가 하락 압력): ...\n"
        "- 최종 결과: 어느 쪽 압력이 우세했는지 명시\n\n"
        "### 근거 및 데이터\n"
        "- 정량적 데이터 필수 포함 (%, bp, 지수, 금액 등)\n"
        "- 출처 명시 (Fed, Bloomberg, ECB 등)\n"
        "- 과거 유사 사례 참조 가능\n\n"
        "### 팩트 체크 (중요)\n"
        "- **예정된 경제 지표 일정은 반드시 제공된 Economic Calendar 데이터에서만 인용**하세요\n"
        "- 제공된 데이터에 없는 일정을 추측하거나 만들어내지 마세요\n"
        "- '다음 주', '다음 달' 등 시점 언급 시 반드시 출처 확인\n"
        "- 불확실한 일정은 언급하지 않거나 '확인 필요'로 표기\n"
    )

    user_prompt_base = "".join(user_prompt_parts)
    return system_prompt, user_prompt_base


def _build_crypto_prompt_base(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> tuple[str, str]:
    """
    Crypto 프롬프트의 공통 부분을 구성합니다.

    이 헬퍼 함수는 system_prompt와 user_prompt_base(데이터 섹션 + 작성 원칙)를 반환합니다.
    Key Points 프롬프트와 Narrative 프롬프트에서 재사용됩니다.

    Args:
        keywords: Crypto 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        economic_events: Economic Calendar 이벤트 리스트 (선택)

    Returns:
        (system_prompt, user_prompt_base) 튜플
        - system_prompt: 역할 정의
        - user_prompt_base: 데이터 섹션 + 공통 작성 원칙
    """
    keywords_json = json.dumps(keywords, ensure_ascii=False, indent=2)
    sources_json = json.dumps(source_highlights, ensure_ascii=False, indent=2)
    economic_calendar_text = format_economic_calendar(economic_events)

    system_prompt = (
        "당신은 암호화폐 시장 전문 분석가이자 현업 트레이더입니다.\n"
        "온체인 데이터(DeFi, 프로토콜, TVL)와 제도권 동향(ETF, 규제, 기관투자, Crypto 정책)을 종합 분석하고,\n"
        "시장 반응의 인과관계를 명확히 제시하세요.\n"
        "\n"
        "당신의 목표는 주기적으로 암호화폐 시장 시황을 작성하는 것이며, 근거를 기반으로 명확한 현황 분석 및 전망을 제시하는 것입니다.\n"
        "당신은 트레이더이기 때문에, 실제 매매에 활용할 수 있는 분석을 제공하세요."
    )

    user_prompt_parts = []

    # ========================================
    # 1. 데이터 제공 섹션
    # ========================================
    user_prompt_parts.append(
        "## 제공된 데이터\n\n"
        "### 키워드\n"
        f"{keywords_json}\n\n"
        "### 주요 출처\n"
        f"{sources_json}\n\n"
    )

    if economic_calendar_text:
        user_prompt_parts.append(
            f"{economic_calendar_text}\n\n"
            "**[참고]** 위 경제 지표가 암호화폐 투자 심리에 미치는 영향을 고려하세요.\n\n"
        )

    # ========================================
    # 2. 공통 작성 원칙
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 공통 작성 원칙\n\n"
        "### 인과관계 작성 시 주의사항\n"
        "- ✅ 원인과 결과를 논리적으로 연결\n"
        "- ✅ 각 단계의 전달 경로 명확히: ETF 승인 → 기관 자금 유입 → 가격 상승\n"
        "- ✅ '~에도 불구하고'는 역접(반대) 상황에만 사용\n"
        "- ✅ **정량적 데이터 우선**:\n"
        "  • TVL, ETF 자금 흐름, 거래량 등 구체적 수치 사용\n"
        "  • 추상적 표현 대신 정량적 데이터\n"
        "- ✅ 긍정/부정 요인 명확히 구분\n"
        "- ✅ 불확실한 인과관계는 단정 금지\n\n"
        "### 온체인 vs 제도권 균형\n"
        "- 두 영역의 동향을 균형있게 다룰 것\n"
        "- 상호 연결점 강조: 예) ETF 자금 유입 → 온체인 활동 증가\n"
        "- 한쪽 영역만 치우치지 않도록 주의\n\n"
    )

    user_prompt_base = "".join(user_prompt_parts)
    return system_prompt, user_prompt_base


def _build_integrated_prompt_base(
    macro_narrative: list[str],
    crypto_narrative: list[str],
    all_keywords: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> tuple[str, str]:
    """
    통합 프롬프트의 공통 부분을 구성합니다.

    이 헬퍼 함수는 system_prompt와 user_prompt_base(데이터 섹션 + 작성 원칙)를 반환합니다.
    Key Points 프롬프트와 Narrative 프롬프트에서 재사용됩니다.

    Args:
        macro_narrative: Macro 내러티브 문단 리스트
        crypto_narrative: Crypto 내러티브 문단 리스트
        all_keywords: 전체 키워드 리스트
        economic_events: Economic Calendar 이벤트 (선택사항)

    Returns:
        (system_prompt, user_prompt_base) 튜플
        - system_prompt: 역할 정의
        - user_prompt_base: 데이터 섹션 + 공통 작성 원칙
    """
    keywords_json = json.dumps(
        all_keywords[:15], ensure_ascii=False, indent=2
    )  # 상위 15개만

    system_prompt = (
        "당신은 디지털 자산 시장 전체를 조망하는 수석 분석가입니다.\n"
        "거시경제 환경과 암호화폐 시장 동향을 종합하여 통합적인 시장 전망을 제시하세요.\n"
        "\n"
        "당신의 목표는 Macro와 Crypto 내러티브를 연결하여 더 깊은 인사이트를 도출하는 것입니다.\n"
        "당신은 트레이더로서 실제 매매에 활용할 수 있는 인사이트를 제공하세요."
    )

    macro_text = "\n".join(f"- {p}" for p in (macro_narrative or []))
    crypto_text = "\n".join(f"- {p}" for p in (crypto_narrative or []))

    # Economic Calendar 포맷팅
    economic_calendar_text = format_economic_calendar(economic_events)

    user_prompt_parts = [
        "## 제공된 내러티브\n\n"
        "아래 두 내러티브를 참고하여 통합 분석을 작성하세요.\n\n"
        "### Macro (거시경제) 내러티브\n"
        f"{macro_text if macro_text else '(내용 없음)'}\n\n"
        "### Crypto (암호화폐) 내러티브\n"
        f"{crypto_text if crypto_text else '(내용 없음)'}\n\n"
        f"### 주요 키워드\n{keywords_json}\n\n"
    ]

    # Economic Calendar 추가 (있을 경우)
    if economic_calendar_text:
        user_prompt_parts.append(f"{economic_calendar_text}\n\n")

    # 공통 작성 원칙
    user_prompt_parts.append(
        "---\n\n"
        "## 공통 작성 원칙\n\n"
        "### 통합 내러티브의 목적\n"
        "- 단순 요약이 아닌 **두 내러티브 간의 연결고리**를 찾아 새로운 인사이트 도출\n"
        "- 거시경제 → 암호화폐 시장으로의 **전달 경로** 명확화\n"
        "- 투자자 관점에서 **실행 가능한 시사점** 제시\n\n"
        "### 필수 포함 요소\n"
        "1. **Macro-Crypto 연결고리**\n"
        "   - 금리/인플레이션이 암호화폐 시장에 미치는 영향\n"
        "   - 달러 강세/약세와 비트코인 가격의 상관관계\n"
        "   - 위험자산 선호도 변화가 크립토에 미치는 영향\n"
        '   - 예: "금리 인하 기대감 → 위험자산 선호 → ETF 자금 유입 → BTC 상승"\n\n'
        "2. **종합 시장 전망**\n"
        "   - 거시경제와 암호화폐 양쪽 요인을 고려한 시장 방향성\n"
        "   - 긍정/부정 요인의 상대적 힘 평가\n"
        "   - 단기 vs 중장기 전망 구분\n\n"
        "3. **투자 시사점**\n"
        "   - 현 환경에서 주목할 테마/섹터\n"
        "   - 리스크 요인과 대응 방안\n"
        "   - 포지셔닝 방향 (간접적 제안)\n\n"
        "### 작성 규칙\n"
        "- 정량적 데이터 인용 (금리, %, TVL, ETF 자금 등)\n"
        "- 인과관계 명확: A → B → C 형태로 전달 경로 서술\n"
        "- 단순 나열 금지: 두 내러티브를 연결하는 새로운 관점 필수\n"
    )

    user_prompt_base = "".join(user_prompt_parts)
    return system_prompt, user_prompt_base


def build_macro_narrative_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
    key_points: list[str] | None = None,
) -> str:
    """
    Macro 내러티브 프롬프트를 생성합니다.

    거시경제 요인(금리, 인플레이션, 주식시장, 규제 등)에 집중한 내러티브를 생성합니다.
    항상 2개 문단으로 고정: 문단1(과거 분석), 문단2(미래 전망)

    Args:
        keywords: Macro 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        economic_events: Economic Calendar 이벤트 리스트 (선택)
        key_points: Key Points 리스트 (2단계 LLM 호출 시 사용, 선택)
            - 제공 시 내러티브는 이 Key Points를 반드시 반영해야 함

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    # 공통 부분 재사용
    system_prompt, user_prompt_base = _build_macro_prompt_base(
        keywords, source_highlights, economic_events
    )

    # 문단 구성 안내 추가
    system_prompt += (
        "\n\n"
        "**문단 구성**:\n"
        "- 문단1: 과거 이벤트 분석 (발표된 경제 지표와 시장 반응)\n"
        "- 문단2: 미래 이벤트 전망 (예정된 경제 지표와 시장 기대)"
    )

    user_prompt_parts = [user_prompt_base]

    # Key Points가 제공된 경우 프롬프트에 추가
    if key_points:
        key_points_text = "\n".join(f"- {p}" for p in key_points)
        user_prompt_parts.append(
            "---\n\n"
            "## Key Points (필수 반영)\n\n"
            "아래 Key Points는 반드시 내러티브에 반영되어야 합니다:\n\n"
            f"{key_points_text}\n\n"
            "**중요**: 위 Key Points의 모든 내용을 내러티브에 포함하세요. "
            "Key Points에 있는 정량적 데이터와 인사이트를 누락하지 마세요.\n\n"
        )

    # ========================================
    # 문단별 작성 가이드 (Narrative 전용)
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 작성 가이드\n\n"
        "**반드시 2개 문단으로 작성**하세요. 각 문단의 구성은 다음과 같습니다:\n\n"
        "### 문단 1: 과거 이벤트 분석 (Past Analysis)\n\n"
        "**목적**: 발표된 경제 지표 및 각종 이벤트에 따른 반응을 분석합니다.\n\n"
        "**필수 포함 요소**:\n"
        "1. 발표된 주요 경제 지표 요약\n"
        "   - 실제 발표값 vs 시장 예상치 비교\n"
        "   - 이전 수치 대비 변화\n"
        "   - 주요 이벤트 내용 요약 및 시장 반응\n"
        '   - 예: "미국 11월 CPI는 2.7%(예상 2.6%)로 예상을 상회했으며, 이전 2.6% 대비 0.1%p 상승"\n\n'
        "2. 각 시장의 반응\n"
        "   - 금리: 국채 수익률, 정책금리 전망 변화\n"
        "   - 주식: 주요 지수 등락률 및 섹터별 영향\n"
        "   - 환율: 달러지수, 주요 통화쌍 변동\n"
        "   - Commodity: 금, 원유 등 주요 상품 가격\n"
        '   - 예: "10년물 국채 수익률은 4.2%로 10bp 상승하며 금리 인하 기대 후퇴를 반영"\n\n'
        "3. 시장 간 상호작용 분석\n"
        "   - 금리 상승 → 주식 하락 압력\n"
        "   - 달러 강세 → 신흥국 통화 약세\n"
        "   - 인플레이션 우려 → 금 가격 상승\n"
        "   - 각 연결고리의 인과관계 명확히 서술\n\n"
        "4. 긍정/부정 요인 종합 평가\n"
        "   - 긍정 요인: (예: 고용 지표 호조, 금리 인하 기대)\n"
        "   - 부정 요인: (예: 인플레이션 재가속, 금리 인상 압력)\n"
        "   - 최종 평가: 어느 요인이 우세했는지 명시\n\n"
        "**작성 규칙**:\n"
        "- 길이: 200~400자\n"
        "- 정량적 데이터 최소 3개 이상 포함 (%, bp, 지수 등)\n"
        "- 인과관계 명확: A → B → C 형태로 전달 경로 서술\n"
        "- 방향성 정확: 매파↔비둘기파, 강세↔약세, 상승↔하락 혼동 금지\n\n"
        "---\n\n"
        "### 문단 2: 미래 이벤트 전망 (Future Outlook)\n\n"
        "**목적**: 예정된 경제 지표 발표 일정과 시장 기대치를 바탕으로 시장 영향을 전망합니다.\n\n"
        "**필수 포함 요소**:\n"
        "1. 예정된 주요 경제 지표 일정\n"
        "   - 발표 예정일 및 지표명\n"
        "   - 시장 기대치 (컨센서스)\n"
        "   - 이전 수치 참고\n"
        "2. 시장 기대치 및 컨센서스\n"
        "   - 주요 기관/애널리스트 전망\n"
        "   - 시장이 가격에 반영한 수준\n"
        "3. 시나리오별 시장 영향 예측 (정량적)\n"
        "   - 기대치 충족 시: 예상되는 시장 반응\n"
        "   - 기대치 상회 시: 긍정적 시나리오 (구체적 수치로 표현)\n"
        "   - 기대치 하회 시: 부정적 시나리오 (구체적 수치로 표현)\n"
        "4. 투자 시사점\n"
        "   - 주목해야 할 핵심 변수\n"
        "   - 리스크 요인\n"
        "   - 포지셔닝 방향 (간접적 제안)\n"
        "**작성 규칙**:\n"
        "- 길이: 200~400자\n"
        "- 불확실성 표현 사용: '~할 가능성', '~로 예상됨', '~할 경우' 등\n"
        "- 시나리오별 정량적 영향 명시: '2~3% 상승', '10bp 하락' 등\n"
        "- 근거 명확히 제시: '과거 유사 사례', 'Fed Funds Futures 기준' 등\n"
        "### 문단 3: 내용 정리 및 인사이트 제공\n\n"
        "**목적**: 예정된 경제 지표 발표 일정과 시장 기대치를 바탕으로 시장 영향을 전망합니다.\n\n"
    )

    # ========================================
    # 출력 형식
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        '  "narrative": [\n'
        '    "문단1: 과거 이벤트 분석 내용...",\n'
        '    "문단2: 미래 이벤트 전망 내용..."\n'
        "  ]\n"
        "}\n"
        "```\n\n"
        "**중요**: \n"
        "- 정확히 2개 문단만 작성\n"
        "- 각 문단은 하나의 문자열로 작성 (줄바꿈 없음)\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


def build_crypto_narrative_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    num_paragraphs: int = 2,
    economic_events: Sequence[Any] | None = None,
    key_points: list[str] | None = None,
) -> str:
    """
    Crypto 내러티브 프롬프트를 생성합니다.

    암호화폐 시장 전체를 포괄합니다:
    - 온체인 동향: 블록체인 기술, DeFi, NFT, 프로토콜 업데이트
    - 제도권 동향: ETF, 기관 투자, 규제, 메인스트림 채택

    항상 2개 문단으로 고정: 문단1(과거 이벤트 분석), 문단2(미래 트렌드 전망)

    Args:
        keywords: Crypto 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        num_paragraphs: 생성할 문단 수 (기본값 2, 고정)
        economic_events: Economic Calendar 이벤트 리스트 (선택)
        key_points: Key Points 리스트 (2단계 LLM 호출 시 사용, 선택)
            - 제공 시 내러티브는 이 Key Points를 반드시 반영해야 함

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    # 공통 부분 재사용
    system_prompt, user_prompt_base = _build_crypto_prompt_base(
        keywords, source_highlights, economic_events
    )

    # 문단 구성 안내 추가
    system_prompt += (
        "\n\n"
        "**문단 구성**:\n"
        "- 문단1: 과거 이벤트 분석 (발생한 온체인/제도권 이벤트와 시장 반응)\n"
        "- 문단2: 미래 트렌드 전망 (예정된 업데이트/규제 변화와 시장 기대)"
    )

    user_prompt_parts = [user_prompt_base]

    # Key Points가 제공된 경우 프롬프트에 추가
    if key_points:
        key_points_text = "\n".join(f"- {p}" for p in key_points)
        user_prompt_parts.append(
            "---\n\n"
            "## Key Points (필수 반영)\n\n"
            "아래 Key Points는 반드시 내러티브에 반영되어야 합니다:\n\n"
            f"{key_points_text}\n\n"
            "**중요**: 위 Key Points의 모든 내용을 내러티브에 포함하세요. "
            "Key Points에 있는 정량적 데이터와 인사이트를 누락하지 마세요.\n\n"
        )

    # ========================================
    # 문단별 작성 가이드 (Narrative 전용)
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 작성 가이드\n\n"
        "**반드시 2개 문단으로 작성**하세요. 각 문단의 구성은 다음과 같습니다:\n\n"
        "### 문단 1: 과거 이벤트 분석 (Past Analysis)\n\n"
        "**목적**: 발생한 암호화폐 시장 이벤트와 시장 반응을 분석합니다.\n\n"
        "**필수 포함 요소**:\n"
        "1. 핵심 성장/하락 동력 분석\n"
        "   - 온체인 트렌드: L2 경쟁, DeFi TVL 변동, 프로토콜 업데이트\n"
        "   - 제도권 동향: ETF 자금 흐름, 기관 투자, 규제 변화\n"
        "   - 정량적 근거 필수: TVL(%), 거래량, ETF 순유입/유출 금액\n"
        '   - 예: "비트코인 현물 ETF에서 3억 달러 순유입, Arbitrum TVL 15% 증가"\n\n'
        "2. 주요 이벤트 요약\n"
        "   - 온체인: 프로토콜 업데이트, 에어드롭, 메인넷 런칭, 해킹 사고\n"
        "   - 제도권: ETF 승인/거부, SEC 소송, 기관 투자 발표, 규제 법안\n"
        "   - 각 이벤트가 BTC/ETH 등 주요 코인에 미친 영향\n"
        '   - 예: "SEC의 이더리움 ETF 승인으로 ETH 10% 급등"\n\n'
        "3. 시장 반응 분석\n"
        "   - 가격 변동: 주요 코인 및 알트코인의 등락률\n"
        "   - 거래량 변화: 온체인 거래량, CEX/DEX 거래량\n"
        "   - 자금 흐름: ETF 자금 흐름, DeFi TVL 변동, 거래소 입출금\n"
        '   - 예: "비트코인 $95,000 돌파, 24시간 거래량 400억 달러"\n\n'
        "4. 인과관계 분석\n"
        "   - 온체인: 업그레이드 → TVL 증가 → 토큰 가격 상승\n"
        "   - 제도권: ETF 승인 → 기관 자금 유입 → 시장 상승\n"
        "   - 규제: SEC 소송 → 불확실성 증가 → 매도 압력\n\n"
        "5. 긍정/부정 요인 종합 평가\n"
        "   - 긍정 요인: ETF 승인, TVL 급증, 기관 진입, 프로토콜 성공\n"
        "   - 부정 요인: 규제 압박, 해킹, ETF 자금 유출, 기술적 실패\n"
        "   - 최종 평가: 어느 요인이 우세했는지 명시\n\n"
        "**작성 규칙**:\n"
        "- 길이: 200~400자\n"
        "- 정량적 데이터 최소 3개 이상 포함\n"
        "- 인과관계 명확: A → B → C 형태로 전달 경로 서술\n"
        "- 온체인 + 제도권 양쪽 동향을 균형있게 다룰 것\n\n"
        "---\n\n"
        "### 문단 2: 미래 트렌드 전망 (Future Outlook)\n\n"
        "**목적**: 예정된 이벤트와 시장 기대치를 분석합니다.\n\n"
        "**필수 포함 요소**:\n"
        "1. 예정된 주요 이벤트\n"
        "   - 온체인: 프로토콜 업그레이드, 토큰 언락, 에어드롭, 메인넷 출시\n"
        "   - 제도권: ETF 결정 일정, 규제 청문회, 기관 투자 발표 예정\n"
        '   - 예: "이더리움 Pectra 업그레이드 예정, SEC 스테이킹 ETF 심사 중"\n\n'
        "2. 시장 기대치 및 컨센서스\n"
        "   - 주요 분석가 전망 (온체인 애널리스트, 기관 리서치)\n"
        "   - 커뮤니티 기대 수준\n"
        '   - 예: "시장은 스팟 ETH ETF 승인으로 20억 달러 자금 유입 기대"\n\n'
        "3. 시나리오별 시장 영향 예측\n"
        "   - 기대치 충족 시: 예상되는 가격/TVL 변화\n"
        "   - 기대치 상회 시: 긍정적 시나리오\n"
        "   - 기대치 하회 시: 부정적 시나리오 (규제 불확실성, 기술적 실패)\n"
        '   - 예: "ETF 승인 시 BTC $100K 도달 가능, 거부 시 $80K 지지선 테스트"\n\n'
        "4. 투자 시사점\n"
        "   - 주목해야 할 테마/섹터 (L2, RWA, AI 크립토, ETF 수혜주)\n"
        "   - 리스크 요인 (규제, 기술적 리스크, 유동성)\n"
        "   - 포지셔닝 방향 (간접적 제안)\n\n"
        "**작성 규칙**:\n"
        "- 길이: 200~400자\n"
        "- 불확실성 표현 사용: '~할 가능성', '~로 예상됨'\n"
        "- 시나리오별 정량적 영향 명시\n"
        "- 온체인 + 제도권 양쪽 전망을 균형있게 다룰 것\n\n"
    )

    # ========================================
    # 출력 형식
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        '  "narrative": [\n'
        '    "문단1: 과거 이벤트 분석 내용...",\n'
        '    "문단2: 미래 트렌드 전망 내용..."\n'
        "  ]\n"
        "}\n"
        "```\n\n"
        "**중요**: \n"
        "- 정확히 2개 문단만 작성\n"
        "- 각 문단은 하나의 문자열로 작성 (줄바꿈 없음)\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


# 하위 호환성을 위한 별칭 (deprecated)
def build_crypto_native_narrative_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    num_paragraphs: int = 2,
    economic_events: Sequence[Any] | None = None,
    key_points: list[str] | None = None,
) -> str:
    """Deprecated: build_crypto_narrative_prompt를 사용하세요."""
    return build_crypto_narrative_prompt(
        keywords, source_highlights, num_paragraphs, economic_events, key_points
    )


# 하위 호환성을 위한 별칭 (deprecated)
def build_crypto_macro_narrative_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    num_paragraphs: int = 2,
    economic_events: Sequence[Any] | None = None,
    key_points: list[str] | None = None,
) -> str:
    """Deprecated: build_crypto_narrative_prompt를 사용하세요."""
    return build_crypto_narrative_prompt(
        keywords, source_highlights, num_paragraphs, economic_events, key_points
    )


def build_integrated_narrative_prompt(
    macro_narrative: list[str],
    crypto_narrative: list[str],
    all_keywords: list[dict[str, Any]],
    num_paragraphs: int = 3,
    economic_events: Sequence[Any] | None = None,
    key_points: list[str] | None = None,
    # 하위 호환성을 위한 deprecated 파라미터
    crypto_native_narrative: list[str] = None,
    crypto_macro_narrative: list[str] = None,
) -> str:
    """
    통합 내러티브 프롬프트를 생성합니다.

    Macro와 Crypto 내러티브를 종합하여 전체 시장 그림을 그립니다.

    Args:
        macro_narrative: Macro 내러티브 문단 리스트
        crypto_narrative: Crypto 내러티브 문단 리스트
        all_keywords: 전체 키워드 리스트
        num_paragraphs: 생성할 문단 수
        economic_events: Economic Calendar 이벤트 (선택사항)
        key_points: Key Points 리스트 (2단계 LLM 호출 시 사용, 선택)
            - 제공 시 내러티브는 이 Key Points를 반드시 반영해야 함
        crypto_native_narrative: (deprecated) 하위 호환성용
        crypto_macro_narrative: (deprecated) 하위 호환성용

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    # 하위 호환성: 기존 3-카테고리 방식 호출 처리
    if crypto_native_narrative is not None or crypto_macro_narrative is not None:
        # 기존 방식으로 호출됨 - crypto_native + crypto_macro를 합쳐서 crypto로 사용
        combined_crypto = []
        if crypto_native_narrative:
            combined_crypto.extend(crypto_native_narrative)
        if crypto_macro_narrative:
            combined_crypto.extend(crypto_macro_narrative)
        crypto_narrative = combined_crypto if combined_crypto else crypto_narrative

    # 공통 부분 재사용
    system_prompt, user_prompt_base = _build_integrated_prompt_base(
        macro_narrative, crypto_narrative, all_keywords, economic_events
    )

    user_prompt_parts = [user_prompt_base]

    # Key Points가 제공된 경우 프롬프트에 추가
    if key_points:
        key_points_text = "\n".join(f"- {p}" for p in key_points)
        user_prompt_parts.append(
            "---\n\n"
            "## Key Points (필수 반영)\n\n"
            "아래 Key Points는 반드시 통합 내러티브에 반영되어야 합니다:\n\n"
            f"{key_points_text}\n\n"
            "**중요**: 위 Key Points의 모든 내용을 내러티브에 포함하세요. "
            "특히 Macro-Crypto 연결고리와 정량적 데이터를 누락하지 마세요.\n\n"
        )

    # ========================================
    # 작성 가이드 (Narrative 전용)
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 작성 가이드\n\n"
        f"**반드시 {num_paragraphs}개 문단으로 작성**하세요.\n\n"
        "### 작성 규칙\n"
        "- 각 문단 길이: 150~250자\n"
    )

    # ========================================
    # 출력 형식
    # ========================================
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        f'  "narrative": ["문단1", "문단2", "문단3"{", ..." if num_paragraphs > 3 else ""}]\n'
        "}\n"
        "```\n\n"
        "**중요**: \n"
        f"- 정확히 {num_paragraphs}개 문단만 작성\n"
        "- 각 문단은 하나의 문자열로 작성 (줄바꿈 없음)\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


def parse_narrative_response(response_text: str, category: str) -> list[str]:
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
    result = parse_json_from_llm_response(
        response_text, context=f"{category} Narrative 응답"
    )

    if "narrative" not in result:
        raise ValueError(f"{category} Narrative 응답에 'narrative' 필드가 없습니다.")

    narrative = result.get("narrative")
    if not isinstance(narrative, list) or not narrative:
        raise ValueError(f"'{category} narrative'는 비어있지 않은 리스트여야 합니다.")

    normalized_narrative = [
        str(paragraph).strip() for paragraph in narrative if str(paragraph).strip()
    ]
    if not normalized_narrative:
        raise ValueError(f"'{category} narrative'에 유효한 문단이 없습니다.")

    return normalized_narrative


def format_economic_calendar(economic_events: Sequence[Any] | None = None) -> str:
    """
    Economic Calendar 이벤트를 프롬프트용 텍스트로 포맷팅합니다.

    Args:
        economic_events: Economic Calendar 이벤트 리스트 (CollectedItem 형식)

    Returns:
        포맷팅된 텍스트 문자열
    """
    if not economic_events:
        return ""

    from datetime import datetime, timezone

    # 과거/미래 분리
    now = datetime.now(timezone.utc)
    past_events = []
    future_events = []

    for event in economic_events:
        timestamp = getattr(event, "timestamp", None)
        if timestamp:
            if timestamp <= now:
                past_events.append(event)
            else:
                future_events.append(event)

    lines = []

    # 발표된 경제 지표
    if past_events:
        lines.append("**[발표된 경제 지표]**")
        for event in past_events[:10]:  # 최대 10개
            text = getattr(event, "text", "")
            if text:
                lines.append(f"▪ {text}")

    # 예정된 경제 지표
    if future_events:
        if lines:  # 이미 past_events가 있으면 줄바꿈 추가
            lines.append("")
        lines.append("**[예정된 경제 지표 발표 일정]**")
        for event in future_events[:10]:  # 최대 10개
            text = getattr(event, "text", "")
            if text:
                lines.append(f"▪ {text}")

    return "\n".join(lines) if lines else ""


def format_economic_calendar_split(
    economic_events: Sequence[Any] | None = None,
) -> tuple[str, str]:
    """
    Economic Calendar 이벤트를 과거/미래로 분리하여 포맷팅합니다.

    Args:
        economic_events: Economic Calendar 이벤트 리스트 (CollectedItem 형식)

    Returns:
        (past_events_text, future_events_text) 튜플
    """
    if not economic_events:
        return "", ""

    from datetime import datetime, timezone

    # 과거/미래 분리
    now = datetime.now(timezone.utc)
    past_events = []
    future_events = []

    for event in economic_events:
        timestamp = getattr(event, "timestamp", None)
        if timestamp:
            if timestamp <= now:
                past_events.append(event)
            else:
                future_events.append(event)

    # 발표된 경제 지표 포맷팅
    past_lines = []
    if past_events:
        for event in past_events[:10]:  # 최대 10개
            text = getattr(event, "text", "")
            if text:
                past_lines.append(f"▪ {text}")

    # 예정된 경제 지표 포맷팅
    future_lines = []
    if future_events:
        for event in future_events[:10]:  # 최대 10개
            text = getattr(event, "text", "")
            if text:
                future_lines.append(f"▪ {text}")

    past_text = "\n".join(past_lines) if past_lines else ""
    future_text = "\n".join(future_lines) if future_lines else ""

    return past_text, future_text


# ============================================================================
# Key Points 생성 프롬프트 (2단계 LLM 호출 방식 - Phase 3)
# ============================================================================


def build_macro_keypoints_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> str:
    """
    Macro Key Points 생성 프롬프트를 구성합니다.

    1단계 LLM 호출에서 사용되며, 핵심 포인트와 소스 매핑을 생성합니다.
    _build_macro_prompt_base()를 재사용하여 공통 부분을 활용합니다.

    Args:
        keywords: Macro 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        economic_events: Economic Calendar 이벤트 리스트 (선택)

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    # 공통 부분 재사용
    system_prompt, user_prompt_base = _build_macro_prompt_base(
        keywords, source_highlights, economic_events
    )

    # Key Points 전용 시스템 프롬프트 추가
    system_prompt += (
        "\n\n"
        "**목표**: 주어진 데이터에서 핵심 포인트(Key Points)를 추출합니다.\n"
        "Key Points는 이후 내러티브 생성의 기반이 되므로, 정확하고 정량적인 정보를 포함해야 합니다."
    )

    user_prompt_parts = [user_prompt_base]

    # Key Points 작성 가이드
    user_prompt_parts.append(
        "---\n\n"
        "## Key Points 작성 가이드\n\n"
        "### Key Points란?\n"
        "- 내러티브 작성의 기반이 되는 핵심 정보입니다\n"
        "- 각 포인트는 독립적으로 의미를 전달해야 합니다\n"
        "- 정량적 데이터를 반드시 포함하세요 (%, bp, 지수, 금액 등)\n\n"
        "### 작성 규칙\n"
        "- **개수**: 5~20개 (데이터 양에 따라 유동적으로 결정)\n"
        "- **중요도순 정렬**: 가장 중요한 포인트를 먼저 나열\n"
        "- **정량적 데이터 필수**: 각 포인트에 최소 1개 이상의 수치 포함\n"
        "- **소스 매핑**: 각 포인트가 어느 소스에서 추출되었는지 명시\n"
        "- **간결성**: 각 포인트는 1~2문장으로 구성\n\n"
        "### 포함해야 할 내용\n"
        "1. 주요 경제 지표 발표 및 결과\n"
        "2. 중앙은행 정책 변화 및 발언\n"
        "3. 금리/주식/환율/상품 시장 반응\n"
        "4. 향후 예정된 주요 이벤트\n"
        "5. 시장 간 상호작용 및 인과관계\n\n"
    )

    # 출력 형식
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        '  "key_points": [\n'
        '    "미국 11월 CPI는 2.7%(예상 2.6%)로 예상을 상회하며 인플레이션 재가속 우려 부각",\n'
        '    "10년물 국채 수익률 4.2%로 10bp 상승, 금리 인하 기대 후퇴",\n'
        '    "Fed 금리 인하 확률 CME FedWatch 기준 65%로 전주 대비 10%p 하락",\n'
        "    ...\n"
        "  ],\n"
        '  "source_mapping": {\n'
        '    "0": [1, 5, 12],\n'
        '    "1": [3, 8],\n'
        '    "2": [2, 7, 15],\n'
        "    ...\n"
        "  }\n"
        "}\n"
        "```\n\n"
        "**중요**:\n"
        "- key_points: 5~20개의 핵심 포인트 (중요도순)\n"
        "- source_mapping: 각 포인트 인덱스 → 관련 소스 ID 리스트\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


def build_crypto_keypoints_prompt(
    keywords: list[dict[str, Any]],
    source_highlights: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> str:
    """
    Crypto Key Points 생성 프롬프트를 구성합니다.

    1단계 LLM 호출에서 사용되며, 핵심 포인트와 소스 매핑을 생성합니다.
    _build_crypto_prompt_base()를 재사용하여 공통 부분을 활용합니다.

    Args:
        keywords: Crypto 카테고리 키워드 리스트
        source_highlights: 주요 출처 하이라이트
        economic_events: Economic Calendar 이벤트 리스트 (선택)

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    # 공통 부분 재사용
    system_prompt, user_prompt_base = _build_crypto_prompt_base(
        keywords, source_highlights, economic_events
    )

    # Key Points 전용 시스템 프롬프트 추가
    system_prompt += (
        "\n\n"
        "**목표**: 주어진 데이터에서 핵심 포인트(Key Points)를 추출합니다.\n"
        "Key Points는 이후 내러티브 생성의 기반이 되므로, 정확하고 정량적인 정보를 포함해야 합니다."
    )

    user_prompt_parts = [user_prompt_base]

    # Key Points 작성 가이드
    user_prompt_parts.append(
        "---\n\n"
        "## Key Points 작성 가이드\n\n"
        "### Key Points란?\n"
        "- 내러티브 작성의 기반이 되는 핵심 정보입니다\n"
        "- 각 포인트는 독립적으로 의미를 전달해야 합니다\n"
        "- 정량적 데이터를 반드시 포함하세요 (TVL, %, 자금 흐름, 거래량 등)\n\n"
        "### 작성 규칙\n"
        "- **개수**: 5~20개 (데이터 양에 따라 유동적으로 결정)\n"
        "- **중요도순 정렬**: 가장 중요한 포인트를 먼저 나열\n"
        "- **정량적 데이터 필수**: 각 포인트에 최소 1개 이상의 수치 포함\n"
        "- **소스 매핑**: 각 포인트가 어느 소스에서 추출되었는지 명시\n"
        "- **간결성**: 각 포인트는 1~2문장으로 구성\n\n"
        "### 포함해야 할 내용 (온체인 + 제도권 균형)\n"
        "1. **온체인 동향**: TVL 변동, 프로토콜 업데이트, DeFi 트렌드\n"
        "2. **제도권 동향**: ETF 자금 흐름, 기관 투자, 규제 변화\n"
        "3. **가격 및 거래량**: 주요 코인 가격 변동, 거래량 변화\n"
        "4. **향후 이벤트**: 예정된 업그레이드, 토큰 언락, 규제 일정\n"
        "5. **시장 심리**: 공포/탐욕 지수, 소셜 센티먼트\n\n"
    )

    # 출력 형식
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        '  "key_points": [\n'
        '    "비트코인 현물 ETF에서 3억 달러 순유입, 기관 매수세 지속",\n'
        '    "이더리움 Pectra 업그레이드 테스트넷 성공, 메인넷 Q1 적용 예정",\n'
        '    "Arbitrum TVL 150억 달러로 15% 증가, L2 경쟁 심화",\n'
        "    ...\n"
        "  ],\n"
        '  "source_mapping": {\n'
        '    "0": [2, 6, 11],\n'
        '    "1": [4, 9],\n'
        '    "2": [1, 5, 13],\n'
        "    ...\n"
        "  }\n"
        "}\n"
        "```\n\n"
        "**중요**:\n"
        "- key_points: 5~20개의 핵심 포인트 (중요도순)\n"
        "- source_mapping: 각 포인트 인덱스 → 관련 소스 ID 리스트\n"
        "- 온체인과 제도권 동향을 균형있게 포함\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


def build_integrated_keypoints_prompt(
    macro_key_points: list[str],
    crypto_key_points: list[str],
    all_keywords: list[dict[str, Any]],
    economic_events: Sequence[Any] | None = None,
) -> str:
    """
    통합 Key Points 생성 프롬프트를 구성합니다.

    Macro와 Crypto의 Key Points를 입력받아 통합된 Key Points를 생성합니다.
    두 영역 간의 연결고리를 찾아 새로운 인사이트를 도출합니다.

    Args:
        macro_key_points: Macro Key Points 리스트
        crypto_key_points: Crypto Key Points 리스트
        all_keywords: 전체 키워드 리스트
        economic_events: Economic Calendar 이벤트 (선택)

    Returns:
        Gemini API 호출용 프롬프트 문자열
    """
    keywords_json = json.dumps(
        all_keywords[:15], ensure_ascii=False, indent=2
    )  # 상위 15개만

    system_prompt = (
        "당신은 디지털 자산 시장 전체를 조망하는 수석 분석가입니다.\n"
        "거시경제와 암호화폐 시장의 연결고리를 찾아 통합적인 인사이트를 도출하세요.\n"
        "\n"
        "**목표**: Macro와 Crypto Key Points를 종합하여 통합 Key Points를 생성합니다.\n"
        "단순 요약이 아닌, 두 영역 간의 연결고리와 새로운 인사이트를 찾아야 합니다."
    )

    macro_text = "\n".join(f"- {p}" for p in (macro_key_points or []))
    crypto_text = "\n".join(f"- {p}" for p in (crypto_key_points or []))

    # Economic Calendar 포맷팅
    economic_calendar_text = format_economic_calendar(economic_events)

    user_prompt_parts = [
        "## 제공된 Key Points\n\n"
        "### Macro (거시경제) Key Points\n"
        f"{macro_text if macro_text else '(내용 없음)'}\n\n"
        "### Crypto (암호화폐) Key Points\n"
        f"{crypto_text if crypto_text else '(내용 없음)'}\n\n"
        f"### 주요 키워드\n{keywords_json}\n\n"
    ]

    # Economic Calendar 추가 (있을 경우)
    if economic_calendar_text:
        user_prompt_parts.append(f"{economic_calendar_text}\n\n")

    # Key Points 작성 가이드
    user_prompt_parts.append(
        "---\n\n"
        "## 통합 Key Points 작성 가이드\n\n"
        "### 통합 Key Points의 목적\n"
        "- 단순 합치기가 아닌 **두 영역 간의 연결고리** 도출\n"
        "- 거시경제 → 암호화폐로의 **전달 경로** 명확화\n"
        "- 투자자 관점에서 **실행 가능한 시사점** 제시\n\n"
        "### 작성 규칙\n"
        "- **개수**: 5~15개 (핵심만 선별)\n"
        "- **중요도순 정렬**: 가장 중요한 포인트를 먼저 나열\n"
        "- **연결고리 강조**: Macro-Crypto 간 인과관계 명시\n"
        "- **정량적 데이터 포함**: 각 포인트에 수치 포함\n\n"
        "### 필수 포함 요소\n"
        "1. **Macro-Crypto 연결고리**\n"
        '   - 예: "금리 인하 기대감 → 위험자산 선호 → ETF 자금 유입 → BTC 상승"\n'
        "2. **종합 시장 방향성**\n"
        "   - 긍정/부정 요인의 상대적 힘 평가\n"
        "3. **투자 시사점**\n"
        "   - 주목할 테마/섹터, 리스크 요인\n\n"
    )

    # 출력 형식
    user_prompt_parts.append(
        "---\n\n"
        "## 출력 형식\n\n"
        "반드시 다음 JSON 형식으로만 출력하세요:\n\n"
        "```json\n"
        "{\n"
        '  "key_points": [\n'
        '    "Fed 금리 인하 기대 후퇴로 위험자산 선호 약화, BTC ETF 유입 둔화 예상",\n'
        '    "달러 강세 지속 시 BTC/USD 하방 압력 증가, 지지선 $90K 주목",\n'
        '    "그러나 온체인 활동 증가와 기관 매수세는 긍정적, 중기 상승 관점 유지",\n'
        "    ...\n"
        "  ],\n"
        '  "source_mapping": {\n'
        '    "0": ["macro_0", "macro_2", "crypto_1"],\n'
        '    "1": ["macro_1", "crypto_3"],\n'
        '    "2": ["crypto_0", "crypto_2", "crypto_5"],\n'
        "    ...\n"
        "  }\n"
        "}\n"
        "```\n\n"
        "**중요**:\n"
        "- key_points: 5~15개의 통합 핵심 포인트 (중요도순)\n"
        '- source_mapping: 각 포인트가 참조한 원본 Key Point ("macro_인덱스" 또는 "crypto_인덱스")\n'
        "- Macro-Crypto 연결고리를 반드시 포함\n"
        "- JSON 형식 외 다른 텍스트 출력 금지\n"
    )

    user_prompt = "".join(user_prompt_parts)
    return f"{system_prompt}\n\n{user_prompt}"


def parse_keypoints_response(
    response_text: str, category: str = "Key Points"
) -> dict[str, Any]:
    """
    Key Points 응답을 파싱하고 유효성을 검증합니다.

    Args:
        response_text: LLM 응답 텍스트
        category: 카테고리 이름 (에러 메시지용)

    Returns:
        파싱된 Key Points 딕셔너리
        {
            "key_points": ["포인트1", "포인트2", ...],
            "source_mapping": {"0": [1, 2], "1": [3], ...}
        }

    Raises:
        ValueError: 응답 구조가 예상과 다르거나 유효성 검증 실패 시
    """
    result = parse_json_from_llm_response(
        response_text, context=f"{category} 응답"
    )

    # key_points 필드 검증
    if "key_points" not in result:
        raise ValueError(f"{category} 응답에 'key_points' 필드가 없습니다.")

    key_points = result.get("key_points")
    if not isinstance(key_points, list):
        raise ValueError(f"'{category} key_points'는 리스트여야 합니다.")

    # 빈 문자열 제거 및 정규화
    normalized_key_points = [
        str(point).strip() for point in key_points if str(point).strip()
    ]

    if not normalized_key_points:
        raise ValueError(f"'{category} key_points'에 유효한 포인트가 없습니다.")

    # 개수 검증 (5~20개 범위, 경고만 표시)
    point_count = len(normalized_key_points)
    if point_count < 5:
        logger.warning(
            f"[parse_keypoints_response] {category}: Key Points 개수가 최소 권장(5개) 미만입니다: {point_count}개"
        )
    elif point_count > 20:
        logger.warning(
            f"[parse_keypoints_response] {category}: Key Points 개수가 최대 권장(20개) 초과입니다: {point_count}개"
        )

    # source_mapping 필드 검증 (선택적)
    source_mapping_raw = result.get("source_mapping", {})
    if not isinstance(source_mapping_raw, dict):
        logger.warning(
            f"[parse_keypoints_response] {category}: 'source_mapping'이 딕셔너리가 아닙니다. 빈 딕셔너리로 대체합니다."
        )
        source_mapping_raw = {}

    # source_mapping 정규화
    source_mapping: dict[str, list[Any]] = {}
    for key, value in source_mapping_raw.items():
        str_key = str(key)
        if isinstance(value, list):
            source_mapping[str_key] = value
        else:
            logger.warning(
                f"[parse_keypoints_response] {category}: source_mapping['{key}']가 리스트가 아닙니다: {type(value)}"
            )
            source_mapping[str_key] = []

    return {
        "key_points": normalized_key_points,
        "source_mapping": source_mapping,
    }

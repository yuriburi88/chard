"""
KeywordExtractorNode 구현

LLM 파이프라인 문서의 섹션 3.2를 참조하여 구현되었습니다.
각 청크의 텍스트를 분석하여 키워드를 추출합니다.
"""

import asyncio
import logging
from typing import Any

from src.workflows.id_generator import get_id_generator
from src.workflows.llm_client import GeminiClient
from src.workflows.prompts import (
    build_keyword_extraction_prompt,
    parse_keyword_extraction_response,
)
from src.workflows.state import AnalysisState


logger = logging.getLogger(__name__)


async def keyword_extractor_node(state: AnalysisState) -> AnalysisState:
    """
    청크를 분석하여 키워드 추출

    LLM 파이프라인 문서의 섹션 3.2를 참조하여 구현되었습니다.

    처리 단계:
    1. state에서 chunks 추출
    2. 설정에서 병렬 처리 동시성 옵션 확인
    3. 각 청크에 대해 병렬로 키워드 추출 수행 (동시 실행 수 제한 가능)
    4. 추출된 키워드를 통합하여 state 업데이트

    병렬 처리 옵션:
    - parallel_concurrency=0: 무제한 병렬 처리 (asyncio.gather, 빠르지만 rate limit 위험)
    - parallel_concurrency=N (N>0): 최대 N개 청크를 동시에 처리 (Semaphore 사용, 안정성과 성능의 균형)

    Args:
        state: LangGraph 상태 (청크 리스트 포함)

    Returns:
        업데이트된 상태 (추출된 키워드 포함)
    """
    logger.info("[KeywordExtractorNode] 키워드 추출 시작")

    # 1. 입력 데이터 확인
    chunks = state.get("chunks", [])
    if not chunks:
        logger.warning("[KeywordExtractorNode] chunks가 비어있습니다.")
        return {
            **state,
            "extracted_keywords": [],
            "errors": state.get("errors", [])
            + ["KeywordExtractorNode: chunks가 비어있습니다."],
        }

    logger.info(f"[KeywordExtractorNode] 처리할 청크 수: {len(chunks)}개")

    # 2. 설정에서 LLM 옵션 및 병렬 처리 동시성 옵션 확인
    config = state.get("config", {})
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "gemini-2.0-flash-exp")
    temperature = llm_config.get("temperature", 0.1)
    max_tokens = llm_config.get("max_tokens", 4000)
    parallel_concurrency = llm_config.get("parallel_concurrency", 5)

    # 동시성 제한 해석: 0이면 무제한, 양수면 해당 수만큼 제한
    if parallel_concurrency == 0:
        concurrency_mode = "무제한"
    else:
        concurrency_mode = f"최대 {parallel_concurrency}개 동시 실행"

    logger.info(
        f"[KeywordExtractorNode] LLM 설정: "
        f"모델={model}, temperature={temperature}, max_tokens={max_tokens}, "
        f"병렬 처리 동시성={concurrency_mode}"
    )

    # 3. GeminiClient 초기화
    try:
        gemini_client = GeminiClient(
            model=model, temperature=temperature, max_tokens=max_tokens
        )
    except Exception as e:
        error_msg = f"KeywordExtractorNode: GeminiClient 초기화 실패 - {str(e)}"
        logger.error(f"[KeywordExtractorNode] {error_msg}", exc_info=True)
        return {
            **state,
            "extracted_keywords": [],
            "errors": state.get("errors", []) + [error_msg],
        }

    # 4. Economic Calendar 데이터 가져오기
    raw_records = state.get("raw_records", [])
    economic_events = [
        record for record in raw_records if record.get("source") == "economic_calendar"
    ]

    if economic_events:
        logger.info(
            f"[KeywordExtractorNode] Economic Calendar 이벤트 {len(economic_events)}개를 "
            f"Macro 키워드 추출에 활용합니다."
        )
    else:
        logger.debug("[KeywordExtractorNode] Economic Calendar 데이터가 없습니다.")

    # 5. ID 생성기 초기화 및 ID 매핑 준비
    id_generator = get_id_generator()

    # 각 청크의 레코드에 ID 부여 및 매핑 등록
    chunks_with_ids: list[list[dict[str, Any]]] = []
    for chunk in chunks:
        chunk_with_ids = []
        for record in chunk:
            record_id = id_generator.generate_id()
            record_with_id = {**record, "id": record_id}
            id_generator.register_record(record_id, record)
            chunk_with_ids.append(record_with_id)
        chunks_with_ids.append(chunk_with_ids)

    logger.debug(
        f"[KeywordExtractorNode] ID 매핑 완료: 총 레코드 수={len(id_generator.get_all_mappings())}개"
    )

    # 6. 각 청크에 대해 키워드 추출 수행 (병렬 처리, 동시성 제한 가능)
    extracted_keywords: list[dict[str, Any]] = []
    errors: list[str] = state.get("errors", [])

    try:
        if parallel_concurrency == 0:
            # 무제한 병렬 처리: 모든 청크를 동시에 처리
            logger.info("[KeywordExtractorNode] 무제한 병렬 처리 모드로 실행")
            tasks = [
                extract_keywords_from_chunk(
                    chunk_with_ids,
                    chunk_id=i,
                    gemini_client=gemini_client,
                    economic_events=economic_events,
                )
                for i, chunk_with_ids in enumerate(chunks_with_ids)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # 제한된 병렬 처리: Semaphore를 사용하여 동시 실행 수 제한
            logger.info(
                f"[KeywordExtractorNode] 제한된 병렬 처리 모드로 실행 (최대 {parallel_concurrency}개 동시 실행)"
            )
            semaphore = asyncio.Semaphore(parallel_concurrency)

            async def extract_with_semaphore(
                chunk_with_ids: list[dict[str, Any]], chunk_id: int
            ) -> dict[str, Any]:
                """Semaphore를 사용하여 동시 실행 수를 제한하는 래퍼 함수"""
                async with semaphore:
                    return await extract_keywords_from_chunk(
                        chunk_with_ids,
                        chunk_id=chunk_id,
                        gemini_client=gemini_client,
                        economic_events=economic_events,
                    )

            tasks = [
                extract_with_semaphore(chunk_with_ids, chunk_id=i)
                for i, chunk_with_ids in enumerate(chunks_with_ids)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 통합
        for chunk_id, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = f"KeywordExtractorNode: 청크 {chunk_id+1} 처리 중 오류 - {str(result)}"
                logger.error(f"[KeywordExtractorNode] {error_msg}", exc_info=True)
                errors.append(error_msg)
            else:
                keywords = result.get("keywords", [])

                # 각 키워드에 chunk_id 추가 (선택적, 추적용)
                for keyword in keywords:
                    keyword["chunk_id"] = chunk_id

                extracted_keywords.extend(keywords)
                logger.debug(
                    f"[KeywordExtractorNode] 청크 {chunk_id+1}/{len(chunks)} 처리 완료: "
                    f"추출된 키워드 수={len(keywords)}개"
                )

    except Exception as e:
        error_msg = f"KeywordExtractorNode: 처리 중 오류 발생 - {str(e)}"
        logger.error(f"[KeywordExtractorNode] {error_msg}", exc_info=True)
        errors.append(error_msg)

    # 7. 통계 로깅
    concurrency_info = (
        "무제한" if parallel_concurrency == 0 else f"최대 {parallel_concurrency}개"
    )
    id_mapping_stats = id_generator.get_mapping_stats()

    # 카테고리별 키워드 수 집계
    category_counts = {
        "macro": 0,
        "crypto_native": 0,
        "crypto_macro": 0,
        "uncategorized": 0,
    }
    for kw in extracted_keywords:
        category = kw.get("category", "uncategorized")
        category_counts[category] = category_counts.get(category, 0) + 1

    logger.info(
        f"[KeywordExtractorNode] 키워드 추출 완료 (병렬 처리, {concurrency_info} 동시 실행): "
        f"전체 청크 수={len(chunks)}개, "
        f"추출된 키워드 수={len(extracted_keywords)}개, "
        f"오류 수={len(errors) - len(state.get('errors', []))}개"
    )
    logger.info(
        f"[KeywordExtractorNode] 카테고리별 키워드: "
        f"Macro={category_counts['macro']}, "
        f"Crypto Native={category_counts['crypto_native']}, "
        f"Crypto-Macro={category_counts['crypto_macro']}, "
        f"미분류={category_counts['uncategorized']}"
    )
    logger.debug(f"[KeywordExtractorNode] ID 매핑 통계: {id_mapping_stats}")

    # 8. state 업데이트 (ID 매핑 정보 포함)
    return {
        **state,
        "extracted_keywords": extracted_keywords,
        "id_mapping": id_generator.get_all_mappings(),  # 디버깅용 ID 매핑 정보
        "errors": errors,
    }


async def extract_keywords_from_chunk(
    chunk: list[dict[str, Any]],
    chunk_id: int,
    gemini_client: GeminiClient,
    economic_events: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    단일 청크에서 키워드 추출

    Args:
        chunk: ID가 부여된 정규화된 데이터 레코드 리스트 (각 레코드에 "id" 필드 포함)
        chunk_id: 청크 ID (로깅용)
        gemini_client: GeminiClient 인스턴스
        economic_events: Economic Calendar 이벤트 리스트 (선택적)

    Returns:
        키워드 추출 결과 딕셔너리
        {
            "keywords": [
                {
                    "term": "키워드",
                    "category": "macro",
                    "score": 85,
                    "evidence_ids": [1, 2, 3],
                    "sources": ["출처1", "출처2"],
                    "chunk_id": 0
                }
            ]
        }
    """
    logger.debug(
        f"[KeywordExtractorNode] 청크 {chunk_id+1} 키워드 추출 시작: 레코드 수={len(chunk)}개"
    )

    try:
        # 프롬프트 구성 (Economic Calendar 포함)
        prompt = build_keyword_extraction_prompt(chunk, economic_events=economic_events)

        logger.debug(
            f"[KeywordExtractorNode] 청크 {chunk_id+1} 프롬프트 생성 완료: "
            f"프롬프트 길이={len(prompt)}자, "
            f"Economic Calendar 이벤트={len(economic_events) if economic_events else 0}개"
        )

        # Gemini API 호출 (JSON 형식 요청)
        response_text = await gemini_client.generate_content_async(
            prompt=prompt, response_format="json"
        )

        logger.debug(
            f"[KeywordExtractorNode] 청크 {chunk_id+1} API 응답 수신: "
            f"응답 길이={len(response_text)}자"
        )

        # ID 매핑 가져오기 (검증용)
        id_generator = get_id_generator()
        id_mapping = id_generator.get_all_mappings()

        # JSON 파싱 및 검증 (ID 매핑 전달)
        result = parse_keyword_extraction_response(response_text, id_mapping=id_mapping)

        logger.info(
            f"[KeywordExtractorNode] 청크 {chunk_id+1} 키워드 추출 완료: "
            f"추출된 키워드 수={len(result.get('keywords', []))}개"
        )

        return result

    except Exception as e:
        error_msg = f"청크 {chunk_id+1}에서 키워드 추출 실패: {str(e)}"
        logger.error(f"[KeywordExtractorNode] {error_msg}", exc_info=True)
        raise Exception(error_msg) from e


# extract_keywords_parallel 함수는 제거되었습니다.
# keyword_extractor_node 함수가 enable_parallel_processing 옵션을 통해
# 병렬 처리와 순차 처리를 모두 지원합니다.

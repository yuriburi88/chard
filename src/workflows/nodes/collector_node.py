"""
CollectorNode 구현

LLM 파이프라인 문서의 섹션 3.1을 참조하여 구현되었습니다.
수집된 데이터를 LangGraph 워크플로에 전달할 수 있는 형태로 변환합니다.
"""

import logging
from typing import Dict, Any, List
from collections import Counter
from datetime import datetime

from src.workflows.state import AnalysisState
from src.preprocessor import Preprocessor, PreprocessingConfig

logger = logging.getLogger(__name__)


async def collector_node(state: AnalysisState) -> AnalysisState:
    """
    데이터를 청크로 분할하고 다음 노드로 전달
    
    LLM 파이프라인 문서의 섹션 3.1을 참조하여 구현되었습니다.
    
    처리 단계:
    1. raw_records에서 정규화된 데이터 레코드 추출
    2. config에서 청크 크기 설정 확인
    3. Preprocessor를 사용하여 청크 생성 (토큰 제한 고려, 소스별 그룹화, 시간순 정렬)
    4. 각 청크에 메타데이터 추가 (청크 ID, 소스 분포 등)
    5. state 업데이트 및 반환
    
    Args:
        state: LangGraph 상태 (수집된 원본 데이터 포함)
    
    Returns:
        업데이트된 상태 (청크 리스트 포함)
    """
    logger.info("[CollectorNode] 데이터 청크 생성 시작")
    
    # 1. 입력 데이터 확인
    raw_records = state.get("raw_records", [])
    if not raw_records:
        logger.warning("[CollectorNode] raw_records가 비어있습니다.")
        return {
            **state,
            "chunks": [],
            "chunk_count": 0,
            "errors": state.get("errors", []) + ["CollectorNode: raw_records가 비어있습니다."]
        }

    # Economic Calendar 레코드 필터링 (키워드 추출 대상에서 제외, 참고자료로만 사용)
    filtered_records = [
        record for record in raw_records
        if record.get("source") != "economic_calendar"
    ]

    ec_count = len(raw_records) - len(filtered_records)
    logger.info(
        f"[CollectorNode] 처리할 레코드 수: {len(filtered_records)}개 "
        f"(Economic Calendar {ec_count}개는 참고자료로만 사용)"
    )

    if not filtered_records:
        logger.warning("[CollectorNode] 키워드 추출 대상 레코드가 없습니다 (Economic Calendar만 존재).")
        return {
            **state,
            "chunks": [],
            "chunk_count": 0,
            "errors": state.get("errors", []) + ["CollectorNode: 키워드 추출 대상 레코드가 없습니다."]
        }

    # 2. 설정에서 청크 크기 확인
    config = state.get("config", {})
    llm_config = config.get("llm", {})
    chunk_size = llm_config.get("chunk_size", 50000)  # 기본값: 50000 토큰

    logger.info(f"[CollectorNode] 청크 크기 설정: {chunk_size} 토큰")

    # 3. Preprocessor를 사용하여 청크 생성 (Economic Calendar 제외된 레코드만 사용)
    try:
        preprocessor = Preprocessor(
            config=PreprocessingConfig(token_encoding="cl100k_base")
        )

        chunks = await preprocessor.chunk_messages(
            records=filtered_records,
            max_tokens=chunk_size
        )
        
        logger.info(f"[CollectorNode] 청크 생성 완료: {len(chunks)}개 청크")
        
    except Exception as e:
        error_msg = f"CollectorNode: 청크 생성 중 오류 발생 - {str(e)}"
        logger.error(f"[CollectorNode] {error_msg}", exc_info=True)
        return {
            **state,
            "chunks": [],
            "chunk_count": 0,
            "errors": state.get("errors", []) + [error_msg]
        }
    
    # 4. 각 청크에 메타데이터 추가
    chunks_with_metadata = []
    
    for chunk_id, chunk in enumerate(chunks):
        # 소스 분포 계산
        source_counter = Counter(record.get("source", "unknown") for record in chunk)
        source_distribution = dict(source_counter)
        
        # 타임스탬프 범위 계산
        timestamps = []
        for record in chunk:
            timestamp_str = record.get("timestamp", "")
            if timestamp_str:
                try:
                    from dateutil import parser
                    timestamp = parser.parse(timestamp_str) if isinstance(timestamp_str, str) else timestamp_str
                    timestamps.append(timestamp)
                except Exception:
                    pass
        
        min_timestamp = min(timestamps) if timestamps else None
        max_timestamp = max(timestamps) if timestamps else None
        
        # 청크 메타데이터 생성
        chunk_metadata = {
            "chunk_id": chunk_id,
            "record_count": len(chunk),
            "source_distribution": source_distribution,
            "min_timestamp": min_timestamp.isoformat() if min_timestamp else None,
            "max_timestamp": max_timestamp.isoformat() if max_timestamp else None,
        }
        
        # 각 레코드에 청크 메타데이터 추가 (선택적)
        # 실제로는 청크 레벨에서만 메타데이터를 유지하는 것이 더 효율적
        
        chunks_with_metadata.append({
            "chunk_id": chunk_id,
            "records": chunk,
            "metadata": chunk_metadata
        })
        
        logger.debug(
            f"[CollectorNode] 청크 {chunk_id+1}/{len(chunks)}: "
            f"레코드 수={len(chunk)}개, "
            f"소스 분포={source_distribution}"
        )
    
    # 5. 통계 로깅
    total_records = sum(len(chunk["records"]) for chunk in chunks_with_metadata)
    all_sources = set()
    for chunk in chunks_with_metadata:
        all_sources.update(chunk["metadata"]["source_distribution"].keys())
    
    logger.info(
        f"[CollectorNode] 청크 생성 완료: "
        f"전체 청크 수={len(chunks_with_metadata)}개, "
        f"전체 레코드 수={total_records}개, "
        f"소스 종류={sorted(all_sources)}"
    )
    
    # 6. state 업데이트
    # chunks는 원본 레코드 리스트의 리스트로 저장 (메타데이터는 별도로 관리)
    chunks_for_state = [chunk["records"] for chunk in chunks_with_metadata]
    
    return {
        **state,
        "chunks": chunks_for_state,
        "chunk_count": len(chunks_for_state),
    }


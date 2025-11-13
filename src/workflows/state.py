"""
LangGraph 워크플로 상태 정의

LLM 파이프라인 문서의 섹션 4.1을 참조하여 구현되었습니다.
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class AnalysisState(TypedDict, total=False):
    """
    LangGraph 워크플로 상태
    
    LangGraph 워크플로 전체에서 공유되는 상태 정보를 정의합니다.
    각 노드는 이 상태를 읽고 업데이트하여 다음 노드로 전달합니다.
    
    필드 설명:
    - 입력 데이터: 수집된 원본 데이터 및 설정 정보
    - 중간 처리 결과: 각 노드에서 생성된 중간 결과
    - 최종 결과: 최종 분석 결과 (키워드, 인사이트 등)
    - 메타데이터: 실행 정보 및 에러 로그
    """
    
    # 입력 데이터
    raw_records: List[Dict[str, Any]]
    """정규화된 원본 데이터 (LLM 파이프라인 문서 섹션 2.1 형식)
    
    각 레코드는 다음 형식을 따릅니다:
    {
        "source": "rss" | "telegram",
        "timestamp": "ISO 8601 형식",
        "text": "원본 텍스트",
        "meta": {
            "title": "기사 제목 또는 메시지 요약",
            "url": "기사 링크 (RSS만)",
            "channel": "텔레그램 채널명 (Telegram만)"
        }
    }
    """
    
    config: Dict[str, Any]
    """설정 정보
    
    LLM 분석 옵션, 키워드 정규화 옵션, 출력 구성 등이 포함됩니다.
    ConfigManager에서 로드된 설정을 그대로 전달합니다.
    """
    
    # 중간 처리 결과
    chunks: List[List[Dict[str, Any]]]
    """분할된 청크 리스트
    
    CollectorNode에서 생성된 청크들입니다.
    각 청크는 raw_records 형식의 레코드 리스트입니다.
    토큰 제한을 고려하여 소스별 그룹화 및 시간순 정렬이 적용됩니다.
    """
    
    chunk_count: int
    """청크 수
    
    chunks 리스트의 길이와 동일합니다.
    """
    
    extracted_keywords: List[Dict[str, Any]]
    """각 청크에서 추출된 키워드 리스트
    
    KeywordExtractorNode에서 생성된 키워드들입니다.
    각 키워드는 다음 형식을 따릅니다:
    {
        "term": "키워드",
        "score": 85,
        "evidence": ["문장1", "문장2"],
        "sources": ["출처1", "출처2"],
        "chunk_id": 0  # 선택적: 어느 청크에서 추출되었는지
    }
    """
    
    # 최종 결과
    clustered_keywords: List[Dict[str, Any]]
    """임베딩 기반 클러스터링 결과
    
    각 항목은 원본 키워드 딕셔너리에 cluster_id, cluster_members 필드가 추가된 형태입니다.
    AggregatorNode에서 1차 정규화를 완료한 뒤 저장됩니다.
    """
    
    scored_keywords: List[Dict[str, Any]]
    """클러스터링된 키워드의 스코어 재계산 결과
    
    AggregatorNode 4.5 단계에서 계산된 전체 키워드 리스트이며,
    점수 분해 정보(score_breakdown)를 포함합니다.
    """
    
    candidate_keywords: List[Dict[str, Any]]
    """LLM 검증을 위해 선택된 상위 후보 키워드 리스트
    
    AggregatorNode 4.6 단계에서 사용할 상위 2N개 키워드를 저장합니다.
    """
    
    aggregated_keywords: List[Dict[str, Any]]
    """통합된 키워드 리스트
    
    AggregatorNode에서 생성된 최종 키워드들입니다.
    임베딩 기반 클러스터링 및 LLM 검증을 거쳐 정규화되었습니다.
    각 키워드는 다음 형식을 따릅니다:
    {
        "term": "대표 키워드",
        "original_variants": ["원본1", "원본2", "원본3"],  # 원본 키워드 변형들
        "score": 92,
        "evidence": ["문장1", "문장2", "문장3"],
        "sources": ["출처1", "출처2"],
        "occurrence_count": 15  # 출현 횟수
    }
    """
    
    scoring_summary: Dict[str, Any]
    """AggregatorNode에서 계산된 통계 정보
    
    추출/클러스터/스코어링/후보/최종 키워드 수 등을 포함하는 요약 정보입니다.
    """
    
    insights: Dict[str, Any]
    """내러티브 요약 및 거래 인사이트
    
    InsightNode에서 생성된 인사이트입니다.
    다음 형식을 따릅니다:
    {
        "narrative_summary": [
            "문단1",
            "문단2",
            "문단3"
        ],
        "trading_insights": {
            "opportunities": ["인사이트1", "인사이트2"],
            "risks": ["위험1", "위험2"],
            "market_sentiment": "긍정적/중립적/부정적"
        },
        "key_sources": [
            {
                "title": "기사 제목 또는 메시지 요약",
                "url": "링크 (RSS만)",
                "relevance": "관련 키워드"
            }
        ]
    }
    """
    
    # 메타데이터
    execution_time: float
    """실행 시간 (초)
    
    워크플로 시작부터 종료까지의 경과 시간입니다.
    """
    
    errors: List[str]
    """에러 목록
    
    워크플로 실행 중 발생한 에러 메시지들이 누적됩니다.
    각 노드에서 발생한 에러는 이 리스트에 추가됩니다.
    """
    
    start_time: Optional[datetime]
    """워크플로 시작 시각
    
    워크플로 실행 시작 시각을 기록합니다.
    """
    
    end_time: Optional[datetime]
    """워크플로 종료 시각
    
    워크플로 실행 종료 시각을 기록합니다.
    """


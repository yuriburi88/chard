"""
LangGraph 워크플로 파이프라인

LLM 파이프라인 문서의 섹션 4.2를 참조하여 구현되었습니다.
LangGraph를 사용하여 키워드 분석 파이프라인을 노드 기반으로 모델링합니다.

에러 핸들링 전략:
- 각 노드는 try-except 블록으로 에러를 포착하고, state의 errors 리스트에 추가합니다.
- 에러가 발생해도 워크플로는 계속 진행되며, 부분적인 결과를 반환할 수 있습니다.
- 각 노드는 에러 발생 시 빈 결과를 반환하되, errors 필드에 에러 메시지를 추가합니다.
- 최종 상태의 errors 리스트를 확인하여 전체 실행 중 발생한 모든 에러를 추적할 수 있습니다.

비동기 태스크 전파:
- 모든 노드는 async def로 정의되어 있으며, LangGraph가 자동으로 비동기 실행을 보장합니다.
- 각 노드 내부에서 병렬 처리가 필요한 경우 (예: KeywordExtractorNode의 청크 병렬 처리),
  asyncio.gather()를 사용하여 병렬 실행을 구현합니다.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from src.workflows.nodes.aggregator_node import aggregator_node
from src.workflows.nodes.collector_node import collector_node
from src.workflows.nodes.insight_node import insight_node
from src.workflows.nodes.keyword_extractor_node import keyword_extractor_node
from src.workflows.state import AnalysisState


logger = logging.getLogger(__name__)


def create_keyword_analysis_graph(
    enable_parallel_processing: bool = False,
) -> StateGraph:
    """
    LangGraph 워크플로 생성

    키워드 분석 파이프라인을 위한 LangGraph 워크플로를 생성합니다.

    노드 구성:
    - collector: 데이터 청크 생성 (CollectorNode)
    - extractor: 키워드 추출 (KeywordExtractorNode)
    - aggregator: 키워드 통합 및 정규화 (AggregatorNode)
    - insight: 내러티브 요약 및 거래 인사이트 생성 (InsightNode)

    엣지 구성:
    - collector → extractor → aggregator → insight → END

    병렬 처리 옵션:
    - parallel_concurrency=0: 무제한 병렬 처리 (asyncio.gather, 빠르지만 rate limit 위험)
    - parallel_concurrency=N (N>0, 기본값: 5): 최대 N개 청크를 동시에 처리 (Semaphore 사용, 안정성과 성능의 균형)

    참고: 병렬 처리 옵션은 keyword_extractor_node 내부에서 처리되며,
    워크플로 구조는 동일합니다. 비동기 I/O 바운드 작업이므로 항상 병렬 처리를 사용합니다.

    에러 핸들링:
    - 각 노드에서 발생한 에러는 state.errors 리스트에 누적됩니다.
    - 에러가 발생해도 워크플로는 계속 진행되며, 부분적인 결과를 반환할 수 있습니다.

    비동기 실행:
    - 모든 노드는 async def로 정의되어 있으며, LangGraph가 자동으로 비동기 실행을 보장합니다.

    Args:
        enable_parallel_processing: 병렬 처리 활성화 여부 (기본값: False)
            이 파라미터는 더 이상 사용되지 않으며, config의 parallel_concurrency 옵션을 사용합니다.
            호환성을 위해 유지되지만 실제 동작에는 영향을 주지 않습니다.

    Returns:
        컴파일된 LangGraph 워크플로
    """
    logger.info(
        "[LangGraph Pipeline] 워크플로 생성 시작 (병렬 처리 옵션: %s)",
        "활성화" if enable_parallel_processing else "비활성화",
    )

    # StateGraph 생성
    workflow = StateGraph(AnalysisState)

    # 노드 추가
    # CollectorNode는 4.2 단계에서 구현 완료
    workflow.add_node("collector", collector_node)
    # KeywordExtractorNode는 4.3 단계에서 구현 완료
    # 병렬 처리 옵션은 keyword_extractor_node 내부에서 처리됩니다.
    workflow.add_node("extractor", keyword_extractor_node)
    # AggregatorNode는 4.5 단계까지 구현 완료
    workflow.add_node("aggregator", aggregator_node)
    # InsightNode는 4.8 단계에서 구현 완료
    workflow.add_node("insight", insight_node)

    # 엣지 정의
    workflow.set_entry_point("collector")
    workflow.add_edge("collector", "extractor")
    workflow.add_edge("extractor", "aggregator")
    workflow.add_edge("aggregator", "insight")
    workflow.add_edge("insight", END)

    logger.info(
        "[LangGraph Pipeline] 워크플로 생성 완료: collector → extractor → aggregator → insight → END"
    )

    return workflow.compile()


async def run_keyword_analysis_workflow(
    initial_state: AnalysisState, graph: Any | None = None
) -> AnalysisState:
    """
    LangGraph 워크플로를 실행하고 최종 상태를 반환합니다.

    에러 핸들링:
    - 워크플로 실행 중 발생한 예외는 포착하여 state.errors에 추가합니다.
    - 예외가 발생해도 가능한 한 부분적인 결과를 반환합니다.
    - 실행 시간을 측정하여 state.execution_time에 기록합니다.

    비동기 실행:
    - LangGraph의 ainvoke 메서드를 사용하여 비동기로 워크플로를 실행합니다.
    - 모든 노드는 async def로 정의되어 있어 자동으로 비동기 실행됩니다.

    Args:
        initial_state: 초기 워크플로 상태
            - raw_records: 정규화된 원본 데이터 (필수)
            - config: 설정 정보 (필수)
            - errors: 에러 리스트 (선택, 없으면 빈 리스트로 초기화)
        graph: 컴파일된 LangGraph 워크플로 (None이면 자동 생성)

    Returns:
        최종 워크플로 상태
            - 모든 노드의 처리 결과가 포함됩니다.
            - errors 리스트에 발생한 모든 에러가 누적됩니다.
            - execution_time에 실행 시간이 기록됩니다.

    Raises:
        ValueError: 필수 필드(raw_records, config)가 누락된 경우
        Exception: 워크플로 실행 중 치명적인 에러가 발생한 경우
    """
    logger.info("[LangGraph Pipeline] 워크플로 실행 시작")

    # 입력 검증
    if "raw_records" not in initial_state:
        raise ValueError("initial_state에 'raw_records' 필드가 필요합니다.")
    if "config" not in initial_state:
        raise ValueError("initial_state에 'config' 필드가 필요합니다.")

    # 초기 상태 준비
    start_time = datetime.now(timezone.utc)
    state: AnalysisState = {
        **initial_state,
        "errors": initial_state.get("errors", []),
        "start_time": start_time,
    }

    # 워크플로 생성 (제공되지 않은 경우)
    if graph is None:
        logger.info("[LangGraph Pipeline] 워크플로 자동 생성")

        # 설정에서 병렬 처리 동시성 옵션 확인
        config = initial_state.get("config", {})
        llm_config = config.get("llm", {})
        parallel_concurrency = llm_config.get("parallel_concurrency", 5)

        if parallel_concurrency == 0:
            concurrency_info = "무제한"
        else:
            concurrency_info = f"최대 {parallel_concurrency}개 동시 실행"

        logger.info("[LangGraph Pipeline] 병렬 처리 동시성: %s", concurrency_info)

        # 워크플로 생성 (병렬 처리 옵션은 keyword_extractor_node 내부에서 처리됨)
        graph = create_keyword_analysis_graph()

    try:
        # 워크플로 실행 (비동기)
        logger.info("[LangGraph Pipeline] 워크플로 실행 중...")
        final_state = await graph.ainvoke(state)

        # 실행 시간 계산
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()

        final_state["end_time"] = end_time
        final_state["execution_time"] = execution_time

        # 에러 로깅
        errors = final_state.get("errors", [])
        if errors:
            logger.warning(
                "[LangGraph Pipeline] 워크플로 실행 중 %d개의 에러 발생: %s",
                len(errors),
                "; ".join(errors[:3]),  # 처음 3개만 표시
            )
        else:
            logger.info("[LangGraph Pipeline] 워크플로 실행 완료 (에러 없음)")

        logger.info(
            "[LangGraph Pipeline] 실행 시간: %.2f초, 에러 수: %d",
            execution_time,
            len(errors),
        )

        return final_state

    except Exception as e:
        # 치명적인 에러 처리
        error_msg = f"LangGraph 워크플로 실행 중 예외 발생: {str(e)}"
        logger.error("[LangGraph Pipeline] %s", error_msg, exc_info=True)

        # 부분적인 결과 반환 시도
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()

        return {
            **state,
            "errors": state.get("errors", []) + [error_msg],
            "end_time": end_time,
            "execution_time": execution_time,
        }

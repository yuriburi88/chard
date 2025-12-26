"""
비동기 유틸리티 모듈

애플리케이션 전반의 asyncio 이벤트 루프 초기화 및 관리 유틸리티를 제공합니다.
"""

import asyncio
import logging
import sys
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any


logger = logging.getLogger(__name__)


def setup_event_loop_policy() -> None:
    """
    asyncio 이벤트 루프 정책을 설정합니다.

    Windows 환경에서 ProactorEventLoop를 사용하도록 설정하여
    비동기 I/O 성능을 최적화합니다.
    """
    if sys.platform == "win32":
        # Windows에서 ProactorEventLoop 사용 (더 나은 성능)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.debug("Windows ProactorEventLoop 정책 설정 완료")
    else:
        # Unix 계열에서는 기본 정책 사용
        logger.debug("기본 이벤트 루프 정책 사용")


@asynccontextmanager
async def managed_event_loop():
    """
    이벤트 루프를 관리하는 컨텍스트 매니저입니다.

    사용 예시:
        async with managed_event_loop():
            # 비동기 작업 수행
            await some_async_function()
    """
    # 이벤트 루프 정책 설정
    setup_event_loop_policy()

    # 이벤트 루프 가져오기 또는 생성
    try:
        loop = asyncio.get_running_loop()
        logger.debug("실행 중인 이벤트 루프 사용")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug("새 이벤트 루프 생성")

    try:
        yield loop
    finally:
        # 정리 작업
        try:
            # 대기 중인 모든 태스크 취소
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.debug(f"대기 중인 태스크 {len(pending)}개 취소 중...")
                for task in pending:
                    task.cancel()

                # 취소된 태스크 완료 대기
                await asyncio.gather(*pending, return_exceptions=True)

            # 이벤트 루프 종료
            if not loop.is_closed():
                loop.close()
                logger.debug("이벤트 루프 종료 완료")
        except Exception as e:
            logger.warning(f"이벤트 루프 정리 중 오류 발생: {e}")


async def run_with_timeout(
    coro: Callable,
    timeout: float | None = None,
    timeout_message: str = "작업이 타임아웃되었습니다.",
) -> Any:
    """
    타임아웃을 적용하여 코루틴을 실행합니다.

    Args:
        coro: 실행할 코루틴
        timeout: 타임아웃 시간 (초, None이면 타임아웃 없음)
        timeout_message: 타임아웃 발생 시 출력할 메시지

    Returns:
        코루틴의 반환값

    Raises:
        asyncio.TimeoutError: 타임아웃 발생 시
    """
    if timeout is None:
        return await coro

    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"{timeout_message} (타임아웃: {timeout}초)")
        raise


async def cleanup_resources() -> None:
    """
    애플리케이션 종료 시 리소스를 정리합니다.

    HTTP 클라이언트, 데이터베이스 연결 등의 리소스를 안전하게 종료합니다.
    """
    logger.info("리소스 정리 시작...")

    # TODO: 실제 리소스 정리 구현
    # - HTTP 클라이언트 세션 종료
    # - 데이터베이스 연결 종료
    # - 임시 파일 정리 등

    logger.info("리소스 정리 완료")


def run_async_main(
    main_func: Callable, *args, timeout: float | None = None, **kwargs
) -> int:
    """
    비동기 메인 함수를 실행하는 래퍼 함수입니다.

    이벤트 루프 초기화, 에러 핸들링, 리소스 정리를 자동으로 처리합니다.

    Args:
        main_func: 실행할 비동기 메인 함수
        *args: 메인 함수에 전달할 위치 인자
        timeout: 전체 실행 타임아웃 (초, None이면 타임아웃 없음)
        **kwargs: 메인 함수에 전달할 키워드 인자

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """

    async def wrapped_main() -> None:
        """리소스 정리를 포함한 래핑된 메인 함수"""
        try:
            # 메인 함수 실행
            if timeout:
                await run_with_timeout(
                    main_func(*args, **kwargs),
                    timeout=timeout,
                    timeout_message="애플리케이션 실행이 타임아웃되었습니다.",
                )
            else:
                await main_func(*args, **kwargs)
        finally:
            # 리소스 정리
            await cleanup_resources()

    try:
        # 이벤트 루프 정책 설정
        setup_event_loop_policy()

        # 비동기 메인 함수 실행
        asyncio.run(wrapped_main())
        return 0

    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
        return 130
    except asyncio.TimeoutError:
        logger.error("애플리케이션 실행이 타임아웃되었습니다.")
        return 124
    except Exception as e:
        logger.critical(f"예상치 못한 오류 발생: {e}", exc_info=True)
        return 1

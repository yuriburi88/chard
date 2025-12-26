"""
BaseCollector 추상 클래스

모든 데이터 수집기가 구현해야 하는 공통 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseCollector(ABC):
    """
    데이터 수집기의 기본 추상 클래스.

    모든 수집기(RSS, Telegram, Economic Calendar 등)는
    이 클래스를 상속받아 구현해야 합니다.
    """

    @abstractmethod
    async def collect(
        self,
        config: Any,
        min_timestamp: datetime | None = None,
    ) -> list[Any]:
        """
        데이터를 수집합니다.

        Args:
            config: 수집기 설정 객체
            min_timestamp: 이 시간 이후의 데이터만 수집 (선택적)

        Returns:
            수집된 데이터 객체 리스트
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """
        수집기의 소스 타입을 반환합니다.

        Returns:
            소스 타입 문자열 (예: "rss", "telegram", "economic_calendar")
        """
        pass

    def validate_config(self, config: Any) -> bool:
        """
        설정 객체의 유효성을 검증합니다.

        Args:
            config: 검증할 설정 객체

        Returns:
            유효하면 True, 아니면 False
        """
        return True

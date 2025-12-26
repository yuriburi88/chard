"""
고유 ID 생성기 (Singleton 패턴)

각 실행 turn 내에서 고유한 ID를 생성합니다.
초 단위 epoch time을 seed로 사용하여 시작하고, 요청 시마다 1씩 증가합니다.
"""

import logging
import time
from typing import Any, Optional


logger = logging.getLogger(__name__)


class RecordIdGenerator:
    """
    레코드 고유 ID 생성기 (Singleton)

    생성 시각의 초 단위 epoch time을 seed로 사용하고,
    요청 시마다 1씩 증가하여 고유 ID를 생성합니다.
    """

    _instance: Optional["RecordIdGenerator"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # 초 단위 epoch time을 seed로 사용
            self._seed = int(time.time())
            self._counter = 0
            self._id_mapping: dict[int, dict[str, Any]] = {}
            RecordIdGenerator._initialized = True

            logger.info(f"[RecordIdGenerator] 초기화 완료: seed={self._seed}")

    def generate_id(self) -> int:
        """
        새로운 고유 ID를 생성합니다.

        Returns:
            고유 ID (정수)
        """
        self._counter += 1
        record_id = self._seed + self._counter

        logger.debug(
            f"[RecordIdGenerator] ID 생성: {record_id} (seed={self._seed}, counter={self._counter})"
        )

        return record_id

    def register_record(self, record_id: int, record: dict[str, Any]) -> None:
        """
        레코드를 ID 매핑에 등록합니다.

        Args:
            record_id: 레코드 ID
            record: 레코드 데이터 (원본 레코드 딕셔너리)
        """
        self._id_mapping[record_id] = record

        logger.debug(
            f"[RecordIdGenerator] 레코드 등록: id={record_id}, "
            f"source={record.get('source', 'unknown')}, "
            f"text_preview={str(record.get('text', ''))[:50]}..."
        )

    def get_record(self, record_id: int) -> dict[str, Any] | None:
        """
        ID로 레코드를 조회합니다.

        Args:
            record_id: 레코드 ID

        Returns:
            레코드 데이터 (없으면 None)
        """
        return self._id_mapping.get(record_id)

    def get_all_mappings(self) -> dict[int, dict[str, Any]]:
        """
        모든 ID 매핑을 반환합니다 (디버깅용).

        Returns:
            ID 매핑 딕셔너리
        """
        return self._id_mapping.copy()

    def get_mapping_stats(self) -> dict[str, Any]:
        """
        ID 매핑 통계를 반환합니다 (디버깅용).

        Returns:
            통계 정보 딕셔너리
        """
        return {
            "seed": self._seed,
            "counter": self._counter,
            "total_records": len(self._id_mapping),
            "source_distribution": self._get_source_distribution(),
        }

    def _get_source_distribution(self) -> dict[str, int]:
        """소스별 레코드 수 분포를 계산합니다."""
        distribution: dict[str, int] = {}
        for record in self._id_mapping.values():
            source = record.get("source", "unknown")
            distribution[source] = distribution.get(source, 0) + 1
        return distribution

    def reset(self) -> None:
        """
        ID 생성기를 리셋합니다 (테스트용).
        """
        self._seed = int(time.time())
        self._counter = 0
        self._id_mapping.clear()
        logger.info(f"[RecordIdGenerator] 리셋 완료: 새로운 seed={self._seed}")


# 전역 인스턴스 접근 함수
def get_id_generator() -> RecordIdGenerator:
    """
    RecordIdGenerator 싱글톤 인스턴스를 반환합니다.

    Returns:
        RecordIdGenerator 인스턴스
    """
    return RecordIdGenerator()

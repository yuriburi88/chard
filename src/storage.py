"""
비동기 파일 I/O 유틸리티 모듈

출력 디렉토리 구조 생성 및 비동기 파일 읽기/쓰기 기능을 제공합니다.
- `output/<YYYY-MM-DD>/<HHmmss>` 디렉토리 구조 생성
- 비동기 JSON 파일 저장/읽기
- 비동기 텍스트 파일 저장/읽기
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


try:
    import aiofiles

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logging.warning(
        "aiofiles가 설치되지 않았습니다. 비동기 파일 I/O 기능이 비활성화됩니다."
    )

logger = logging.getLogger(__name__)


class StorageManager:
    """
    비동기 파일 I/O 관리 클래스

    출력 디렉토리 구조를 생성하고 비동기 파일 읽기/쓰기를 관리합니다.
    """

    def __init__(self, base_output_dir: str = "output", display_timezone: int = 9):
        """
        StorageManager 초기화

        Args:
            base_output_dir: 기본 출력 디렉토리 경로 (기본값: "output")
            display_timezone: 표현용 타임존 offset (UTC offset, 기본값: 9 = KST)
        """
        self.base_output_dir = Path(base_output_dir)
        self.display_timezone = display_timezone

        if not AIOFILES_AVAILABLE:
            logger.warning(
                "[StorageManager] aiofiles가 설치되지 않아 비동기 파일 I/O가 비활성화됩니다. "
                "동기 방식으로 대체됩니다."
            )

    def _to_display_timezone(self, utc_datetime: datetime) -> datetime:
        """
        UTC datetime을 표현용 타임존으로 변환합니다.

        Args:
            utc_datetime: UTC datetime 객체

        Returns:
            표현용 타임존으로 변환된 datetime 객체
        """
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)

        display_tz = timezone(timedelta(hours=self.display_timezone))
        return utc_datetime.astimezone(display_tz)

    async def create_output_directory(
        self, timestamp: datetime | None = None
    ) -> Path:
        """
        출력 디렉토리 구조를 생성합니다.

        `output/<YYYY-MM-DD>` 형식의 날짜별 디렉토리를 생성합니다.

        Args:
            timestamp: 타임스탬프 (None이면 현재 시간 사용)

        Returns:
            생성된 디렉토리 경로 (Path 객체)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # 타임존이 없는 경우 UTC로 가정
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 표현용 타임존으로 변환하여 날짜 계산
        display_timestamp = self._to_display_timezone(timestamp)
        date_str = display_timestamp.strftime("%Y-%m-%d")
        output_dir = self.base_output_dir / date_str

        # 디렉토리 생성 (비동기)
        if AIOFILES_AVAILABLE:
            # aiofiles는 디렉토리 생성이 없으므로 os.makedirs 사용
            # 하지만 비동기 컨텍스트에서 안전하게 사용하기 위해
            # asyncio.to_thread를 사용하거나 동기 함수를 직접 호출
            import asyncio

            await asyncio.to_thread(os.makedirs, output_dir, exist_ok=True)
        else:
            # 동기 방식
            os.makedirs(output_dir, exist_ok=True)

        logger.info(f"[StorageManager] 출력 디렉토리 생성: {output_dir}")

        return output_dir

    async def save_json(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        file_path: Path | str,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> None:
        """
        데이터를 JSON 파일로 비동기 저장합니다.

        Args:
            data: 저장할 데이터 (딕셔너리 또는 딕셔너리 리스트)
            file_path: 저장할 파일 경로
            indent: JSON 들여쓰기 (기본값: 2)
            ensure_ascii: ASCII만 사용 여부 (기본값: False, 한글 등 유니코드 허용)
        """
        file_path = Path(file_path)

        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # JSON 문자열로 변환
        json_str = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)

        if AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json_str)
        else:
            # 동기 방식 (fallback)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)

        logger.info(
            f"[StorageManager] JSON 파일 저장 완료: {file_path} "
            f"(크기: {len(json_str):,} bytes)"
        )

    async def load_json(
        self, file_path: Path | str
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        JSON 파일을 비동기로 읽어옵니다.

        Args:
            file_path: 읽을 파일 경로

        Returns:
            파싱된 JSON 데이터 (딕셔너리 또는 딕셔너리 리스트)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        if AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()
        else:
            # 동기 방식 (fallback)
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

        data = json.loads(content)

        logger.info(
            f"[StorageManager] JSON 파일 로드 완료: {file_path} "
            f"(크기: {len(content):,} bytes)"
        )

        return data

    async def save_text(
        self, content: str, file_path: Path | str, encoding: str = "utf-8"
    ) -> None:
        """
        텍스트를 파일로 비동기 저장합니다.

        Args:
            content: 저장할 텍스트 내용
            file_path: 저장할 파일 경로
            encoding: 파일 인코딩 (기본값: "utf-8")
        """
        file_path = Path(file_path)

        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                await f.write(content)
        else:
            # 동기 방식 (fallback)
            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)

        logger.info(
            f"[StorageManager] 텍스트 파일 저장 완료: {file_path} "
            f"(크기: {len(content):,} bytes)"
        )

    async def load_text(self, file_path: Path | str, encoding: str = "utf-8") -> str:
        """
        텍스트 파일을 비동기로 읽어옵니다.

        Args:
            file_path: 읽을 파일 경로
            encoding: 파일 인코딩 (기본값: "utf-8")

        Returns:
            파일 내용 (문자열)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        if AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, encoding=encoding) as f:
                content = await f.read()
        else:
            # 동기 방식 (fallback)
            with open(file_path, encoding=encoding) as f:
                content = f.read()

        logger.info(
            f"[StorageManager] 텍스트 파일 로드 완료: {file_path} "
            f"(크기: {len(content):,} bytes)"
        )

        return content

    async def save_raw_data(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        output_dir: Path | str,
        filename_prefix: str = "raw",
        timestamp: datetime | None = None,
    ) -> Path:
        """
        원본 데이터를 JSON 파일로 저장합니다.

        `*_raw.json` 형식의 파일명으로 저장합니다.

        Args:
            data: 저장할 원본 데이터
            output_dir: 출력 디렉토리 경로
            filename_prefix: 파일명 접두사 (기본값: "raw")
            timestamp: 타임스탬프 (None이면 현재 시간 사용)

        Returns:
            저장된 파일 경로
        """
        output_dir = Path(output_dir)

        # timestamp가 None이면 현재 시간 사용
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        else:
            # 타임존이 없는 경우 UTC로 가정
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 표현용 타임존으로 변환하여 파일명 생성
        display_timestamp = self._to_display_timezone(timestamp)
        date_str = display_timestamp.strftime("%Y%m%d")
        time_str = display_timestamp.strftime("%H%M%S")
        filename = f"{filename_prefix}_{date_str}_{time_str}_raw.json"

        file_path = output_dir / filename

        await self.save_json(data, file_path)

        logger.info(f"[StorageManager] 원본 데이터 저장 완료: {file_path}")

        return file_path

    def get_output_dir_path(self, timestamp: datetime | None = None) -> Path:
        """
        출력 디렉토리 경로를 반환합니다 (생성하지 않음).

        Args:
            timestamp: 타임스탬프 (None이면 현재 시간 사용)

        Returns:
            출력 디렉토리 경로 (Path 객체)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # 타임존이 없는 경우 UTC로 가정
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # 표현용 타임존으로 변환하여 날짜 계산
        display_timestamp = self._to_display_timezone(timestamp)
        date_str = display_timestamp.strftime("%Y-%m-%d")

        return self.base_output_dir / date_str


class ExecutionLogger:
    """
    실행 로그 관리 클래스

    실행 시작/종료 시간, 처리 단계별 소요 시간, 데이터 통계, 에러 정보 등을 기록하고
    최종 실행 로그를 JSON 파일로 저장합니다.
    """

    def __init__(self, output_dir: Path | str):
        """
        ExecutionLogger 초기화

        Args:
            output_dir: 실행 로그를 저장할 출력 디렉토리 경로
        """
        self.output_dir = Path(output_dir)
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.stages: list[dict[str, Any]] = []
        self.statistics: dict[str, Any] = {}
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def start(self) -> None:
        """
        실행 시작 시간을 기록합니다.
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"[ExecutionLogger] 실행 시작: {self.start_time.isoformat()}")

    def end(self) -> None:
        """
        실행 종료 시간을 기록합니다.
        """
        self.end_time = datetime.now(timezone.utc)

        if self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            logger.info(
                f"[ExecutionLogger] 실행 종료: {self.end_time.isoformat()} "
                f"(소요 시간: {duration:.2f}초)"
            )
        else:
            logger.warning(
                "[ExecutionLogger] 실행 종료 기록되었지만 시작 시간이 없습니다."
            )

    def log_stage(
        self,
        stage_name: str,
        start_time: datetime,
        end_time: datetime,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        처리 단계 정보를 기록합니다.

        Args:
            stage_name: 단계 이름 (예: "collect", "preprocess", "normalize")
            start_time: 단계 시작 시간
            end_time: 단계 종료 시간
            success: 성공 여부 (기본값: True)
            details: 추가 상세 정보 (선택)
        """
        duration = (end_time - start_time).total_seconds()

        stage_info = {
            "stage": stage_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "success": success,
            "details": details or {},
        }

        self.stages.append(stage_info)

        logger.info(
            f"[ExecutionLogger] 단계 완료: {stage_name} "
            f"(소요 시간: {duration:.2f}초, 성공: {success})"
        )

    def set_statistics(self, stats: dict[str, Any]) -> None:
        """
        데이터 통계를 설정합니다.

        Args:
            stats: 통계 정보 딕셔너리
                예: {
                    "rss_articles": 50,
                    "telegram_messages": 100,
                    "processed_items": 150,
                    "chunks_created": 3
                }
        """
        self.statistics = stats
        logger.info(f"[ExecutionLogger] 통계 정보 설정: {stats}")

    def add_statistic(self, key: str, value: Any) -> None:
        """
        개별 통계 항목을 추가합니다.

        Args:
            key: 통계 키
            value: 통계 값
        """
        self.statistics[key] = value
        logger.debug(f"[ExecutionLogger] 통계 추가: {key} = {value}")

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        에러 정보를 기록합니다.

        Args:
            error_type: 에러 타입 (예: "CollectionError", "ProcessingError")
            error_message: 에러 메시지
            stage: 에러가 발생한 단계 (선택)
            details: 추가 상세 정보 (선택)
        """
        error_info = {
            "type": error_type,
            "message": error_message,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        self.errors.append(error_info)

        logger.error(
            f"[ExecutionLogger] 에러 기록: {error_type} - {error_message} "
            f"(단계: {stage or 'N/A'})"
        )

    def log_warning(
        self,
        warning_type: str,
        warning_message: str,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        경고 정보를 기록합니다.

        Args:
            warning_type: 경고 타입
            warning_message: 경고 메시지
            stage: 경고가 발생한 단계 (선택)
            details: 추가 상세 정보 (선택)
        """
        warning_info = {
            "type": warning_type,
            "message": warning_message,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        self.warnings.append(warning_info)

        logger.warning(
            f"[ExecutionLogger] 경고 기록: {warning_type} - {warning_message} "
            f"(단계: {stage or 'N/A'})"
        )

    def get_summary(self) -> dict[str, Any]:
        """
        실행 로그 요약 정보를 반환합니다.

        Returns:
            실행 로그 요약 딕셔너리
        """
        total_duration = None
        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            # 아직 종료되지 않은 경우 현재 시간까지의 경과 시간
            total_duration = (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds()

        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_seconds": (
                round(total_duration, 2) if total_duration else None
            ),
            "stages_count": len(self.stages),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "statistics": self.statistics,
        }

    async def save_log(
        self, storage_manager: StorageManager, filename: str = "execution_log.json"
    ) -> Path:
        """
        실행 로그를 JSON 파일로 저장합니다.

        Args:
            storage_manager: StorageManager 인스턴스
            filename: 저장할 파일명 (기본값: "execution_log.json")

        Returns:
            저장된 파일 경로
        """
        log_data = {
            "execution": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "total_duration_seconds": None,
            },
            "stages": self.stages,
            "statistics": self.statistics,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.get_summary(),
        }

        # 총 소요 시간 계산
        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds()
            log_data["execution"]["total_duration_seconds"] = round(total_duration, 2)
        elif self.start_time:
            total_duration = (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds()
            log_data["execution"]["total_duration_seconds"] = round(total_duration, 2)

        file_path = self.output_dir / filename

        await storage_manager.save_json(log_data, file_path)

        logger.info(f"[ExecutionLogger] 실행 로그 저장 완료: {file_path}")

        return file_path

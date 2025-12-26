"""
비동기 파일 I/O 유틸리티 테스트

StorageManager의 각 기능을 테스트합니다.
- 디렉토리 구조 생성
- JSON 파일 저장/읽기
- 텍스트 파일 저장/읽기
- 원본 데이터 저장
"""

import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.storage import ExecutionLogger, StorageManager


class TestStorageManager:
    """StorageManager 테스트 클래스"""

    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # 테스트 후 정리
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def storage_manager(self, temp_dir):
        """StorageManager 인스턴스 생성"""
        return StorageManager(base_output_dir=str(temp_dir))

    @pytest.mark.asyncio
    async def test_create_output_directory(self, storage_manager):
        """출력 디렉토리 생성 테스트"""
        timestamp = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        output_dir = await storage_manager.create_output_directory(timestamp)

        # 디렉토리가 생성되었는지 확인
        assert output_dir.exists()
        assert output_dir.is_dir()

        # 경로 형식 확인: output/2024-01-15 (날짜별 폴더만)
        assert "2024-01-15" in str(output_dir)
        assert output_dir.name == "2024-01-15"

    @pytest.mark.asyncio
    async def test_create_output_directory_current_time(self, storage_manager):
        """현재 시간으로 출력 디렉토리 생성 테스트"""
        output_dir = await storage_manager.create_output_directory()

        # 디렉토리가 생성되었는지 확인
        assert output_dir.exists()
        assert output_dir.is_dir()

        # 경로에 날짜가 포함되어 있는지 확인 (날짜별 폴더만)
        assert output_dir.name  # 날짜 디렉토리 (예: 2024-01-15)
        # 날짜 형식 확인 (YYYY-MM-DD)
        assert len(output_dir.name) == 10
        assert output_dir.name.count("-") == 2

    @pytest.mark.asyncio
    async def test_save_and_load_json(self, storage_manager, temp_dir):
        """JSON 파일 저장 및 읽기 테스트"""
        # 출력 디렉토리 생성
        output_dir = await storage_manager.create_output_directory()

        # 테스트 데이터
        test_data = {
            "keywords": ["비트코인", "이더리움"],
            "scores": [85, 75],
            "metadata": {"timestamp": "2024-01-15T14:30:45Z", "source_count": 10},
        }

        # JSON 파일 저장
        file_path = output_dir / "test.json"
        await storage_manager.save_json(test_data, file_path)

        # 파일이 생성되었는지 확인
        assert file_path.exists()

        # JSON 파일 읽기
        loaded_data = await storage_manager.load_json(file_path)

        # 데이터가 일치하는지 확인
        assert loaded_data == test_data
        assert loaded_data["keywords"] == ["비트코인", "이더리움"]
        assert loaded_data["scores"] == [85, 75]

    @pytest.mark.asyncio
    async def test_save_and_load_json_list(self, storage_manager):
        """JSON 리스트 저장 및 읽기 테스트"""
        # 출력 디렉토리 생성
        output_dir = await storage_manager.create_output_directory()

        # 테스트 데이터 (리스트)
        test_data = [
            {"keyword": "비트코인", "score": 85},
            {"keyword": "이더리움", "score": 75},
        ]

        # JSON 파일 저장
        file_path = output_dir / "test_list.json"
        await storage_manager.save_json(test_data, file_path)

        # JSON 파일 읽기
        loaded_data = await storage_manager.load_json(file_path)

        # 데이터가 일치하는지 확인
        assert isinstance(loaded_data, list)
        assert len(loaded_data) == 2
        assert loaded_data[0]["keyword"] == "비트코인"
        assert loaded_data[1]["keyword"] == "이더리움"

    @pytest.mark.asyncio
    async def test_save_and_load_text(self, storage_manager):
        """텍스트 파일 저장 및 읽기 테스트"""
        # 출력 디렉토리 생성
        output_dir = await storage_manager.create_output_directory()

        # 테스트 텍스트
        test_text = "비트코인 가격이 상승하고 있습니다.\n이더리움도 함께 상승세를 보이고 있습니다."

        # 텍스트 파일 저장
        file_path = output_dir / "test.txt"
        await storage_manager.save_text(test_text, file_path)

        # 파일이 생성되었는지 확인
        assert file_path.exists()

        # 텍스트 파일 읽기
        loaded_text = await storage_manager.load_text(file_path)

        # 텍스트가 일치하는지 확인
        assert loaded_text == test_text

    @pytest.mark.asyncio
    async def test_save_text_unicode(self, storage_manager):
        """유니코드 텍스트 저장 테스트"""
        # 출력 디렉토리 생성
        output_dir = await storage_manager.create_output_directory()

        # 한글, 이모지 등 유니코드 텍스트
        test_text = "비트코인 🚀 이더리움 💎 암호화폐 시장 급등!"

        # 텍스트 파일 저장
        file_path = output_dir / "test_unicode.txt"
        await storage_manager.save_text(test_text, file_path)

        # 텍스트 파일 읽기
        loaded_text = await storage_manager.load_text(file_path)

        # 텍스트가 일치하는지 확인
        assert loaded_text == test_text

    @pytest.mark.asyncio
    async def test_save_raw_data(self, storage_manager):
        """원본 데이터 저장 테스트"""
        # 출력 디렉토리 생성
        timestamp = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        output_dir = await storage_manager.create_output_directory(timestamp)

        # 테스트 원본 데이터
        raw_data = [
            {
                "source": "rss",
                "title": "비트코인 가격 상승",
                "content": "비트코인 가격이 10% 상승했습니다.",
                "timestamp": "2024-01-15T14:30:45Z",
            },
            {
                "source": "telegram",
                "channel": "CryptoChannel",
                "text": "이더리움도 상승 중",
                "timestamp": "2024-01-15T14:31:00Z",
            },
        ]

        # 원본 데이터 저장 (timestamp 전달)
        file_path = await storage_manager.save_raw_data(
            raw_data, output_dir, filename_prefix="test", timestamp=timestamp
        )

        # 파일이 생성되었는지 확인
        assert file_path.exists()

        # 파일명 형식 확인: test_<YYYYMMDD>_<HHmmss>_raw.json
        # 표현용 타임존(KST, UTC+9)으로 변환되므로 UTC 14:30:45 -> KST 23:30:45
        assert "test_" in file_path.name
        assert "20240115" in file_path.name
        assert "233045" in file_path.name  # KST로 변환된 시간
        assert "_raw.json" in file_path.name

        # JSON 파일 읽기
        loaded_data = await storage_manager.load_json(file_path)

        # 데이터가 일치하는지 확인
        assert isinstance(loaded_data, list)
        assert len(loaded_data) == 2
        assert loaded_data[0]["source"] == "rss"
        assert loaded_data[1]["source"] == "telegram"

    @pytest.mark.asyncio
    async def test_get_output_dir_path(self, storage_manager):
        """출력 디렉토리 경로 반환 테스트 (생성하지 않음)"""
        timestamp = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        output_dir_path = storage_manager.get_output_dir_path(timestamp)

        # 경로 형식 확인 (날짜별 폴더만)
        assert "2024-01-15" in str(output_dir_path)
        assert output_dir_path.name == "2024-01-15"

        # 디렉토리가 생성되지 않았는지 확인 (get_output_dir_path는 생성하지 않음)
        assert not output_dir_path.exists()

    @pytest.mark.asyncio
    async def test_file_not_found_error(self, storage_manager):
        """파일을 찾을 수 없을 때 에러 테스트"""
        # 존재하지 않는 파일 경로
        file_path = Path("nonexistent_file.json")

        # FileNotFoundError가 발생해야 함
        with pytest.raises(FileNotFoundError):
            await storage_manager.load_json(file_path)

        with pytest.raises(FileNotFoundError):
            await storage_manager.load_text(file_path)

    @pytest.mark.asyncio
    async def test_nested_directory_creation(self, storage_manager):
        """중첩된 디렉토리 자동 생성 테스트"""
        # 출력 디렉토리 생성
        output_dir = await storage_manager.create_output_directory()

        # 중첩된 경로에 파일 저장
        nested_path = output_dir / "subdir" / "nested" / "test.json"

        test_data = {"test": "data"}
        await storage_manager.save_json(test_data, nested_path)

        # 파일이 생성되었는지 확인
        assert nested_path.exists()
        assert nested_path.parent.exists()
        assert nested_path.parent.parent.exists()

        # 데이터 읽기
        loaded_data = await storage_manager.load_json(nested_path)
        assert loaded_data == test_data


class TestExecutionLogger:
    """ExecutionLogger 테스트 클래스"""

    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # 테스트 후 정리
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def storage_manager(self, temp_dir):
        """StorageManager 인스턴스 생성"""
        from src.storage import StorageManager

        return StorageManager(base_output_dir=str(temp_dir))

    @pytest.fixture
    def execution_logger(self, temp_dir):
        """ExecutionLogger 인스턴스 생성"""

        return ExecutionLogger(output_dir=temp_dir)

    def test_execution_logger_init(self, execution_logger):
        """ExecutionLogger 초기화 테스트"""
        assert execution_logger.start_time is None
        assert execution_logger.end_time is None
        assert len(execution_logger.stages) == 0
        assert len(execution_logger.statistics) == 0
        assert len(execution_logger.errors) == 0
        assert len(execution_logger.warnings) == 0

    def test_start_and_end(self, execution_logger):
        """실행 시작/종료 테스트"""
        execution_logger.start()
        assert execution_logger.start_time is not None


        time.sleep(0.1)  # 약간의 지연

        execution_logger.end()
        assert execution_logger.end_time is not None
        assert execution_logger.end_time > execution_logger.start_time

    def test_log_stage(self, execution_logger):
        """단계 로깅 테스트"""
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc)

        time.sleep(0.05)
        end_time = datetime.now(timezone.utc)

        execution_logger.log_stage(
            "test_stage",
            start_time,
            end_time,
            success=True,
            details={"items_processed": 10},
        )

        assert len(execution_logger.stages) == 1
        stage = execution_logger.stages[0]
        assert stage["stage"] == "test_stage"
        assert stage["success"] is True
        assert stage["details"]["items_processed"] == 10
        assert stage["duration_seconds"] > 0

    def test_set_statistics(self, execution_logger):
        """통계 설정 테스트"""
        stats = {"rss_articles": 50, "telegram_messages": 100, "processed_items": 150}

        execution_logger.set_statistics(stats)

        assert execution_logger.statistics == stats

    def test_add_statistic(self, execution_logger):
        """개별 통계 추가 테스트"""
        execution_logger.add_statistic("rss_articles", 50)
        execution_logger.add_statistic("telegram_messages", 100)

        assert execution_logger.statistics["rss_articles"] == 50
        assert execution_logger.statistics["telegram_messages"] == 100

    def test_log_error(self, execution_logger):
        """에러 로깅 테스트"""
        execution_logger.log_error(
            "CollectionError",
            "RSS 피드 수집 실패",
            stage="collect",
            details={"source": "BlockMedia", "url": "https://example.com/feed"},
        )

        assert len(execution_logger.errors) == 1
        error = execution_logger.errors[0]
        assert error["type"] == "CollectionError"
        assert error["message"] == "RSS 피드 수집 실패"
        assert error["stage"] == "collect"
        assert "timestamp" in error

    def test_log_warning(self, execution_logger):
        """경고 로깅 테스트"""
        execution_logger.log_warning(
            "DataQualityWarning",
            "일부 데이터가 필터링되었습니다",
            stage="preprocess",
            details={"filtered_count": 5},
        )

        assert len(execution_logger.warnings) == 1
        warning = execution_logger.warnings[0]
        assert warning["type"] == "DataQualityWarning"
        assert warning["message"] == "일부 데이터가 필터링되었습니다"
        assert warning["stage"] == "preprocess"
        assert "timestamp" in warning

    def test_get_summary(self, execution_logger):
        """요약 정보 반환 테스트"""
        execution_logger.start()
        execution_logger.set_statistics({"rss_articles": 50})
        execution_logger.log_stage(
            "test_stage",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            success=True,
        )

        summary = execution_logger.get_summary()

        assert summary["start_time"] is not None
        assert summary["stages_count"] == 1
        assert summary["errors_count"] == 0
        assert summary["warnings_count"] == 0
        assert summary["statistics"]["rss_articles"] == 50

    @pytest.mark.asyncio
    async def test_save_log(self, execution_logger, storage_manager):
        """실행 로그 저장 테스트"""
        from datetime import datetime, timezone

        execution_logger.start()
        execution_logger.set_statistics({"rss_articles": 50, "telegram_messages": 100})

        start_time = datetime.now(timezone.utc)

        time.sleep(0.05)
        end_time = datetime.now(timezone.utc)

        execution_logger.log_stage(
            "collect",
            start_time,
            end_time,
            success=True,
            details={"sources": ["rss", "telegram"]},
        )

        execution_logger.end()

        # 실행 로그 저장
        log_path = await execution_logger.save_log(storage_manager)

        # 파일이 생성되었는지 확인
        assert log_path.exists()

        # 로그 파일 읽기
        log_data = await storage_manager.load_json(log_path)

        # 로그 데이터 검증
        assert "execution" in log_data
        assert "stages" in log_data
        assert "statistics" in log_data
        assert "errors" in log_data
        assert "warnings" in log_data
        assert "summary" in log_data

        assert log_data["execution"]["start_time"] is not None
        assert log_data["execution"]["end_time"] is not None
        assert log_data["execution"]["total_duration_seconds"] is not None
        assert len(log_data["stages"]) == 1
        assert log_data["statistics"]["rss_articles"] == 50
        assert log_data["statistics"]["telegram_messages"] == 100

    @pytest.mark.asyncio
    async def test_save_log_with_errors(self, execution_logger, storage_manager):
        """에러가 포함된 실행 로그 저장 테스트"""
        execution_logger.start()
        execution_logger.log_error(
            "CollectionError", "RSS 피드 수집 실패", stage="collect"
        )
        execution_logger.log_warning(
            "DataQualityWarning", "일부 데이터 필터링", stage="preprocess"
        )
        execution_logger.end()

        # 실행 로그 저장
        log_path = await execution_logger.save_log(storage_manager)

        # 로그 파일 읽기
        log_data = await storage_manager.load_json(log_path)

        # 에러와 경고가 포함되어 있는지 확인
        assert len(log_data["errors"]) == 1
        assert len(log_data["warnings"]) == 1
        assert log_data["summary"]["errors_count"] == 1
        assert log_data["summary"]["warnings_count"] == 1

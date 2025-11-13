"""
main.py 함수 단위 테스트

데이터 수집 함수들의 빈 소스 처리 및 에러 처리 테스트
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.config_manager import AppConfig, CollectionPeriodConfig, OutputConfig, RSSSourceConfig, TelegramSourceConfig
from src.storage import ExecutionLogger
from main import collect_rss_data, collect_telegram_data
from src.collectors.models import Article, TelegramMessage


@pytest.fixture
def execution_logger(tmp_path):
    """ExecutionLogger 인스턴스 생성"""
    return ExecutionLogger(output_dir=tmp_path)


@pytest.fixture
def app_config_with_rss_only():
    """RSS 소스만 있는 AppConfig"""
    return AppConfig(
        gemini_api_key="test_key",
        collection_period=CollectionPeriodConfig(recent_hours=24),
        rss_sources=[
            RSSSourceConfig(
                name="Test RSS",
                url="https://example.com/feed",
                priority=1.0,
                timezone=9,
                max_articles=100,
                hours_back=24
            )
        ],
        telegram_sources=[],
        output=OutputConfig()
    )


@pytest.fixture
def app_config_with_telegram_only():
    """Telegram 소스만 있는 AppConfig"""
    return AppConfig(
        gemini_api_key="test_key",
        collection_period=CollectionPeriodConfig(recent_hours=24),
        rss_sources=[],
        telegram_sources=[
            TelegramSourceConfig(
                name="Test Telegram",
                channel_id="test_channel",
                auth_method="bot_api",
                bot_token="test_token",
                timezone=9,
                max_messages=100
            )
        ],
        output=OutputConfig()
    )


@pytest.fixture
def app_config_with_no_sources():
    """소스가 없는 AppConfig"""
    return AppConfig(
        gemini_api_key="test_key",
        collection_period=CollectionPeriodConfig(recent_hours=24),
        rss_sources=[],
        telegram_sources=[],
        output=OutputConfig()
    )


@pytest.fixture
def app_config_with_both_sources():
    """RSS와 Telegram 소스가 모두 있는 AppConfig"""
    return AppConfig(
        gemini_api_key="test_key",
        collection_period=CollectionPeriodConfig(recent_hours=24),
        rss_sources=[
            RSSSourceConfig(
                name="Test RSS",
                url="https://example.com/feed",
                priority=1.0,
                timezone=9,
                max_articles=100,
                hours_back=24
            )
        ],
        telegram_sources=[
            TelegramSourceConfig(
                name="Test Telegram",
                channel_id="test_channel",
                auth_method="bot_api",
                bot_token="test_token",
                timezone=9,
                max_messages=100
            )
        ],
        output=OutputConfig()
    )


@pytest.mark.asyncio
async def test_collect_rss_data_empty_sources(execution_logger, app_config_with_telegram_only):
    """RSS 소스가 없을 때 정상 동작 테스트"""
    min_timestamp = datetime.now(timezone.utc)
    
    articles = await collect_rss_data(
        app_config_with_telegram_only,
        min_timestamp,
        execution_logger
    )
    
    # 빈 리스트 반환 확인
    assert articles == []
    assert len(articles) == 0
    
    # log_stage가 호출되었는지 확인
    stages = execution_logger.stages
    rss_stages = [s for s in stages if s.get("stage") == "rss_collect"]
    assert len(rss_stages) == 1
    
    rss_stage = rss_stages[0]
    assert rss_stage["success"] is True
    assert rss_stage["details"]["sources_count"] == 0
    assert rss_stage["details"]["articles_count"] == 0


@pytest.mark.asyncio
async def test_collect_telegram_data_empty_sources(execution_logger, app_config_with_rss_only):
    """Telegram 소스가 없을 때 정상 동작 테스트"""
    min_timestamp = datetime.now(timezone.utc)
    
    messages = await collect_telegram_data(
        app_config_with_rss_only,
        min_timestamp,
        execution_logger
    )
    
    # 빈 리스트 반환 확인
    assert messages == []
    assert len(messages) == 0
    
    # log_stage가 호출되었는지 확인
    stages = execution_logger.stages
    telegram_stages = [s for s in stages if s.get("stage") == "telegram_collect"]
    assert len(telegram_stages) == 1
    
    telegram_stage = telegram_stages[0]
    assert telegram_stage["success"] is True
    assert telegram_stage["details"]["sources_count"] == 0
    assert telegram_stage["details"]["messages_count"] == 0


@pytest.mark.asyncio
async def test_collect_rss_data_with_sources(execution_logger, app_config_with_both_sources):
    """RSS 소스가 있을 때 정상 수집 테스트"""
    min_timestamp = datetime.now(timezone.utc)
    
    # RSSCollector를 모의로 대체
    mock_articles = [
        Article(
            title="Test Article",
            url="https://example.com/article",
            source="Test RSS",
            source_type="rss",
            published_at=datetime.now(timezone.utc),
            content="Test content",
            author="Test Author",
            description="Test description",
            tags=[]
        )
    ]
    
    with patch('main.RSSCollector') as mock_collector_class:
        mock_collector = AsyncMock()
        mock_collector.__aenter__ = AsyncMock(return_value=mock_collector)
        mock_collector.__aexit__ = AsyncMock(return_value=None)
        mock_collector.collect = AsyncMock(return_value=mock_articles)
        mock_collector_class.return_value = mock_collector
        
        articles = await collect_rss_data(
            app_config_with_both_sources,
            min_timestamp,
            execution_logger
        )
        
        # 기사가 수집되었는지 확인
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        
        # log_stage가 호출되었는지 확인
        stages = execution_logger.stages
        rss_stages = [s for s in stages if s.get("stage") == "rss_collect"]
        assert len(rss_stages) == 1
        
        rss_stage = rss_stages[0]
        assert rss_stage["success"] is True
        assert rss_stage["details"]["sources_count"] == 1
        assert rss_stage["details"]["articles_count"] == 1


@pytest.mark.asyncio
async def test_collect_telegram_data_with_sources(execution_logger, app_config_with_both_sources):
    """Telegram 소스가 있을 때 정상 수집 테스트"""
    min_timestamp = datetime.now(timezone.utc)
    
    # TelegramCollector를 모의로 대체
    mock_messages = [
        TelegramMessage(
            message_id=1,
            text="Test message",
            channel_id="test_channel",
            channel_name="Test Telegram",
            timestamp=datetime.now(timezone.utc),
            author="Test Author"
        )
    ]
    
    with patch('main.TelegramCollector') as mock_collector_class:
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=mock_messages)
        mock_collector_class.return_value = mock_collector
        
        messages = await collect_telegram_data(
            app_config_with_both_sources,
            min_timestamp,
            execution_logger
        )
        
        # 메시지가 수집되었는지 확인
        assert len(messages) == 1
        assert messages[0].text == "Test message"
        
        # log_stage가 호출되었는지 확인
        stages = execution_logger.stages
        telegram_stages = [s for s in stages if s.get("stage") == "telegram_collect"]
        assert len(telegram_stages) == 1
        
        telegram_stage = telegram_stages[0]
        assert telegram_stage["success"] is True
        assert telegram_stage["details"]["sources_count"] == 1
        assert telegram_stage["details"]["messages_count"] == 1


@pytest.mark.asyncio
async def test_main_async_no_sources_error(app_config_with_no_sources, tmp_path):
    """모든 소스가 없을 때 에러 발생 테스트"""
    from main import main_async
    from src.storage import ExecutionLogger
    
    # ExecutionLogger를 모의로 대체하여 에러 기록 확인
    captured_errors = []
    
    original_log_error = ExecutionLogger.log_error
    
    def mock_log_error(self, error_type, error_message, stage=None, details=None):
        captured_errors.append({
            "type": error_type,
            "message": error_message,
            "stage": stage,
            "details": details
        })
        return original_log_error(self, error_type, error_message, stage, details)
    
    # StorageManager를 모의로 대체
    with patch('main.StorageManager') as mock_storage_class:
        mock_storage = AsyncMock()
        mock_storage.create_output_directory = AsyncMock(return_value=tmp_path)
        mock_storage_class.return_value = mock_storage
        
        # setup_logging을 모의로 대체
        with patch('main.setup_logging'):
            # ExecutionLogger.log_error를 모의로 대체
            with patch.object(ExecutionLogger, 'log_error', mock_log_error):
                # main_async 실행 시 ValueError 발생 확인
                with pytest.raises(ValueError) as exc_info:
                    await main_async(app_config_with_no_sources, log_level="INFO")
                
                # 에러 메시지 확인
                assert "수집할 소스가 설정되지 않았습니다" in str(exc_info.value)
                
                # 에러가 로그에 기록되었는지 확인
                no_source_errors = [e for e in captured_errors if e["type"] == "NoSourceError"]
                assert len(no_source_errors) == 1
                assert "수집할 소스가 설정되지 않았습니다" in no_source_errors[0]["message"]
                assert no_source_errors[0]["details"]["rss_sources_count"] == 0
                assert no_source_errors[0]["details"]["telegram_sources_count"] == 0


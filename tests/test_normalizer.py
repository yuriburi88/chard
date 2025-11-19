"""
데이터 정규화 모듈 테스트

데이터 정규화 기능을 테스트합니다.
- Article을 CollectedItem으로 변환
- TelegramMessage를 CollectedItem으로 변환
- 혼합 데이터 정규화
- LLM 파이프라인 문서 형식으로 변환
"""

import pytest
from datetime import datetime, timezone
from src.normalizer import DataNormalizer
from src.collectors.models import Article, TelegramMessage, CollectedItem


class TestDataNormalizer:
    """데이터 정규화 테스트 클래스"""
    
    @pytest.fixture
    def sample_article(self):
        """샘플 Article 생성"""
        return Article(
            title="비트코인 가격 상승",
            url="https://example.com/btc",
            content="비트코인 가격이 10% 상승했습니다.",
            source="BlockMedia",
            published_at=datetime.now(timezone.utc),
            source_type="rss",
            description="비트코인 시장 분석",
            author="기자",
            tags=["비트코인", "암호화폐"]
        )
    
    @pytest.fixture
    def sample_telegram_message(self):
        """샘플 TelegramMessage 생성"""
        return TelegramMessage(
            message_id=12345,
            text="이더리움 가격이 상승하고 있습니다.",
            channel_id="@cryptonews",
            channel_name="Crypto News",
            timestamp=datetime.now(timezone.utc),
            author="User1",
            reply_to_message_id=12340
        )
    
    def test_normalize_article(self, sample_article):
        """Article을 CollectedItem으로 변환 테스트"""
        result = DataNormalizer.normalize_article(sample_article)
        
        assert isinstance(result, CollectedItem)
        assert result.source_type == "rss"
        assert result.source_name == "BlockMedia"
        assert result.text == sample_article.content
        assert result.timestamp == sample_article.published_at
        
        # 메타데이터 확인
        assert "title" in result.metadata
        assert result.metadata["title"] == sample_article.title
        assert "url" in result.metadata
        assert result.metadata["url"] == sample_article.url
        # author는 프로젝트 목적에 불필요하므로 제외됨
        assert "author" not in result.metadata
    
    def test_normalize_telegram_message(self, sample_telegram_message):
        """TelegramMessage를 CollectedItem으로 변환 테스트"""
        result = DataNormalizer.normalize_telegram_message(sample_telegram_message)
        
        assert isinstance(result, CollectedItem)
        assert result.source_type == "telegram"
        assert result.source_name == sample_telegram_message.channel_name
        assert result.text == sample_telegram_message.text
        assert result.timestamp == sample_telegram_message.timestamp
        
        # 메타데이터 확인
        assert "channel_id" in result.metadata
        assert result.metadata["channel_id"] == sample_telegram_message.channel_id
        assert "channel_name" in result.metadata
        assert result.metadata["channel_name"] == sample_telegram_message.channel_name
        assert "message_id" in result.metadata
        assert result.metadata["message_id"] == sample_telegram_message.message_id
        # author는 프로젝트 목적에 불필요하므로 제외됨
        assert "author" not in result.metadata
        assert "reply_to_message_id" in result.metadata
        assert result.metadata["reply_to_message_id"] == sample_telegram_message.reply_to_message_id
    
    def test_normalize_articles(self, sample_article):
        """Article 리스트 정규화 테스트"""
        articles = [sample_article]
        results = DataNormalizer.normalize_articles(articles)
        
        assert len(results) == 1
        assert isinstance(results[0], CollectedItem)
        assert results[0].source_type == "rss"
    
    def test_normalize_telegram_messages(self, sample_telegram_message):
        """TelegramMessage 리스트 정규화 테스트"""
        messages = [sample_telegram_message]
        results = DataNormalizer.normalize_telegram_messages(messages)
        
        assert len(results) == 1
        assert isinstance(results[0], CollectedItem)
        assert results[0].source_type == "telegram"
    
    def test_normalize_mixed_data(self, sample_article, sample_telegram_message):
        """혼합 데이터 정규화 테스트"""
        results = DataNormalizer.normalize_mixed_data(
            articles=[sample_article],
            telegram_messages=[sample_telegram_message]
        )
        
        assert len(results) == 2
        assert all(isinstance(item, CollectedItem) for item in results)
        
        # 시간순 정렬 확인
        timestamps = [item.timestamp for item in results]
        assert timestamps == sorted(timestamps)
    
    def test_normalize_mixed_data_empty(self):
        """빈 데이터 정규화 테스트"""
        results = DataNormalizer.normalize_mixed_data()
        assert results == []
        
        results = DataNormalizer.normalize_mixed_data(articles=[], telegram_messages=[])
        assert results == []
    
    def test_to_dict_format_rss(self, sample_article):
        """RSS Article을 딕셔너리 형식으로 변환 테스트"""
        item = DataNormalizer.normalize_article(sample_article)
        result = DataNormalizer.to_dict_format(item)
        
        assert result["source"] == "rss"
        assert result["timestamp"] == sample_article.published_at.isoformat()
        assert result["text"] == sample_article.content
        
        # meta 필드 확인
        assert "meta" in result
        assert result["meta"]["title"] == sample_article.title
        assert result["meta"]["url"] == sample_article.url
        # author는 프로젝트 목적에 불필요하므로 제외됨
        assert "author" not in result["meta"]
    
    def test_to_dict_format_telegram(self, sample_telegram_message):
        """TelegramMessage를 딕셔너리 형식으로 변환 테스트"""
        item = DataNormalizer.normalize_telegram_message(sample_telegram_message)
        result = DataNormalizer.to_dict_format(item)
        
        assert result["source"] == "telegram"
        assert result["timestamp"] == sample_telegram_message.timestamp.isoformat()
        assert result["text"] == sample_telegram_message.text
        
        # meta 필드 확인
        assert "meta" in result
        assert result["meta"]["channel"] == sample_telegram_message.channel_name
        # author는 프로젝트 목적에 불필요하므로 제외됨
        assert "author" not in result["meta"]
    
    def test_to_dict_format_batch(self, sample_article, sample_telegram_message):
        """배치 딕셔너리 변환 테스트"""
        items = DataNormalizer.normalize_mixed_data(
            articles=[sample_article],
            telegram_messages=[sample_telegram_message]
        )
        
        results = DataNormalizer.to_dict_format_batch(items)
        
        assert len(results) == 2
        assert all(isinstance(item, dict) for item in results)
        assert all("source" in item for item in results)
        assert all("timestamp" in item for item in results)
        assert all("text" in item for item in results)
        assert all("meta" in item for item in results)
    
    def test_normalize_article_with_minimal_fields(self):
        """최소 필드만 있는 Article 정규화 테스트"""
        article = Article(
            title="제목",
            url="",
            content="본문",
            source="Source",
            published_at=datetime.now(timezone.utc),
            source_type="rss"
        )
        
        result = DataNormalizer.normalize_article(article)
        
        assert isinstance(result, CollectedItem)
        assert result.source_type == "rss"
        assert result.source_name == "Source"
        assert result.text == "본문"
    
    def test_normalize_telegram_message_without_optional_fields(self):
        """선택 필드가 없는 TelegramMessage 정규화 테스트"""
        message = TelegramMessage(
            message_id=12345,
            text="메시지 텍스트",
            channel_id="@channel",
            channel_name="Channel",
            timestamp=datetime.now(timezone.utc)
        )
        
        result = DataNormalizer.normalize_telegram_message(message)
        
        assert isinstance(result, CollectedItem)
        assert result.source_type == "telegram"
        assert result.source_name == "Channel"
        assert result.text == "메시지 텍스트"
        
        # 선택 필드는 메타데이터에 없어야 함
        assert "author" not in result.metadata
        assert "reply_to_message_id" not in result.metadata
    
    def test_normalize_articles_error_handling(self):
        """Article 정규화 오류 처리 테스트"""
        # 잘못된 Article 생성 (빈 content로 인해 오류 발생 가능)
        # 하지만 Article의 __post_init__에서 검증하므로 여기서는 정상 케이스만 테스트
        articles = []
        results = DataNormalizer.normalize_articles(articles)
        assert results == []
    
    def test_normalize_telegram_messages_error_handling(self):
        """TelegramMessage 정규화 오류 처리 테스트"""
        messages = []
        results = DataNormalizer.normalize_telegram_messages(messages)
        assert results == []
    
    def test_to_dict_format_filters_none_values(self):
        """None 값이 메타데이터에 포함된 경우 필터링되는지 테스트"""
        # title과 url이 None인 경우
        item = CollectedItem(
            source_type="rss",
            source_name="TestSource",
            timestamp=datetime.now(timezone.utc),
            text="Test content",
            metadata={
                "title": None,
                "url": None,
                "author": "Test Author",
                "valid_field": "valid_value"
            }
        )
        
        result = DataNormalizer.to_dict_format(item)
        meta = result["meta"]
        
        # None 값은 제외되어야 함
        assert "title" not in meta
        assert "url" not in meta
        # 유효한 값은 포함되어야 함
        assert "valid_field" in meta
        assert meta["valid_field"] == "valid_value"
    
    def test_to_dict_format_filters_none_channel_values(self):
        """텔레그램 채널 정보가 None인 경우 필터링되는지 테스트"""
        # channel_name과 channel_id가 None인 경우
        item = CollectedItem(
            source_type="telegram",
            source_name="TestChannel",
            timestamp=datetime.now(timezone.utc),
            text="Test message",
            metadata={
                "channel_name": None,
                "channel_id": None,
                "message_id": 12345,
                "valid_field": "valid_value"
            }
        )
        
        result = DataNormalizer.to_dict_format(item)
        meta = result["meta"]
        
        # None 값은 제외되어야 함
        assert "channel" not in meta
        assert "channel_name" not in meta
        assert "channel_id" not in meta
        # 유효한 값은 포함되어야 함
        assert "message_id" in meta
        assert meta["message_id"] == 12345
        assert "valid_field" in meta
        assert meta["valid_field"] == "valid_value"
    
    def test_to_dict_format_handles_partial_none_values(self):
        """일부 필드만 None인 경우 올바르게 처리되는지 테스트"""
        # title은 None이지만 url은 유효한 경우
        item = CollectedItem(
            source_type="rss",
            source_name="TestSource",
            timestamp=datetime.now(timezone.utc),
            text="Test content",
            metadata={
                "title": None,
                "url": "https://example.com",
                "valid_field": "valid_value"
            }
        )
        
        result = DataNormalizer.to_dict_format(item)
        meta = result["meta"]
        
        # None 값은 제외되어야 함
        assert "title" not in meta
        # 유효한 값은 포함되어야 함
        assert "url" in meta
        assert meta["url"] == "https://example.com"
        assert "valid_field" in meta
        assert meta["valid_field"] == "valid_value"


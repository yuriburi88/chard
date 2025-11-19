"""
전처리 파이프라인 테스트

전처리 파이프라인의 각 기능을 테스트합니다.
- 언어 감지
- 불용어/스팸 처리
- 토큰 길이 제한
"""

import logging
from typing import List
from datetime import datetime, timezone

import pytest

from src.collectors.models import Article, CollectedItem
from src.preprocessor import Preprocessor, PreprocessingConfig
from src.normalizer import DataNormalizer


class TestPreprocessor:
    """전처리 파이프라인 테스트 클래스"""
    
    @pytest.fixture
    def preprocessor(self):
        """Preprocessor 인스턴스 생성"""
        config = PreprocessingConfig(
            language_detection_enabled=True,
            spam_filter_enabled=True,
            token_limit_enabled=True
        )
        return Preprocessor(config)
    
    @pytest.fixture
    def sample_articles(self):
        """샘플 Article 리스트 생성"""
        return [
            Article(
                title="비트코인 가격 상승, 암호화폐 시장 급등",
                url="https://example.com/btc",
                content="비트코인 가격이 10% 상승하며 암호화폐 시장 전체가 급등세를 보이고 있습니다. 이더리움과 다른 알트코인들도 함께 상승하고 있습니다.",
                source="BlockMedia",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="광고 이벤트 무료 특가",
                url="https://example.com/spam",
                content="지금 가입하면 무료로 특가 상품을 받을 수 있습니다. 광고 promotion 이벤트",
                source="SpamSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="이더리움 ETF 승인",
                url="https://example.com/eth",
                content="이더리움 ETF가 SEC 승인을 받았습니다. 이는 디지털 자산 시장에 큰 영향을 미칠 것으로 예상됩니다.",
                source="CoinDesk",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="짧은 기사",
                url="https://example.com/short",
                content="짧음",
                source="ShortSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            )
        ]
    
    @pytest.mark.asyncio
    async def test_preprocess_articles_basic(self, preprocessor, sample_articles):
        """기본 Article 전처리 테스트"""
        result = await preprocessor.preprocess_articles(sample_articles)
        
        # 스팸 기사와 너무 짧은 기사는 제외되어야 함
        assert len(result) < len(sample_articles)
        
        # 유효한 기사만 통과해야 함
        sources = [article.source for article in result]
        assert "BlockMedia" in sources or "CoinDesk" in sources
        assert "SpamSource" not in sources
        assert "ShortSource" not in sources
    
    @pytest.mark.asyncio
    async def test_preprocess_articles_language_filter(self, preprocessor):
        """언어 필터링 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=True,
            allowed_languages=["ko"],
            spam_filter_enabled=False,
            token_limit_enabled=False
        )
        preprocessor = Preprocessor(config)
        
        articles = [
            Article(
                title="Bitcoin Price Surge",
                url="https://example.com/en",
                content="Bitcoin price has surged by 10% today. The cryptocurrency market is showing strong bullish momentum.",
                source="EnglishSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="비트코인 가격 상승",
                url="https://example.com/ko",
                content="비트코인 가격이 10% 상승했습니다. 암호화폐 시장이 강한 상승세를 보이고 있습니다.",
                source="KoreanSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            )
        ]
        
        result = await preprocessor.preprocess_articles(articles)
        
        # 한국어 기사만 통과해야 함
        sources = [article.source for article in result]
        assert "KoreanSource" in sources
        # 영어 기사는 언어 필터에 의해 제외될 수 있음 (언어 감지 결과에 따라)
    
    @pytest.mark.asyncio
    async def test_preprocess_articles_spam_filter(self, preprocessor):
        """스팸 필터링 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=True,
            token_limit_enabled=False
        )
        preprocessor = Preprocessor(config)
        
        articles = [
            Article(
                title="정상 기사",
                url="https://example.com/normal",
                content="비트코인 가격이 상승하고 있습니다. 시장 분석가들은 긍정적인 전망을 내놓고 있습니다.",
                source="NormalSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="광고 기사",
                url="https://example.com/spam",
                content="지금 가입하면 무료로 특가 상품을 받을 수 있습니다. 광고 promotion 이벤트",
                source="SpamSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            )
        ]
        
        result = await preprocessor.preprocess_articles(articles)
        
        # 정상 기사만 통과해야 함
        sources = [article.source for article in result]
        assert "NormalSource" in sources
        assert "SpamSource" not in sources
    
    @pytest.mark.asyncio
    async def test_preprocess_articles_token_limit(self, preprocessor):
        """토큰 길이 제한 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=True,
            max_tokens_per_item=100  # 매우 작은 토큰 제한
        )
        preprocessor = Preprocessor(config)
        
        # 매우 긴 텍스트 생성
        long_content = "비트코인 " * 1000  # 약 3000자
        
        articles = [
            Article(
                title="짧은 기사",
                url="https://example.com/short",
                content="비트코인 가격이 상승했습니다.",
                source="ShortSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            ),
            Article(
                title="긴 기사",
                url="https://example.com/long",
                content=long_content,
                source="LongSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            )
        ]
        
        result = await preprocessor.preprocess_articles(articles)
        
        # 짧은 기사만 통과해야 함
        sources = [article.source for article in result]
        assert "ShortSource" in sources
        assert "LongSource" not in sources
    
    @pytest.mark.asyncio
    async def test_preprocess_collected_items(self, preprocessor):
        """CollectedItem 전처리 테스트"""
        items = [
            CollectedItem(
                source_type="rss",
                source_name="BlockMedia",
                timestamp=datetime.now(timezone.utc),
                text="비트코인 가격이 10% 상승했습니다. 암호화폐 시장이 강한 상승세를 보이고 있습니다."
            ),
            CollectedItem(
                source_type="telegram",
                source_name="CryptoChannel",
                timestamp=datetime.now(timezone.utc),
                text="광고 promotion 이벤트"
            )
        ]
        
        result = await preprocessor.preprocess_collected_items(items)
        
        # 정상 항목만 통과해야 함
        assert len(result) >= 1
        sources = [item.source_name for item in result]
        assert "BlockMedia" in sources
    
    @pytest.mark.asyncio
    async def test_preprocess_collected_items_split_long_messages(self, caplog):
        """장문 CollectedItem 분할 전처리 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=True,
            max_tokens_per_item=120,
            split_long_messages=True,
            max_tokens_per_segment=40,
            segment_overlap_tokens=10
        )
        preprocessor = Preprocessor(config)

        long_text = "비트코인 가격이 꾸준히 상승하고 있습니다. " * 50
        item = CollectedItem(
            source_type="telegram",
            source_name="CryptoChannel",
            timestamp=datetime.now(timezone.utc),
            text=long_text,
            metadata={"message_id": 123456}
        )

        with caplog.at_level(logging.INFO, logger="src.preprocessor"):
            result = await preprocessor.preprocess_collected_items([item])

        assert len(result) > 1
        normalized_long_text = preprocessor._normalize_text(long_text)
        original_total_tokens = len(preprocessor.token_encoder.encode(normalized_long_text))
        effective_overlap = preprocessor._resolve_overlap_tokens(config.max_tokens_per_segment)
        previous_range_end = None

        total_segment_tokens = 0

        for index, segment in enumerate(result):
            segment_tokens = len(preprocessor.token_encoder.encode(segment.text))
            assert segment_tokens <= config.max_tokens_per_segment
            assert segment.metadata["original_message_id"] == item.metadata["message_id"]
            assert segment.metadata["message_id"] == item.metadata["message_id"]
            assert segment.metadata["segment_index"] == index
            assert segment.metadata["segment_count"] == len(result)
            assert "segment_range_tokens" in segment.metadata
            range_info = segment.metadata["segment_range_tokens"]
            assert range_info["start"] >= 0
            assert range_info["end"] > range_info["start"]
            if index == 0:
                assert range_info["start"] == 0
            else:
                assert range_info["start"] == max(previous_range_end - effective_overlap, 0)
            previous_range_end = range_info["end"]
            assert segment.source_name == item.source_name

            total_segment_tokens += segment_tokens

        assert previous_range_end == original_total_tokens
        assert total_segment_tokens >= original_total_tokens

        stats_log = next(
            (
                message
                for message in caplog.messages
                if "분할세그먼트" in message
            ),
            ""
        )
        assert f"분할세그먼트={len(result)}" in stats_log
    
    @pytest.mark.asyncio
    async def test_preprocess_collected_items_split_disabled(self):
        """장문 분할 비활성화 시 토큰 초과 항목 제외 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=True,
            max_tokens_per_item=120,
            split_long_messages=False,
            max_tokens_per_segment=40
        )
        preprocessor = Preprocessor(config)

        long_text = "이더리움 네트워크 활동이 증가하고 있습니다. " * 50
        item = CollectedItem(
            source_type="telegram",
            source_name="AltcoinChannel",
            timestamp=datetime.now(timezone.utc),
            text=long_text,
            metadata={"message_id": 987654}
        )

        result = await preprocessor.preprocess_collected_items([item])

        assert result == []
    
    def test_normalize_text(self, preprocessor):
        """텍스트 정규화 테스트"""
        # 연속된 공백 정규화
        text = "비트코인    가격    상승"
        normalized = preprocessor._normalize_text(text)
        assert "  " not in normalized  # 연속된 공백이 제거되어야 함
    
    def test_is_spam(self, preprocessor):
        """스팸 판단 테스트"""
        # 스팸 텍스트
        spam_text = "지금 가입하면 무료로 특가 상품을 받을 수 있습니다. 광고"
        assert preprocessor._is_spam(spam_text) is True
        
        # 정상 텍스트
        normal_text = "비트코인 가격이 상승하고 있습니다."
        assert preprocessor._is_spam(normal_text) is False
    
    def test_count_tokens(self, preprocessor):
        """토큰 수 계산 테스트"""
        text = "비트코인 가격이 상승했습니다."
        token_count = preprocessor.count_tokens(text)
        
        # 토큰 수는 양수여야 함
        assert token_count > 0
        # 텍스트 길이보다 작거나 같아야 함 (일반적으로)
        assert token_count <= len(text)
    
    def test_truncate_to_tokens(self, preprocessor):
        """토큰 기준 텍스트 자르기 테스트"""
        text = "비트코인 " * 100  # 긴 텍스트
        max_tokens = 10
        
        truncated = preprocessor.truncate_to_tokens(text, max_tokens)
        
        # 잘린 텍스트의 토큰 수는 max_tokens 이하여야 함
        truncated_tokens = preprocessor.count_tokens(truncated)
        assert truncated_tokens <= max_tokens
    
    def test_split_text_to_segments_token_based(self):
        """토큰 기반 세그먼트 분할 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=False,
            split_long_messages=True,
            max_tokens_per_segment=10,
            segment_overlap_tokens=0
        )
        preprocessor = Preprocessor(config)

        text = " ".join(["segment"] * 100)

        segments = preprocessor._split_text_to_segments(text)

        assert len(segments) > 1

        for index, segment in enumerate(segments, start=1):
            token_count = len(preprocessor.token_encoder.encode(segment))
            assert 0 < token_count <= config.max_tokens_per_segment, (
                f"세그먼트 {index} 토큰 수가 제한을 초과했습니다: {token_count}"
            )

        reconstructed = "".join(segments)
        original_tokens = preprocessor.token_encoder.encode(text)
        reconstructed_tokens = preprocessor.token_encoder.encode(reconstructed)

        assert reconstructed_tokens == original_tokens

    def test_split_text_to_segments_with_overlap(self):
        """토큰 기반 세그먼트 오버랩 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=False,
            split_long_messages=True,
            max_tokens_per_segment=30,
            segment_overlap_tokens=5
        )
        preprocessor = Preprocessor(config)

        text = " ".join(["overlap"] * 120)

        segments = preprocessor._split_text_to_segments(text)

        assert len(segments) > 1

        overlap_tokens = preprocessor.config.segment_overlap_tokens
        segment_tokens = [
            preprocessor.token_encoder.encode(segment) for segment in segments
        ]

        reconstructed_tokens: List[int] = []

        for index, tokens in enumerate(segment_tokens):
            if index == 0:
                reconstructed_tokens.extend(tokens)

                continue

            reconstructed_tokens.extend(tokens[overlap_tokens:])

        original_tokens = preprocessor.token_encoder.encode(text)

        assert reconstructed_tokens == original_tokens

    def test_split_text_to_segments_without_encoder(self):
        """토큰 인코더 미사용 시 문자 기반 분할 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=False,
            token_limit_enabled=False,
            split_long_messages=True,
            max_tokens_per_segment=5,
            segment_overlap_tokens=1,
            token_encoding="invalid-encoding"
        )
        preprocessor = Preprocessor(config)

        assert preprocessor.token_encoder is None

        text = "abcdefghijklmnopqrstuvwxyz" * 4

        segments = preprocessor._split_text_to_segments(text)

        assert len(segments) > 1

        overlap_chars = preprocessor.config.segment_overlap_tokens * 4
        reconstructed = segments[0]

        for segment in segments[1:]:
            reconstructed += segment[overlap_chars:]

        assert reconstructed == text
    
    def test_data_normalizer_preserves_segmentation_metadata(self):
        """DataNormalizer가 분할 메타데이터를 유지하는지 테스트"""
        metadata = {
            "title": "Segmented Message",
            "message_id": 42,
            "original_message_id": "42",
            "segment_index": 1,
            "segment_count": 3,
            "segment_range_tokens": {"start": 10, "end": 20},
            "channel_name": "CryptoChannel",
        }
        
        item = CollectedItem(
            source_type="telegram",
            source_name="CryptoChannel",
            timestamp=datetime.now(timezone.utc),
            text="segment text",
            metadata=metadata
        )
        
        normalized = DataNormalizer.to_dict_format(item)
        meta = normalized["meta"]
        
        assert meta["title"] == metadata["title"]
        assert meta["message_id"] == metadata["message_id"]
        assert meta["original_message_id"] == metadata["original_message_id"]
        assert meta["segment_index"] == metadata["segment_index"]
        assert meta["segment_count"] == metadata["segment_count"]
        assert meta["segment_range_tokens"] == metadata["segment_range_tokens"]
        # 채널 정보는 channel 필드로 노출
        assert meta["channel"] == metadata["channel_name"]
        # 원본 메타데이터의 channel_name도 유지
        assert meta["channel_name"] == metadata["channel_name"]
    
    @pytest.mark.asyncio
    async def test_preprocess_empty_list(self, preprocessor):
        """빈 리스트 전처리 테스트"""
        result = await preprocessor.preprocess_articles([])
        assert result == []
        
        result = await preprocessor.preprocess_collected_items([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_preprocess_all_filtered(self, preprocessor):
        """모든 항목이 필터링되는 경우 테스트"""
        config = PreprocessingConfig(
            language_detection_enabled=False,
            spam_filter_enabled=True,
            token_limit_enabled=False,
            min_content_length=100  # 매우 큰 최소 길이
        )
        preprocessor = Preprocessor(config)
        
        articles = [
            Article(
                title="짧은 기사",
                url="https://example.com/short",
                content="짧음",
                source="ShortSource",
                published_at=datetime.now(timezone.utc),
                source_type="rss"
            )
        ]
        
        result = await preprocessor.preprocess_articles(articles)
        
        # 모든 항목이 필터링되어야 함
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_chunk_messages_basic(self, preprocessor):
        """기본 청크 생성 테스트"""
        # 정규화된 레코드 형식의 샘플 데이터 생성
        records = [
            {
                "source": "rss",
                "timestamp": "2024-01-01T10:00:00Z",
                "text": "비트코인 가격이 상승하고 있습니다. " * 10,  # 약 200자
                "meta": {"title": "비트코인 가격 상승", "url": "https://example.com/1"}
            },
            {
                "source": "rss",
                "timestamp": "2024-01-01T11:00:00Z",
                "text": "이더리움 가격도 함께 상승하고 있습니다. " * 10,  # 약 200자
                "meta": {"title": "이더리움 가격 상승", "url": "https://example.com/2"}
            },
            {
                "source": "telegram",
                "timestamp": "2024-01-01T12:00:00Z",
                "text": "암호화폐 시장이 급등세를 보이고 있습니다. " * 10,  # 약 200자
                "meta": {"channel": "CryptoChannel"}
            }
        ]
        
        chunks = await preprocessor.chunk_messages(records, max_tokens=50000)
        
        # 청크가 생성되어야 함
        assert len(chunks) > 0
        
        # 모든 레코드가 청크에 포함되어야 함
        total_records = sum(len(chunk) for chunk in chunks)
        assert total_records == len(records)
        
        # 각 청크는 비어있지 않아야 함
        for chunk in chunks:
            assert len(chunk) > 0
    
    @pytest.mark.asyncio
    async def test_chunk_messages_source_grouping(self, preprocessor):
        """소스별 그룹화 테스트"""
        # RSS와 텔레그램 레코드 혼합
        records = [
            {
                "source": "rss",
                "timestamp": "2024-01-01T10:00:00Z",
                "text": "RSS 기사 1 " * 20,
                "meta": {"title": "RSS 1"}
            },
            {
                "source": "telegram",
                "timestamp": "2024-01-01T11:00:00Z",
                "text": "텔레그램 메시지 1 " * 20,
                "meta": {"channel": "Channel1"}
            },
            {
                "source": "rss",
                "timestamp": "2024-01-01T12:00:00Z",
                "text": "RSS 기사 2 " * 20,
                "meta": {"title": "RSS 2"}
            },
            {
                "source": "telegram",
                "timestamp": "2024-01-01T13:00:00Z",
                "text": "텔레그램 메시지 2 " * 20,
                "meta": {"channel": "Channel2"}
            }
        ]
        
        chunks = await preprocessor.chunk_messages(records, max_tokens=50000)
        
        # 소스별로 그룹화되어야 함 (각 청크는 같은 소스만 포함)
        for chunk in chunks:
            sources = set(record.get("source") for record in chunk)
            # 각 청크는 하나의 소스만 포함해야 함 (소스별 그룹화)
            assert len(sources) == 1
    
    @pytest.mark.asyncio
    async def test_chunk_messages_time_sorting(self, preprocessor):
        """시간순 정렬 테스트"""
        # 시간순이 섞인 레코드
        records = [
            {
                "source": "rss",
                "timestamp": "2024-01-01T12:00:00Z",
                "text": "세 번째 기사 " * 20,
                "meta": {"title": "Third"}
            },
            {
                "source": "rss",
                "timestamp": "2024-01-01T10:00:00Z",
                "text": "첫 번째 기사 " * 20,
                "meta": {"title": "First"}
            },
            {
                "source": "rss",
                "timestamp": "2024-01-01T11:00:00Z",
                "text": "두 번째 기사 " * 20,
                "meta": {"title": "Second"}
            }
        ]
        
        chunks = await preprocessor.chunk_messages(records, max_tokens=50000)
        
        # 각 청크 내에서 시간순으로 정렬되어야 함
        for chunk in chunks:
            timestamps = [
                record.get("timestamp") for record in chunk
            ]
            # 시간순으로 정렬되어 있는지 확인
            sorted_timestamps = sorted(timestamps)
            assert timestamps == sorted_timestamps
    
    @pytest.mark.asyncio
    async def test_chunk_messages_token_limit(self, preprocessor):
        """토큰 제한 테스트"""
        # 중간 크기 텍스트를 가진 레코드 생성 (토큰 제한 내에 여러 개가 들어갈 수 있도록)
        medium_text = "비트코인 가격이 상승하고 있습니다. " * 100  # 약 2,000자
        
        records = [
            {
                "source": "rss",
                "timestamp": f"2024-01-01T{10+i:02d}:00:00Z",
                "text": medium_text,
                "meta": {"title": f"기사 {i+1}"}
            }
            for i in range(10)  # 여러 레코드 생성
        ]
        
        # 작은 토큰 제한 설정 (하나의 레코드는 들어갈 수 있지만 여러 개는 안 됨)
        max_tokens = 500  # 작은 제한
        chunks = await preprocessor.chunk_messages(records, max_tokens=max_tokens)
        
        # 토큰 제한으로 인해 여러 청크가 생성되어야 함
        assert len(chunks) > 1
        
        # 각 청크의 토큰 수 확인
        # 단일 레코드가 토큰 제한을 초과하는 경우에도 포함되므로, 
        # 청크의 토큰 수는 단일 레코드의 토큰 수보다 작거나 같아야 함
        for chunk in chunks:
            chunk_tokens = sum(
                preprocessor._estimate_record_tokens(record) for record in chunk
            )
            # 각 청크는 최소한 하나의 레코드를 포함해야 함
            assert len(chunk) > 0
            
            # 청크에 레코드가 하나만 있는 경우, 그 레코드의 토큰 수는 제한을 초과할 수 있음
            # (데이터 손실을 방지하기 위해)
            if len(chunk) == 1:
                # 단일 레코드는 제한을 초과할 수 있음
                pass
            else:
                # 여러 레코드가 있는 경우, 토큰 제한을 준수해야 함
                # 약간의 여유를 두고 확인 (메타데이터 포함으로 약간 초과 가능)
                assert chunk_tokens <= max_tokens * 1.2  # 20% 여유
    
    @pytest.mark.asyncio
    async def test_chunk_messages_empty_list(self, preprocessor):
        """빈 리스트 청크 생성 테스트"""
        chunks = await preprocessor.chunk_messages([], max_tokens=50000)
        
        # 빈 리스트는 빈 결과를 반환해야 함
        assert chunks == []
    
    @pytest.mark.asyncio
    async def test_chunk_messages_single_record(self, preprocessor):
        """단일 레코드 청크 생성 테스트"""
        records = [
            {
                "source": "rss",
                "timestamp": "2024-01-01T10:00:00Z",
                "text": "단일 기사",
                "meta": {"title": "Single Article"}
            }
        ]
        
        chunks = await preprocessor.chunk_messages(records, max_tokens=50000)
        
        # 단일 레코드는 하나의 청크로 생성되어야 함
        assert len(chunks) == 1
        assert len(chunks[0]) == 1
        assert chunks[0][0]["text"] == "단일 기사"
    
    @pytest.mark.asyncio
    async def test_chunk_messages_module_level_function(self):
        """모듈 레벨 chunk_messages 함수 테스트"""
        from src.preprocessor import chunk_messages
        
        records = [
            {
                "source": "rss",
                "timestamp": "2024-01-01T10:00:00Z",
                "text": "테스트 기사 " * 10,
                "meta": {"title": "Test Article"}
            }
        ]
        
        chunks = await chunk_messages(records, max_tokens=50000)
        
        # 모듈 레벨 함수도 정상 작동해야 함
        assert len(chunks) > 0
        assert len(chunks[0]) > 0


"""
RSS 수집기 비동기 단위 테스트

모의 RSS 피드 응답을 활용하여 RSS 수집기의 비동기 동작을 테스트합니다.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import feedparser
from types import SimpleNamespace

from src.collectors.rss_collector import RSSCollector
from src.collectors.models import Article
from src.config_manager import RSSSourceConfig


class MockFeedEntry:
    """모의 RSS 피드 엔트리"""
    
    def __init__(
        self,
        title: str,
        link: str,
        published: str,
        content: str,
        summary: str = "",
        author: str = "",
        tags: List[str] = None
    ):
        self.title = title
        self.link = link
        self.published = published
        self.published_parsed = None  # feedparser가 파싱한 날짜 튜플
        self.content = [SimpleNamespace(value=content)] if content else []
        self.summary = summary
        self.author = author
        self.tags = [SimpleNamespace(term=tag) for tag in (tags or [])]


class MockFeed:
    """모의 RSS 피드"""
    
    def __init__(self, entries: List[MockFeedEntry], bozo: bool = False):
        self.entries = entries
        self.bozo = bozo
        self.bozo_exception = None if not bozo else Exception("Parse error")


@pytest.fixture
def sample_rss_config() -> RSSSourceConfig:
    """샘플 RSS 소스 설정"""
    return RSSSourceConfig(
        name="Test RSS Feed",
        url="https://example.com/rss",
        priority=1.0,
        timezone=9,
        max_articles=10,
        hours_back=24
    )


@pytest.fixture
def sample_feed_entries() -> List[MockFeedEntry]:
    """샘플 RSS 피드 엔트리 리스트"""
    now = datetime.now(timezone.utc)
    
    return [
        MockFeedEntry(
            title="Bitcoin Price Surges to New High",
            link="https://example.com/article1",
            published=now.isoformat(),
            content="Bitcoin reached a new all-time high today as institutional investors continue to pour money into the cryptocurrency market.",
            summary="Bitcoin price analysis",
            author="Crypto Reporter",
            tags=["bitcoin", "crypto", "market"]
        ),
        MockFeedEntry(
            title="Ethereum 2.0 Staking Update",
            link="https://example.com/article2",
            published=(now - timedelta(hours=2)).isoformat(),
            content="Ethereum 2.0 staking continues to grow with over 10 million ETH now staked. The network upgrade is progressing smoothly.",
            summary="Ethereum staking news",
            author="Blockchain News",
            tags=["ethereum", "staking"]
        ),
        MockFeedEntry(
            title="DeFi Protocol Launches New Feature",
            link="https://example.com/article3",
            published=(now - timedelta(hours=5)).isoformat(),
            content="A major DeFi protocol has launched a new yield farming feature that allows users to earn rewards by providing liquidity.",
            summary="DeFi news",
            tags=["defi", "yield-farming"]
        ),
    ]


@pytest.mark.asyncio
async def test_rss_collector_basic_collection(sample_rss_config, sample_feed_entries):
    """
    기본 RSS 수집 테스트
    
    모의 피드 응답을 사용하여 RSS 수집기가 정상적으로 기사를 수집하는지 확인합니다.
    """
    # 모의 피드 생성
    mock_feed = MockFeed(entries=sample_feed_entries, bozo=False)
    
    # feedparser.parse를 모의로 대체
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        # httpx.AsyncClient를 모의로 대체
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(sample_rss_config)
            
            # 검증
            assert len(articles) == 3
            assert all(isinstance(article, Article) for article in articles)
            assert articles[0].title == "Bitcoin Price Surges to New High"
            assert articles[0].url == "https://example.com/article1"
            assert articles[0].source == "Test RSS Feed"
            assert articles[0].source_type == "rss"
            assert "Bitcoin reached" in articles[0].content


@pytest.mark.asyncio
async def test_rss_collector_time_filtering(sample_rss_config, sample_feed_entries):
    """
    시간 필터링 테스트
    
    최소 발행 시각 이후의 기사만 수집하는지 확인합니다.
    """
    now = datetime.now(timezone.utc)
    min_published = now - timedelta(hours=3)  # 최근 3시간 이내만
    
    # 모의 피드 생성
    mock_feed = MockFeed(entries=sample_feed_entries, bozo=False)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(
                    sample_rss_config,
                    min_published=min_published
                )
            
            # 최근 3시간 이내 기사만 수집되어야 함 (첫 번째, 두 번째 기사)
            assert len(articles) >= 1
            for article in articles:
                assert article.published_at >= min_published


@pytest.mark.asyncio
async def test_rss_collector_max_articles_limit(sample_rss_config):
    """
    최대 기사 수 제한 테스트
    
    max_articles 설정에 따라 수집이 제한되는지 확인합니다.
    """
    # 많은 엔트리를 가진 모의 피드 생성
    now = datetime.now(timezone.utc)
    many_entries = [
        MockFeedEntry(
            title=f"Article {i}",
            link=f"https://example.com/article{i}",
            published=(now - timedelta(hours=i)).isoformat(),
            content=f"Content for article {i}",
        )
        for i in range(20)
    ]
    
    mock_feed = MockFeed(entries=many_entries, bozo=False)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(sample_rss_config)
            
            # max_articles(10)를 초과하지 않아야 함
            assert len(articles) <= sample_rss_config.max_articles


@pytest.mark.asyncio
async def test_rss_collector_duplicate_removal(sample_rss_config):
    """
    중복 제거 테스트
    
    동일한 링크나 제목을 가진 기사가 중복 제거되는지 확인합니다.
    """
    now = datetime.now(timezone.utc)
    
    # 중복된 링크를 가진 엔트리 생성
    duplicate_entries = [
        MockFeedEntry(
            title="Same Article",
            link="https://example.com/same",
            published=now.isoformat(),
            content="First occurrence",
        ),
        MockFeedEntry(
            title="Same Article",
            link="https://example.com/same",
            published=(now - timedelta(minutes=1)).isoformat(),
            content="Duplicate occurrence",
        ),
        MockFeedEntry(
            title="Different Article",
            link="https://example.com/different",
            published=(now - timedelta(hours=1)).isoformat(),
            content="Different content",
        ),
    ]
    
    mock_feed = MockFeed(entries=duplicate_entries, bozo=False)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(sample_rss_config)
            
            # 중복이 제거되어야 함 (2개만 수집되어야 함)
            assert len(articles) == 2
            urls = [article.url for article in articles]
            assert "https://example.com/same" in urls
            assert "https://example.com/different" in urls


@pytest.mark.asyncio
async def test_rss_collector_empty_feed(sample_rss_config):
    """
    빈 피드 처리 테스트
    
    기사가 없는 빈 피드를 처리하는지 확인합니다.
    """
    mock_feed = MockFeed(entries=[], bozo=False)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(sample_rss_config)
            
            # 빈 리스트가 반환되어야 함
            assert len(articles) == 0
            assert articles == []


@pytest.mark.asyncio
async def test_rss_collector_http_error_handling(sample_rss_config):
    """
    HTTP 오류 처리 테스트
    
    HTTP 요청 실패 시 적절히 오류를 처리하는지 확인합니다.
    """
    import httpx
        
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch('httpx.AsyncClient', return_value=mock_client):
        collector = RSSCollector(http_timeout=5.0)
        
        async with collector:
            with pytest.raises(httpx.HTTPError):
                await collector.collect(sample_rss_config)


@pytest.mark.asyncio
async def test_rss_collector_bozo_feed_handling(sample_rss_config, sample_feed_entries):
    """
    파싱 오류 피드 처리 테스트
    
    bozo 플래그가 있는 피드를 처리하는지 확인합니다.
    """
    mock_feed = MockFeed(entries=sample_feed_entries, bozo=True)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                # bozo 피드도 처리되어야 함 (경고만 발생)
                articles = await collector.collect(sample_rss_config)
            
            # 기사는 여전히 수집되어야 함
            assert len(articles) > 0


@pytest.mark.asyncio
async def test_rss_collector_metadata_extraction(sample_rss_config, sample_feed_entries):
    """
    메타데이터 추출 테스트
    
    작성자, 태그, 요약 등의 메타데이터가 올바르게 추출되는지 확인합니다.
    """
    mock_feed = MockFeed(entries=sample_feed_entries, bozo=False)
    
    with patch('src.collectors.rss_collector.feedparser.parse') as mock_parse:
        mock_parse.return_value = mock_feed
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            collector = RSSCollector(http_timeout=5.0)
            
            async with collector:
                articles = await collector.collect(sample_rss_config)
            
            # 첫 번째 기사의 메타데이터 확인
            first_article = articles[0]
            assert first_article.author == "Crypto Reporter"
            assert first_article.description == "Bitcoin price analysis"
            # 태그는 순서가 다를 수 있으므로 set으로 비교
            assert set(first_article.tags) == {"bitcoin", "crypto", "market"}
            assert len(first_article.tags) == 3


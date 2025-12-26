"""
비동기 RSS 수집기

RSS 피드에서 기사를 비동기로 수집하는 모듈입니다.
- httpx를 사용한 비동기 HTTP 요청
- feedparser를 asyncio.to_thread로 래핑하여 비동기 처리
- 중복 제거 및 메타데이터 표준화
- 상세한 로깅
"""

import asyncio
import html
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import feedparser
import httpx
from dateutil import parser as date_parser

from src.collectors.base import BaseCollector
from src.collectors.models import Article
from src.config_manager import RSSSourceConfig


logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """
    비동기 RSS 수집기

    RSS 피드에서 기사를 수집하고, 중복을 제거하며, 메타데이터를 표준화합니다.
    """

    def __init__(self, http_timeout: float = 30.0):
        """
        RSS 수집기 초기화

        Args:
            http_timeout: HTTP 요청 타임아웃 (초)
        """
        self.http_timeout = http_timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self._client = httpx.AsyncClient(timeout=self.http_timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_source_type(self) -> str:
        """소스 타입 반환"""
        return "rss"

    async def collect(
        self, config: RSSSourceConfig, min_published: datetime | None = None
    ) -> list[Article]:
        """
        RSS 피드에서 기사를 수집합니다.

        Args:
            config: RSS 소스 설정
            min_published: 최소 발행 시각 (이 시각 이후 기사만 수집, None이면 필터링 안 함)

        Returns:
            수집된 기사 리스트 (Article 객체)
        """
        logger.info(f"[RSS 수집 시작] 소스: {config.name}, URL: {config.url}")
        logger.info(
            f"[RSS 수집 설정] max_articles={config.max_articles}, hours_back={config.hours_back}, timezone=UTC+{config.timezone}"
        )

        # HTTP 클라이언트가 없으면 생성
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.http_timeout)

        try:
            # RSS 피드 가져오기 및 파싱
            feed = await self._fetch_feed(config.url)

            if feed.bozo:
                logger.warning(
                    f"[RSS 피드 파싱 경고] {config.name}: {feed.bozo_exception}"
                )

            if not feed.entries:
                logger.warning(f"[RSS 피드 비어있음] {config.name}: 기사가 없습니다.")
                return []

            logger.info(
                f"[RSS 피드 파싱 완료] {config.name}: {len(feed.entries)}개 엔트리 발견"
            )

            # 엔트리 파싱
            articles: list[Article] = []
            seen_keys: set[str] = set()

            # 최소 발행 시각 계산 (시간대 고려)
            if min_published is None:
                # hours_back을 기준으로 계산
                min_published = datetime.now(timezone.utc) - timedelta(
                    hours=config.hours_back
                )
                logger.info(
                    f"[RSS 시간 필터] 최소 발행 시각: {min_published.isoformat()} (최근 {config.hours_back}시간)"
                )

            # 엔트리 처리
            for idx, entry in enumerate(feed.entries):
                # 최대 기사 수 확인
                if len(articles) >= config.max_articles:
                    logger.info(
                        f"[RSS 수집 중단] {config.name}: 최대 기사 수({config.max_articles}) 도달"
                    )
                    break

                try:
                    # 엔트리 파싱
                    article = self._parse_entry(entry, config, min_published)

                    if article is None:
                        continue

                    # 중복 확인
                    unique_key = article.get_unique_key()
                    if unique_key in seen_keys:
                        logger.debug(
                            f"[RSS 중복 제거] {config.name}: {article.title[:50]}..."
                        )
                        continue
                    seen_keys.add(unique_key)

                    articles.append(article)
                    logger.info(
                        f"[RSS 기사 수집] {config.name} [{len(articles)}/{config.max_articles}]: {article.title}"
                    )
                    logger.debug(
                        f"[RSS 기사 상세] URL: {article.url}, 발행: {article.published_at.isoformat()}, 본문 길이: {len(article.content)}자"
                    )

                except Exception as e:
                    logger.error(
                        f"[RSS 엔트리 파싱 실패] {config.name} 엔트리 {idx+1}: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"[RSS 수집 완료] {config.name}: 총 {len(articles)}개 기사 수집"
            )

            # 수집된 기사 상세 로그
            if articles:
                logger.info(f"[RSS 수집 결과 상세] {config.name}:")
                for i, article in enumerate(articles, 1):
                    logger.info(f"  [{i}] 제목: {article.title}")
                    logger.info(f"      URL: {article.url}")
                    logger.info(f"      발행: {article.published_at.isoformat()}")
                    logger.info(f"      본문 길이: {len(article.content)}자")
                    if article.description:
                        logger.info(f"      요약: {article.description[:100]}...")
                    logger.info("")

            return articles

        except Exception as e:
            logger.error(f"[RSS 수집 오류] {config.name}: {e}", exc_info=True)
            raise

    async def _fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        """
        비동기로 RSS 피드를 가져와 파싱합니다.

        Args:
            url: RSS 피드 URL

        Returns:
            파싱된 피드 객체
        """
        logger.debug(f"[RSS HTTP 요청] URL: {url}")

        try:
            # 비동기 HTTP 요청
            response = await self._client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()

            logger.debug(
                f"[RSS HTTP 응답] 상태 코드: {response.status_code}, 본문 길이: {len(response.content)} bytes"
            )

            # feedparser는 동기 라이브러리이므로 asyncio.to_thread로 래핑
            feed = await asyncio.to_thread(feedparser.parse, response.content)

            logger.debug(
                f"[RSS 피드 파싱] 엔트리 수: {len(feed.entries) if feed.entries else 0}"
            )

            return feed

        except httpx.HTTPError as e:
            logger.error(f"[RSS HTTP 오류] {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"[RSS 피드 파싱 오류] {url}: {e}")
            raise

    def _parse_entry(
        self,
        entry: feedparser.FeedParserDict,
        config: RSSSourceConfig,
        min_published: datetime | None,
    ) -> Article | None:
        """
        RSS 엔트리를 Article 객체로 변환합니다.

        Args:
            entry: feedparser 엔트리 객체
            config: RSS 소스 설정
            min_published: 최소 발행 시각

        Returns:
            Article 객체 또는 None (파싱 실패 또는 필터링된 경우)
        """
        # 제목 추출 및 디코딩
        title = self._get_entry_value(entry, "title", "").strip()
        if not title:
            logger.warning("[RSS 엔트리 파싱] 제목이 비어있어 스킵합니다.")
            return None

        title = html.unescape(title)

        # 링크 추출 및 디코딩
        link = self._get_entry_value(entry, "link", "").strip()
        link = unquote(link)

        if not link:
            logger.warning(
                f"[RSS 엔트리 파싱] 링크가 비어있어 스킵합니다. 제목: {title[:50]}..."
            )
            return None

        # 발행 시각 파싱
        published_at = self._parse_entry_date(entry)
        if published_at is None:
            logger.warning(
                f"[RSS 엔트리 파싱] 발행 시각을 파싱할 수 없어 스킵합니다. 제목: {title[:50]}..."
            )
            return None

        # 시간대 정규화 (UTC로 변환)
        published_at = self._normalize_timezone(published_at, config.timezone)

        # 시간 필터링
        if min_published and published_at < min_published:
            logger.debug(
                f"[RSS 시간 필터링] 발행 시각이 최소 시각보다 이전입니다. 제목: {title[:50]}..., 발행: {published_at.isoformat()}, 최소: {min_published.isoformat()}"
            )
            return None

        # 요약 추출
        description = self._get_entry_value(entry, "summary", "").strip()
        if description:
            description = html.unescape(description)

        # 본문 추출: content 필드를 우선 사용하고, 없을 경우 요약을 사용
        content = self._extract_content(entry)
        if not content or not content.strip():
            if description:
                content = description
                logger.debug(
                    f"[RSS 엔트리 파싱] 요약(summary)을 본문으로 사용합니다. 제목: {title[:50]}..."
                )
            else:
                logger.warning(
                    f"[RSS 엔트리 파싱] 본문이 비어있어 스킵합니다. 제목: {title[:50]}..."
                )
                return None

        # 작성자 추출
        author = self._get_entry_value(entry, "author", "").strip()
        if author:
            author = html.unescape(author)

        # 태그 추출
        tags = self._extract_tags(entry)

        # Article 객체 생성
        try:
            article = Article(
                title=title,
                url=link,
                content=content,
                source=config.name,
                published_at=published_at,
                source_type="rss",
                description=description if description else None,
                author=author if author else None,
                tags=tags if tags else None,
            )
            return article
        except ValueError as e:
            logger.error(f"[RSS 엔트리 검증 실패] {e}, 제목: {title[:50]}...")
            return None

    def _get_entry_value(
        self, entry: feedparser.FeedParserDict, key: str, default: str = ""
    ) -> str:
        """
        엔트리에서 값을 안전하게 추출합니다.

        Args:
            entry: feedparser 엔트리 객체
            key: 필드 키
            default: 기본값

        Returns:
            필드 값 (문자열)
        """
        try:
            value = getattr(entry, key, None)
            if value is None:
                return default
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            return str(value) if value else default
        except Exception:
            return default

    def _parse_entry_date(self, entry: feedparser.FeedParserDict) -> datetime | None:
        """
        RSS 엔트리에서 날짜를 파싱합니다.

        다양한 날짜 필드를 시도하여 파싱합니다.

        Args:
            entry: feedparser 엔트리 객체

        Returns:
            datetime 객체 또는 None (파싱 실패 시)
        """
        # 1. 파싱된 날짜 튜플 시도 (가장 정확)
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        for field in date_fields:
            if hasattr(entry, field):
                date_tuple = getattr(entry, field)
                if date_tuple:
                    try:
                        dt = datetime(*date_tuple[:6], tzinfo=timezone.utc)
                        return dt
                    except (ValueError, TypeError):
                        continue

        # 2. 문자열 날짜 파싱 시도
        date_strings = ["published", "updated", "created", "pubDate"]
        for field in date_strings:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                if date_str:
                    try:
                        dt = date_parser.parse(str(date_str))
                        # timezone이 없으면 UTC로 가정
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except (ValueError, TypeError) as e:
                        logger.debug(
                            f"[RSS 날짜 파싱 실패] 필드: {field}, 값: {date_str}, 오류: {e}"
                        )
                        continue

        return None

    def _normalize_timezone(self, dt: datetime, source_timezone: int) -> datetime:
        """
        시간대를 정규화합니다 (UTC로 변환).

        Args:
            dt: datetime 객체
            source_timezone: 소스 시간대 (UTC offset, 예: 9 = KST)

        Returns:
            UTC로 변환된 datetime 객체
        """
        # 이미 timezone-aware이면 그대로 사용
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)

        # timezone-naive이면 소스 시간대를 적용 후 UTC로 변환
        from datetime import timedelta

        source_tz = timezone(timedelta(hours=source_timezone))
        dt = dt.replace(tzinfo=source_tz)
        return dt.astimezone(timezone.utc)

    def _extract_content(self, entry: feedparser.FeedParserDict) -> str:
        """
        RSS 엔트리에서 본문을 추출합니다.

        Args:
            entry: feedparser 엔트리 객체

        Returns:
            본문 텍스트
        """
        # 1. content 필드 시도 (일부 피드는 본문을 content에 저장)
        content_fields = ["content", "summary"]
        for field in content_fields:
            if hasattr(entry, field):
                value = getattr(entry, field)
                if value:
                    # 리스트인 경우 첫 번째 요소 사용
                    if isinstance(value, list) and len(value) > 0:
                        value = value[0]
                        if hasattr(value, "value"):
                            value = value.value

                    # HTML 태그 제거
                    text = self._html_to_text(str(value))
                    if text and len(text.strip()) > 50:  # 최소 길이 체크
                        return text

        # 2. summary 필드 사용 (fallback)
        summary = self._get_entry_value(entry, "summary", "")
        if summary:
            text = self._html_to_text(summary)
            if text and len(text.strip()) > 50:
                return text

        # 3. title을 본문으로 사용 (최후의 수단)
        title = self._get_entry_value(entry, "title", "")
        if title:
            return html.unescape(title)

        return ""

    def _html_to_text(self, html_content: str) -> str:
        """
        HTML 콘텐츠를 텍스트로 변환합니다.

        Args:
            html_content: HTML 문자열

        Returns:
            텍스트 문자열
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")

            # 스크립트, 스타일 태그 제거
            for tag in soup(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            # 텍스트 추출
            text = soup.get_text(separator=" ", strip=True)

            # HTML 엔티티 디코딩
            text = html.unescape(text)

            return text
        except Exception as e:
            logger.debug(f"[RSS HTML 파싱 실패] {e}, 원본 사용")
            # 파싱 실패 시 원본 반환 (이미 텍스트일 수 있음)
            return html.unescape(html_content)

    def _extract_tags(self, entry: feedparser.FeedParserDict) -> list[str]:
        """
        RSS 엔트리에서 태그를 추출합니다.

        Args:
            entry: feedparser 엔트리 객체

        Returns:
            태그 리스트
        """
        tags = []

        try:
            # tags 필드 확인
            if hasattr(entry, "tags") and entry.tags:
                for tag in entry.tags:
                    if hasattr(tag, "term"):
                        tags.append(str(tag.term))
                    elif isinstance(tag, str):
                        tags.append(tag)

            # category 필드 확인
            if hasattr(entry, "category"):
                category = entry.category
                if category:
                    if isinstance(category, list):
                        tags.extend([str(c) for c in category])
                    else:
                        tags.append(str(category))

            # 중복 제거 및 정규화
            tags = list({tag.strip() for tag in tags if tag.strip()})

        except Exception as e:
            logger.debug(f"[RSS 태그 추출 실패] {e}")

        return tags

"""
데이터 정규화 모듈

RSS 기사와 텔레그램 메시지를 공통 스키마(CollectedItem)로 변환합니다.
LLM 파이프라인 문서의 섹션 2.1을 참조하여 구현되었습니다.
"""

import logging
from typing import Any

from src.collectors.models import Article, CollectedItem, MetadataValue, TelegramMessage


logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    데이터 정규화 클래스

    다양한 소스의 데이터를 공통 스키마(CollectedItem)로 변환합니다.
    """

    @staticmethod
    def normalize_article(article: Article) -> CollectedItem:
        """
        Article을 CollectedItem으로 변환합니다.

        Args:
            article: 변환할 Article 객체

        Returns:
            CollectedItem 객체
        """
        return article.to_collected_item()

    @staticmethod
    def normalize_telegram_message(message: TelegramMessage) -> CollectedItem:
        """
        TelegramMessage를 CollectedItem으로 변환합니다.

        텔레그램 메시지를 공통 스키마로 변환합니다.
        메타데이터에는 채널 정보와 메시지 ID가 포함됩니다.

        Args:
            message: 변환할 TelegramMessage 객체

        Returns:
            CollectedItem 객체
        """
        metadata: dict[str, MetadataValue] = {
            "channel_id": message.channel_id,
            "channel_name": message.channel_name,
            "message_id": message.message_id,
        }

        # author는 프로젝트 목적에 불필요하므로 제외

        if message.reply_to_message_id:
            metadata["reply_to_message_id"] = message.reply_to_message_id

        return CollectedItem(
            source_type="telegram",
            source_name=message.channel_name,
            timestamp=message.timestamp,
            text=message.text,
            metadata=metadata,
        )

    @staticmethod
    def normalize_articles(articles: list[Article]) -> list[CollectedItem]:
        """
        Article 리스트를 CollectedItem 리스트로 변환합니다.

        Args:
            articles: 변환할 Article 객체 리스트

        Returns:
            CollectedItem 객체 리스트
        """
        logger.info(f"[DataNormalizer] Article 정규화 시작: {len(articles)}개")

        normalized_items: list[CollectedItem] = []

        for article in articles:
            try:
                item = DataNormalizer.normalize_article(article)
                normalized_items.append(item)
            except Exception as e:
                logger.error(
                    f"[DataNormalizer] Article 정규화 중 오류 발생: source={article.source}, error={e}"
                )
                continue

        logger.info(f"[DataNormalizer] Article 정규화 완료: {len(normalized_items)}개")
        return normalized_items

    @staticmethod
    def normalize_telegram_messages(
        messages: list[TelegramMessage],
    ) -> list[CollectedItem]:
        """
        TelegramMessage 리스트를 CollectedItem 리스트로 변환합니다.

        Args:
            messages: 변환할 TelegramMessage 객체 리스트

        Returns:
            CollectedItem 객체 리스트
        """
        logger.info(f"[DataNormalizer] TelegramMessage 정규화 시작: {len(messages)}개")

        normalized_items: list[CollectedItem] = []

        for message in messages:
            try:
                item = DataNormalizer.normalize_telegram_message(message)
                normalized_items.append(item)
            except Exception as e:
                logger.error(
                    f"[DataNormalizer] TelegramMessage 정규화 중 오류 발생: "
                    f"channel={message.channel_name}, message_id={message.message_id}, error={e}"
                )
                continue

        logger.info(
            f"[DataNormalizer] TelegramMessage 정규화 완료: {len(normalized_items)}개"
        )
        return normalized_items

    @staticmethod
    def normalize_mixed_data(
        articles: list[Article] | None = None,
        telegram_messages: list[TelegramMessage] | None = None,
    ) -> list[CollectedItem]:
        """
        혼합된 데이터 소스를 정규화합니다.

        RSS 기사와 텔레그램 메시지를 함께 정규화하여 단일 리스트로 반환합니다.

        Args:
            articles: Article 객체 리스트 (선택)
            telegram_messages: TelegramMessage 객체 리스트 (선택)

        Returns:
            정규화된 CollectedItem 객체 리스트 (시간순 정렬)
        """
        logger.info(
            f"[DataNormalizer] 혼합 데이터 정규화 시작: "
            f"Article={len(articles) if articles else 0}개, "
            f"TelegramMessage={len(telegram_messages) if telegram_messages else 0}개"
        )

        normalized_items: list[CollectedItem] = []

        # Article 정규화
        if articles:
            article_items = DataNormalizer.normalize_articles(articles)
            normalized_items.extend(article_items)

        # TelegramMessage 정규화
        if telegram_messages:
            message_items = DataNormalizer.normalize_telegram_messages(
                telegram_messages
            )
            normalized_items.extend(message_items)

        # 시간순 정렬
        normalized_items.sort(key=lambda x: x.timestamp)

        logger.info(
            f"[DataNormalizer] 혼합 데이터 정규화 완료: {len(normalized_items)}개"
        )
        return normalized_items

    @staticmethod
    def to_dict_format(item: CollectedItem) -> dict[str, Any]:
        """
        CollectedItem을 LLM 파이프라인 문서 형식의 딕셔너리로 변환합니다.

        LLM 파이프라인 문서의 섹션 2.1에 정의된 형식:
        {
            "source": "rss" | "telegram",
            "timestamp": "ISO 8601 형식",
            "text": "원본 텍스트",
            "meta": {
                "title": "기사 제목 또는 메시지 요약",
                "url": "기사 링크 (RSS만)",
                "channel": "텔레그램 채널명 (Telegram만)"
            }
        }

        Args:
            item: 변환할 CollectedItem 객체

        Returns:
            딕셔너리 형태의 정규화된 데이터
        """
        meta: dict[str, Any] = {
            key: value for key, value in item.metadata.items() if value is not None
        }

        # 텔레그램의 경우 채널 정보 필드를 channel로 통합 (None 값은 제외)
        if item.source_type == "telegram" and "channel" not in meta:
            if "channel_name" in item.metadata:
                channel_name_value = item.metadata["channel_name"]
                if channel_name_value is not None:
                    meta["channel"] = channel_name_value
            elif "channel_id" in item.metadata:
                channel_id_value = item.metadata["channel_id"]
                if channel_id_value is not None:
                    meta["channel"] = channel_id_value

        return {
            "source": item.source_type,
            "timestamp": item.timestamp.isoformat(),
            "text": item.text,
            "meta": meta,
        }

    @staticmethod
    def to_dict_format_batch(items: list[CollectedItem]) -> list[dict[str, Any]]:
        """
        CollectedItem 리스트를 LLM 파이프라인 문서 형식의 딕셔너리 리스트로 변환합니다.

        Args:
            items: 변환할 CollectedItem 객체 리스트

        Returns:
            딕셔너리 리스트
        """
        return [DataNormalizer.to_dict_format(item) for item in items]

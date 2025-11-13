"""
Article Factory

Article 객체 생성을 담당하는 Factory 클래스입니다.
다양한 소스(RSS, Telegram 등)에서 Article을 생성하는 로직을 중앙화합니다.
"""

from typing import List, Optional
from datetime import datetime

from src.collectors.models import Article, CollectedItem, TelegramMessage


class ArticleFactory:
    """
    Article 객체 생성을 담당하는 Factory 클래스
    
    다양한 소스에서 Article을 생성하는 정적 메서드를 제공합니다.
    - 텔레그램 메시지 그룹화 및 변환
    - RSS 엔트리 변환 (향후 확장 가능)
    """
    
    @staticmethod
    def from_telegram_messages(
        messages: List[TelegramMessage],
        time_window_minutes: int = 30,
        max_messages_per_article: int = 50
    ) -> List[Article]:
        """
        텔레그램 메시지를 시간대별로 그룹화하여 Article 리스트로 변환합니다.
        
        텔레그램 메시지들은 짧고 다수 존재하므로, 시간대별로 그룹화하여
        하나의 Article로 묶어서 처리합니다. 이를 통해 메모리 효율성과
        처리 효율성을 높입니다.
        
        Args:
            messages: 텔레그램 메시지 리스트
            time_window_minutes: 그룹화할 시간 창 (분). 같은 시간 창 내의 메시지들을 하나로 묶습니다.
            max_messages_per_article: Article당 최대 메시지 수. 이 수를 초과하면 새 Article을 생성합니다.
        
        Returns:
            Article 리스트 (각 Article은 그룹화된 텔레그램 메시지 배치)
        
        Example:
            >>> messages = [
            ...     TelegramMessage(message_id=1, text="메시지1", channel_id="@test", channel_name="Test", timestamp=datetime.now()),
            ...     TelegramMessage(message_id=2, text="메시지2", channel_id="@test", channel_name="Test", timestamp=datetime.now()),
            ... ]
            >>> articles = ArticleFactory.from_telegram_messages(messages, time_window_minutes=30)
            >>> len(articles)  # 하나의 Article로 그룹화됨
            1
        """
        if not messages:
            return []
        
        # 시간순 정렬
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        articles = []
        current_batch: List[TelegramMessage] = []
        current_start_time: Optional[datetime] = None
        
        for msg in sorted_messages:
            # 새 배치 시작 조건 확인
            should_start_new_batch = False
            
            if not current_batch:
                # 첫 메시지
                should_start_new_batch = True
            else:
                # 시간 창 초과 확인
                if current_start_time:
                    time_diff_seconds = (msg.timestamp - current_start_time).total_seconds()
                    if time_diff_seconds > time_window_minutes * 60:
                        should_start_new_batch = True
                
                # 최대 메시지 수 초과 확인 (시간 창과 독립적으로 체크)
                if len(current_batch) >= max_messages_per_article:
                    should_start_new_batch = True
            
            if should_start_new_batch:
                # 현재 배치를 Article로 변환
                if current_batch:
                    article = ArticleFactory._create_article_from_messages(current_batch)
                    articles.append(article)
                
                # 새 배치 시작
                current_batch = [msg]
                current_start_time = msg.timestamp
            else:
                # 현재 배치에 추가
                current_batch.append(msg)
        
        # 마지막 배치 처리
        if current_batch:
            article = ArticleFactory._create_article_from_messages(current_batch)
            articles.append(article)
        
        return articles
    
    @staticmethod
    def _create_article_from_messages(messages: List[TelegramMessage]) -> Article:
        """
        텔레그램 메시지 배치를 Article 객체로 변환합니다.
        
        Args:
            messages: 그룹화된 텔레그램 메시지 리스트 (최소 1개 이상)
        
        Returns:
            Article 객체
        
        Raises:
            ValueError: messages가 비어있거나, 모든 메시지가 같은 채널에 속하지 않는 경우
        """
        if not messages:
            raise ValueError("messages는 비어있을 수 없습니다.")
        
        # 모든 메시지가 같은 채널에 속하는지 확인
        channel_id = messages[0].channel_id
        channel_name = messages[0].channel_name
        
        for msg in messages[1:]:
            if msg.channel_id != channel_id:
                raise ValueError(
                    f"모든 메시지는 같은 채널에 속해야 합니다. "
                    f"채널 ID 불일치: {channel_id} != {msg.channel_id}"
                )
        
        # 메시지 ID 리스트 추출
        message_ids = [msg.message_id for msg in messages]
        
        # 발행 시각은 첫 메시지의 시각 사용
        published_at = messages[0].timestamp
        
        # 제목 생성: 채널명과 시간 범위 포함
        if len(messages) == 1:
            title = f"[{channel_name}] 메시지"
        else:
            first_time = messages[0].timestamp.strftime("%H:%M")
            last_time = messages[-1].timestamp.strftime("%H:%M")
            title = f"[{channel_name}] 메시지 배치 ({first_time}~{last_time}, {len(messages)}개)"
        
        # 본문 생성: 모든 메시지 텍스트를 시간순으로 결합
        content_parts = []
        for msg in messages:
            # 작성자가 있으면 포함
            if msg.author:
                content_parts.append(f"[{msg.author}]: {msg.text}")
            else:
                content_parts.append(msg.text)
        
        content = "\n\n".join(content_parts)
        
        # Article 객체 생성
        return Article(
            title=title,
            url="",  # 텔레그램 메시지는 URL이 없음
            content=content,
            source=channel_name,
            published_at=published_at,
            source_type="telegram",
            telegram_message_ids=message_ids,
            telegram_message_count=len(messages)
        )

    @staticmethod
    def to_collected_items(articles: List[Article]) -> List[CollectedItem]:
        """
        Article 리스트를 CollectedItem 리스트로 변환합니다.

        Args:
            articles: Article 객체 리스트

        Returns:
            CollectedItem 객체 리스트
        """
        return [article.to_collected_item() for article in articles]

    @staticmethod
    def to_collected_item(article: Article) -> CollectedItem:
        """
        단일 Article 객체를 CollectedItem으로 변환합니다.

        Args:
            article: 변환할 Article 객체

        Returns:
            CollectedItem 객체
        """
        return article.to_collected_item()


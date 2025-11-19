"""
수집기 데이터 모델

RSS 및 텔레그램 수집기에서 사용하는 데이터 모델을 정의합니다.
- Article: RSS 기사 또는 그룹화된 텔레그램 메시지 배치 (분석 단계용)
- TelegramMessage: 텔레그램 개별 메시지 (수집 단계용, 경량 모델)
- CollectedItem: 수집 단계 결과를 공통 스키마로 표현한 데이터 모델
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Union
from datetime import datetime
import hashlib

SegmentRangeTokens = Dict[str, int]
MetadataValue = Union[str, int, float, bool, List[str], List[int], SegmentRangeTokens, None]


@dataclass
class TelegramMessage:
    """
    텔레그램 메시지 경량 모델
    
    텔레그램 수집기에서 개별 메시지를 빠르고 효율적으로 수집하기 위한 경량 모델입니다.
    전처리 단계에서 시간대별로 그룹화되어 Article로 변환됩니다.
    """
    # 필수 필드
    message_id: int  # 텔레그램 메시지 ID
    text: str  # 메시지 텍스트
    channel_id: str  # 채널 ID
    channel_name: str  # 채널 이름
    timestamp: datetime  # 발행 시각 (UTC)
    
    # 선택적 필드
    author: Optional[str] = None  # 작성자 (사용자명)
    reply_to_message_id: Optional[int] = None  # 답장인 경우 원본 메시지 ID
    
    def __post_init__(self):
        """데이터 검증 및 정규화"""
        if not self.text or not self.text.strip():
            raise ValueError("text는 필수이며 비어있을 수 없습니다.")
        if not self.channel_id or not self.channel_id.strip():
            raise ValueError("channel_id는 필수이며 비어있을 수 없습니다.")
        if not self.channel_name or not self.channel_name.strip():
            raise ValueError("channel_name은 필수이며 비어있을 수 없습니다.")
        
        # 공백 제거
        self.text = self.text.strip()
        self.channel_id = self.channel_id.strip()
        self.channel_name = self.channel_name.strip()
        
        # timestamp가 timezone-aware인지 확인 (UTC로 가정)
        if self.timestamp.tzinfo is None:
            from datetime import timezone
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        result = {
            "message_id": self.message_id,
            "text": self.text,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.author:
            result["author"] = self.author
        if self.reply_to_message_id:
            result["reply_to_message_id"] = self.reply_to_message_id
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "TelegramMessage":
        """딕셔너리에서 TelegramMessage 객체 생성"""
        from dateutil import parser
        
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = parser.parse(timestamp)
        elif not isinstance(timestamp, datetime):
            raise ValueError("timestamp는 datetime 또는 ISO 형식 문자열이어야 합니다.")
        
        return cls(
            message_id=data["message_id"],
            text=data["text"],
            channel_id=data["channel_id"],
            channel_name=data["channel_name"],
            timestamp=timestamp,
            author=data.get("author"),
            reply_to_message_id=data.get("reply_to_message_id")
        )


@dataclass
class Article:
    """
    통합 데이터 모델
    
    RSS 기사 또는 그룹화된 텔레그램 메시지 배치를 나타냅니다.
    - RSS 기사: 1:1 매핑 (개별 기사)
    - 텔레그램 메시지: 1:N 매핑 (시간대별로 그룹화된 메시지 배치)
    
    분석 단계(LangGraph)에서 사용되는 통일된 데이터 구조입니다.
    """
    # 필수 필드
    title: str  # 기사 제목 또는 텔레그램 배치 제목
    url: str  # 기사 링크 (텔레그램의 경우 빈 문자열)
    content: str  # 기사 본문 또는 텔레그램 메시지 배치
    source: str  # 출처 (RSS 피드 이름 또는 텔레그램 채널 이름)
    published_at: datetime  # 발행 시각 (UTC)
    
    # 메타데이터
    source_type: str  # "rss" 또는 "telegram"
    description: Optional[str] = None  # 기사 요약
    author: Optional[str] = None  # 작성자 (RSS의 경우)
    tags: Optional[List[str]] = None  # 태그 리스트
    
    # 텔레그램 전용 필드 (source_type="telegram"일 때 사용)
    telegram_message_ids: Optional[List[int]] = None  # 포함된 메시지 ID 리스트
    telegram_message_count: Optional[int] = None  # 포함된 메시지 개수
    
    def __post_init__(self):
        """데이터 검증 및 정규화"""
        # 제목과 본문은 최소한 비어있지 않아야 함
        if not self.title or not self.title.strip():
            raise ValueError("title은 필수이며 비어있을 수 없습니다.")
        if not self.content or not self.content.strip():
            raise ValueError("content는 필수이며 비어있을 수 없습니다.")
        if not self.source or not self.source.strip():
            raise ValueError("source는 필수이며 비어있을 수 없습니다.")
        if self.source_type not in ["rss", "telegram"]:
            raise ValueError("source_type은 'rss' 또는 'telegram'이어야 합니다.")
        
        # 공백 제거
        self.title = self.title.strip()
        self.content = self.content.strip()
        self.source = self.source.strip()
        
        # published_at이 timezone-aware인지 확인 (UTC로 가정)
        if self.published_at.tzinfo is None:
            from datetime import timezone
            self.published_at = self.published_at.replace(tzinfo=timezone.utc)
        
        # 텔레그램 메시지 관련 필드 검증
        if self.source_type == "telegram":
            if self.telegram_message_ids is None:
                self.telegram_message_ids = []
            if self.telegram_message_count is None:
                self.telegram_message_count = len(self.telegram_message_ids)
    
    def get_unique_key(self) -> str:
        """
        중복 제거를 위한 고유 키 생성
        
        링크와 제목을 조합하여 고유 키를 생성합니다.
        링크가 없는 경우(텔레그램 메시지 등) 제목과 출처를 조합합니다.
        
        Returns:
            고유 키 (SHA256 해시)
        """
        if self.url and self.url.strip():
            # 링크가 있으면 링크를 우선 사용
            key_string = f"{self.url}|{self.title}"
        else:
            # 링크가 없으면 제목과 출처, 발행 시각을 조합
            key_string = f"{self.source}|{self.title}|{self.published_at.isoformat()}"
        
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> dict:
        """
        딕셔너리로 변환 (JSON 직렬화용)
        
        Returns:
            딕셔너리 형태의 데이터
        """
        result = {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "source_type": self.source_type,
        }
        
        if self.description:
            result["description"] = self.description
        if self.author:
            result["author"] = self.author
        if self.tags:
            result["tags"] = self.tags
        if self.telegram_message_ids:
            result["telegram_message_ids"] = self.telegram_message_ids
        if self.telegram_message_count is not None:
            result["telegram_message_count"] = self.telegram_message_count
        
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """
        딕셔너리에서 Article 객체 생성
        
        Args:
            data: 딕셔너리 형태의 데이터
            
        Returns:
            Article 객체
        """
        from dateutil import parser
        
        # published_at 파싱
        published_at = data.get("published_at")
        if isinstance(published_at, str):
            published_at = parser.parse(published_at)
        elif not isinstance(published_at, datetime):
            raise ValueError("published_at은 datetime 또는 ISO 형식 문자열이어야 합니다.")
        
        return cls(
            title=data["title"],
            url=data.get("url", ""),
            content=data["content"],
            source=data["source"],
            published_at=published_at,
            source_type=data.get("source_type", "rss"),
            description=data.get("description"),
            author=data.get("author"),
            tags=data.get("tags"),
            telegram_message_ids=data.get("telegram_message_ids"),
            telegram_message_count=data.get("telegram_message_count")
        )

    def to_collected_item(self) -> "CollectedItem":
        """
        Article 정보를 기반으로 CollectedItem 객체를 생성합니다.

        Returns:
            CollectedItem 객체
        """
        metadata: Dict[str, MetadataValue] = {}

        if self.title:
            metadata["title"] = self.title
        if self.url:
            metadata["url"] = self.url
        if self.description:
            metadata["description"] = self.description
        # author는 프로젝트 목적에 불필요하므로 제외
        if self.tags:
            metadata["tags"] = self.tags
        if self.telegram_message_ids:
            metadata["telegram_message_ids"] = self.telegram_message_ids
        if self.telegram_message_count is not None:
            metadata["telegram_message_count"] = self.telegram_message_count

        return CollectedItem(
            source_type=self.source_type,
            source_name=self.source,
            timestamp=self.published_at,
            text=self.content,
            metadata=metadata
        )


@dataclass
class CollectedItem:
    """
    수집 결과 공통 데이터 모델

    RSS 기사와 텔레그램 메시지를 공통 스키마로 표현하여
    후속 전처리 및 분석 단계에서 일관되게 사용할 수 있도록 합니다.
    """

    source_type: Literal["rss", "telegram"]  # 데이터 출처 유형
    source_name: str  # 데이터 출처 이름 (RSS 피드 이름 또는 텔레그램 채널 이름)
    timestamp: datetime  # 데이터 타임스탬프 (UTC)
    text: str  # 본문 텍스트
    metadata: Dict[str, MetadataValue] = field(default_factory=dict)  # 부가 메타데이터 (예: message_id, segment_range_tokens 등)

    def __post_init__(self) -> None:
        """데이터 검증 및 정규화"""
        if self.source_type not in ("rss", "telegram"):
            raise ValueError("source_type은 'rss' 또는 'telegram'이어야 합니다.")
        if not self.source_name or not self.source_name.strip():
            raise ValueError("source_name은 필수이며 비어있을 수 없습니다.")
        if not self.text or not self.text.strip():
            raise ValueError("text는 필수이며 비어있을 수 없습니다.")

        self.source_name = self.source_name.strip()
        self.text = self.text.strip()

        if self.timestamp.tzinfo is None:
            from datetime import timezone
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    def to_dict(self) -> Dict[str, object]:
        """
        딕셔너리로 변환 (JSON 직렬화용)

        Returns:
            딕셔너리 형태의 데이터
        """
        result: Dict[str, object] = {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "timestamp": self.timestamp.isoformat(),
            "text": self.text,
        }

        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "CollectedItem":
        """
        딕셔너리에서 CollectedItem 객체를 생성합니다.

        Args:
            data: 딕셔너리 형태의 데이터

        Returns:
            CollectedItem 객체
        """
        from dateutil import parser

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = parser.parse(timestamp)
        elif not isinstance(timestamp, datetime):
            raise ValueError("timestamp는 datetime 또는 ISO 형식 문자열이어야 합니다.")

        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata는 dict여야 합니다.")

        return cls(
            source_type=data["source_type"],  # type: ignore[index]
            source_name=data["source_name"],  # type: ignore[index]
            timestamp=timestamp,
            text=data["text"],  # type: ignore[index]
            metadata=metadata  # type: ignore[arg-type]
        )

    def with_metadata(self, **kwargs: MetadataValue) -> "CollectedItem":
        """
        메타데이터를 추가하거나 업데이트한 새로운 CollectedItem을 반환합니다.

        Args:
            **kwargs: 추가할 메타데이터 키/값

        Returns:
            업데이트된 CollectedItem 객체
        """
        updated_metadata = {**self.metadata, **kwargs}
        return CollectedItem(
            source_type=self.source_type,
            source_name=self.source_name,
            timestamp=self.timestamp,
            text=self.text,
            metadata=updated_metadata
        )


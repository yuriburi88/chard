"""
비동기 텔레그램 수집기

텔레그램 채널/채팅방에서 메시지를 비동기로 수집하는 모듈입니다.
- BaseTelegramCollector: 추상 기본 클래스
- BotAPICollector: Bot API 구현
- MTProtoCollector: MTProto 구현 (Telethon)
- TelegramCollectorFactory: 런타임에 적절한 구현체 생성
- TelegramCollector: 통합 인터페이스 (Factory를 통해 구현체 사용)
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Set
from datetime import datetime, timezone, timedelta

import httpx
from telegram import Bot
from telegram.error import TelegramError

from src.config_manager import TelegramSourceConfig
from src.collectors.models import TelegramMessage

logger = logging.getLogger(__name__)


class BaseTelegramCollector(ABC):
    """
    텔레그램 수집기 추상 기본 클래스
    
    Bot API와 MTProto 구현체가 공통으로 상속받는 기본 클래스입니다.
    공통 로직(메시지 청소, 시간대 정규화)을 제공합니다.
    """
    
    def __init__(self, request_timeout: float = 30.0):
        """
        텔레그램 수집기 초기화
        
        Args:
            request_timeout: 요청 타임아웃 (초)
        """
        self.request_timeout = request_timeout
    
    @abstractmethod
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        pass
    
    @abstractmethod
    async def collect(
        self,
        config: TelegramSourceConfig,
        min_timestamp: Optional[datetime] = None
    ) -> List[TelegramMessage]:
        """
        텔레그램 채널/채팅방에서 메시지를 수집합니다.
        
        Args:
            config: 텔레그램 소스 설정
            min_timestamp: 최소 타임스탬프 (이 시각 이후 메시지만 수집, None이면 필터링 안 함)
            
        Returns:
            수집된 메시지 리스트 (TelegramMessage 객체)
        """
        pass
    
    def _clean_messages(self, messages: List[TelegramMessage]) -> List[TelegramMessage]:
        """
        메시지를 청소합니다 (스팸/불용어 필터링).
        
        Args:
            messages: 원본 메시지 리스트
            
        Returns:
            청소된 메시지 리스트
        """
        if not messages:
            return []
        
        cleaned = []
        
        # 불용어 키워드
        stop_words = [
            '광고', '배너', '프로모션', '공지', '이벤트',
            'spam', 'advertisement', 'promotion', 'notice'
        ]
        
        for msg in messages:
            # 빈 메시지 제외
            if not msg.text or not msg.text.strip():
                logger.debug(f"[메시지 청소] 빈 메시지 제외: ID={msg.message_id}")
                continue
            
            # 너무 짧은 메시지 제외 (1자 이하)
            if len(msg.text.strip()) <= 1:
                logger.debug(f"[메시지 청소] 너무 짧은 메시지 제외: ID={msg.message_id}, 길이={len(msg.text)}")
                continue
            
            # 불용어 체크
            text_lower = msg.text.lower()
            if any(stop_word in text_lower for stop_word in stop_words):
                logger.debug(f"[메시지 청소] 불용어 포함 메시지 제외: ID={msg.message_id}, 텍스트={msg.text[:50]}...")
                continue
            
            # 통과한 메시지만 추가
            cleaned.append(msg)
        
        return cleaned
    
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
        source_tz = timezone(timedelta(hours=source_timezone))
        dt = dt.replace(tzinfo=source_tz)
        return dt.astimezone(timezone.utc)
    
    def _calculate_min_timestamp(
        self,
        config: TelegramSourceConfig,
        min_timestamp: Optional[datetime]
    ) -> datetime:
        """
        최소 타임스탬프를 계산합니다.
        
        Args:
            config: 텔레그램 소스 설정
            min_timestamp: 제공된 최소 타임스탬프 (None이면 hours_back 기준 계산)
            
        Returns:
            최소 타임스탬프 (UTC)
        """
        if min_timestamp is None:
            # hours_back을 기준으로 계산 (설정에 없으면 24시간)
            hours_back = getattr(config, 'hours_back', 24)
            min_timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            logger.info(f"[텔레그램 시간 필터] 최소 타임스탬프: {min_timestamp.isoformat()} (최근 {hours_back}시간)")
        
        return min_timestamp


class BotAPICollector(BaseTelegramCollector):
    """
    Bot API를 사용한 텔레그램 수집기
    
    python-telegram-bot 라이브러리를 사용하여 메시지를 수집합니다.
    """
    
    def __init__(self, request_timeout: float = 30.0):
        """
        Bot API 수집기 초기화
        
        Args:
            request_timeout: 요청 타임아웃 (초)
        """
        super().__init__(request_timeout)
        self._bot: Optional[Bot] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self._http_client = httpx.AsyncClient(timeout=self.request_timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def collect(
        self,
        config: TelegramSourceConfig,
        min_timestamp: Optional[datetime] = None
    ) -> List[TelegramMessage]:
        """
        Bot API를 사용하여 메시지를 수집합니다.
        
        Args:
            config: 텔레그램 소스 설정
            min_timestamp: 최소 타임스탬프
            
        Returns:
            TelegramMessage 리스트
        """
        if not config.bot_token:
            raise ValueError(f"Bot API를 사용하려면 bot_token이 필요합니다. (소스: {config.name})")
        
        logger.info(f"[Bot API] 봇 초기화 중...")
        bot = Bot(token=config.bot_token, request=self.request_timeout)
        
        try:
            # 봇 정보 확인
            bot_info = await bot.get_me()
            logger.info(f"[Bot API] 봇 정보: @{bot_info.username} ({bot_info.first_name})")
            
            # 채널 정보 확인
            try:
                chat = await bot.get_chat(config.channel_id)
                channel_name = chat.title or chat.username or config.channel_id
                logger.info(f"[Bot API] 채널 정보: {channel_name} (ID: {chat.id})")
            except TelegramError as e:
                logger.warning(f"[Bot API] 채널 정보 조회 실패: {e}, 채널명을 설정값으로 사용")
                channel_name = config.name
            
            # 최소 타임스탬프 계산
            min_timestamp = self._calculate_min_timestamp(config, min_timestamp)
            
            # HTTP 클라이언트가 없으면 생성
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=self.request_timeout)
            
            # 메시지 수집
            messages: List[TelegramMessage] = []
            message_ids: Set[int] = set()  # 중복 제거용
            
            # Bot API를 사용하여 채널 메시지 가져오기
            # 참고: Bot API는 채널 메시지를 직접 가져오는 것이 제한적입니다.
            # 봇이 채널에 추가되어 있어야 하며, getUpdates를 통해 메시지를 받아야 합니다.
            
            try:
                updates = await bot.get_updates(offset=-1, limit=100, timeout=10)
                logger.info(f"[Bot API] getUpdates로 {len(updates)}개 업데이트 수신")
                
                for update in updates:
                    if update.channel_post:
                        msg = update.channel_post
                        # 채널 ID 확인
                        if msg.chat.username == config.channel_id.replace('@', '') or \
                           str(msg.chat.id) == config.channel_id.replace('-', ''):
                            # 메시지 타임스탬프 확인
                            msg_timestamp = msg.date.replace(tzinfo=timezone.utc)
                            if min_timestamp and msg_timestamp < min_timestamp:
                                continue
                            
                            # 중복 확인
                            if msg.message_id in message_ids:
                                continue
                            message_ids.add(msg.message_id)
                            
                            # TelegramMessage 객체 생성
                            telegram_msg = TelegramMessage(
                                message_id=msg.message_id,
                                text=msg.text or msg.caption or "",
                                channel_id=str(msg.chat.id),
                                channel_name=channel_name,
                                timestamp=msg_timestamp,
                                author=None,  # 채널 메시지는 작성자 정보가 없을 수 있음
                                reply_to_message_id=msg.reply_to_message.message_id if msg.reply_to_message else None
                            )
                            
                            messages.append(telegram_msg)
                            
                            if len(messages) >= config.max_messages:
                                break
                
            except TelegramError as e:
                logger.error(f"[Bot API] 메시지 수집 중 오류: {e}")
                # 오류가 발생해도 수집된 메시지는 반환
                if not messages:
                    raise
            
            # 메시지 청소 (스팸/불용어 필터링)
            cleaned_messages = self._clean_messages(messages)
            logger.info(f"[텔레그램 메시지 청소] {len(messages)}개 → {len(cleaned_messages)}개")
            
            return cleaned_messages
            
        except TelegramError as e:
            logger.error(f"[Bot API 오류] {e}")
            raise


class MTProtoCollector(BaseTelegramCollector):
    """
    MTProto를 사용한 텔레그램 수집기
    
    Telethon 라이브러리를 사용하여 메시지를 수집합니다.
    """
    
    def __init__(self, request_timeout: float = 30.0):
        """
        MTProto 수집기 초기화
        
        Args:
            request_timeout: 요청 타임아웃 (초)
        """
        super().__init__(request_timeout)
        self._client = None
        self._session_file: Optional[str] = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self._client:
            await self._client.disconnect()
            self._client = None
    
    async def collect(
        self,
        config: TelegramSourceConfig,
        min_timestamp: Optional[datetime] = None
    ) -> List[TelegramMessage]:
        """
        MTProto를 사용하여 메시지를 수집합니다.
        
        Args:
            config: 텔레그램 소스 설정
            min_timestamp: 최소 타임스탬프
            
        Returns:
            TelegramMessage 리스트
        """
        if not config.api_id or not config.api_hash:
            raise ValueError(f"MTProto를 사용하려면 api_id와 api_hash가 필요합니다. (소스: {config.name})")
        
        try:
            from telethon import TelegramClient
            from telethon.errors import (
                AuthKeyUnregisteredError,
                FloodWaitError,
            )
        except ImportError:
            raise ImportError("MTProto를 사용하려면 telethon 패키지가 필요합니다. 'pip install telethon'을 실행하세요.")
        
        logger.info(f"[MTProto] 클라이언트 초기화 중...")
        
        # 세션 파일 경로 결정
        if config.session_file:
            session_file = config.session_file
        else:
            # 기본 세션 파일명 생성 (채널 ID 기반)
            session_name = f"telegram_{config.channel_id.replace('@', '').replace('-', '')}"
            session_file = f"{session_name}.session"
        
        # 세션 파일 경로를 Path 객체로 변환
        from pathlib import Path
        session_path = Path(session_file)
        
        # 세션 파일의 부모 디렉토리가 없으면 생성
        if session_path.parent and not session_path.parent.exists():
            try:
                session_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"[MTProto] 세션 파일 디렉토리 생성: {session_path.parent}")
            except Exception as e:
                logger.warning(
                    f"[MTProto] 세션 파일 디렉토리 생성 실패: {e}. "
                    f"경로: {session_path.parent}"
                )
        
        self._session_file = str(session_path)
        
        # Telethon 클라이언트 생성
        self._client = TelegramClient(
            self._session_file,
            config.api_id,
            config.api_hash,
            timeout=self.request_timeout
        )
        
        try:
            # 클라이언트 연결 시도
            try:
                await self._client.start()
            except AuthKeyUnregisteredError:
                # 세션이 만료되었거나 무효화된 경우
                logger.error(f"[MTProto] 세션이 만료되었거나 무효화되었습니다. (소스: {config.name})")
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            except Exception as e:
                # 기타 연결 오류
                logger.error(f"[MTProto] 클라이언트 연결 중 오류 발생: {e} (소스: {config.name})")
                raise ValueError(
                    f"MTProto 클라이언트 연결 실패: {e} (소스: {config.name})\n"
                    f"세션이 만료되었을 수 있습니다. 다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            
            # 전화번호 인증이 필요한 경우 (세션이 만료되었거나 무효화된 경우)
            try:
                is_authorized = await self._client.is_user_authorized()
            except AuthKeyUnregisteredError:
                # 세션 인증 확인 중 만료 감지
                logger.error(f"[MTProto] 세션이 만료되었거나 무효화되었습니다. (소스: {config.name})")
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            
            if not is_authorized:
                logger.warning(f"[MTProto] 세션이 만료되었거나 인증되지 않았습니다. (소스: {config.name})")
                logger.warning("[MTProto] 세션 재인증이 필요합니다. 'tele_setup.py'를 실행하여 세션을 갱신하세요.")
                
                if not config.phone_number:
                    raise ValueError(
                        f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                        f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                        f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                    )
                
                # 수집기 실행 중에는 사용자 입력을 받을 수 없으므로 오류 발생
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"수집기 실행 중에는 재인증을 할 수 없습니다.\n"
                    f"다음 명령을 실행하여 세션을 재생성한 후 다시 시도하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            
            logger.info(f"[MTProto] 클라이언트 연결 완료")
            
            # 채널 정보 확인
            try:
                entity = await self._client.get_entity(config.channel_id)
                channel_name = entity.title if hasattr(entity, 'title') else config.name
                channel_id = str(entity.id)
                logger.info(f"[MTProto] 채널 정보: {channel_name} (ID: {channel_id})")
            except AuthKeyUnregisteredError:
                # 채널 조회 중 세션 만료 감지
                logger.error(f"[MTProto] 채널 조회 중 세션이 만료되었습니다. (소스: {config.name})")
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            except FloodWaitError as e:
                # API 제한으로 인한 대기 필요
                logger.warning(f"[MTProto] API 제한으로 인해 {e.seconds}초 대기 필요합니다. (소스: {config.name})")
                raise ValueError(
                    f"Telegram API 제한으로 인해 {e.seconds}초 대기 후 다시 시도해야 합니다. (소스: {config.name})"
                )
            except Exception as e:
                logger.warning(f"[MTProto] 채널 정보 조회 실패: {e}, 채널명을 설정값으로 사용")
                channel_name = config.name
                channel_id = config.channel_id
            
            # 최소 타임스탬프 계산
            min_timestamp = self._calculate_min_timestamp(config, min_timestamp)
            
            # 메시지 수집
            messages: List[TelegramMessage] = []
            message_ids: Set[int] = set()  # 중복 제거용
            
            logger.info(f"[MTProto] 메시지 수집 시작 (최대 {config.max_messages}개)")
            
            # 채널에서 메시지 가져오기
            try:
                message_iter = self._client.iter_messages(
                    config.channel_id,
                    limit=config.max_messages,
                    reverse=False  # 최신 메시지부터
                )
            except AuthKeyUnregisteredError:
                # 메시지 수집 시작 전 세션 만료 감지
                logger.error(f"[MTProto] 메시지 수집 시작 전 세션이 만료되었습니다. (소스: {config.name})")
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            except FloodWaitError as e:
                logger.warning(f"[MTProto] API 제한으로 인해 {e.seconds}초 대기 필요합니다. (소스: {config.name})")
                raise ValueError(
                    f"Telegram API 제한으로 인해 {e.seconds}초 대기 후 다시 시도해야 합니다. (소스: {config.name})"
                )
            
            try:
                async for msg in message_iter:
                    # 메시지 타임스탬프 확인
                    if msg.date:
                        msg_timestamp = msg.date.replace(tzinfo=timezone.utc)
                        if min_timestamp and msg_timestamp < min_timestamp:
                            logger.debug(f"[MTProto] 시간 필터링: 메시지가 최소 타임스탬프보다 이전입니다. 수집 중단.")
                            break
                    
                    # 중복 확인
                    if msg.id in message_ids:
                        continue
                    message_ids.add(msg.id)
                    
                    # 텍스트 추출
                    text = msg.message or ""
                    if not text and msg.entities:
                        # 엔티티가 있는 경우 텍스트 재구성
                        text = msg.raw_text or ""
                    
                    # TelegramMessage 객체 생성
                    telegram_msg = TelegramMessage(
                        message_id=msg.id,
                        text=text,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        timestamp=msg_timestamp if msg.date else datetime.now(timezone.utc),
                        author=msg.sender.first_name if msg.sender and hasattr(msg.sender, 'first_name') else None,
                        reply_to_message_id=msg.reply_to.reply_to_msg_id if msg.reply_to else None
                    )
                    
                    messages.append(telegram_msg)
                    logger.debug(f"[MTProto] 메시지 수집: ID={msg.id}, 텍스트 길이={len(text)}")
                    
                    if len(messages) >= config.max_messages:
                        break
            except AuthKeyUnregisteredError:
                # 메시지 수집 중 세션 만료 감지
                logger.error(f"[MTProto] 메시지 수집 중 세션이 만료되었습니다. (소스: {config.name}, 수집된 메시지: {len(messages)}개)")
                raise ValueError(
                    f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                    f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            except FloodWaitError as e:
                # 메시지 수집 중 API 제한
                logger.warning(f"[MTProto] 메시지 수집 중 API 제한으로 인해 {e.seconds}초 대기 필요합니다. (소스: {config.name}, 수집된 메시지: {len(messages)}개)")
                raise ValueError(
                    f"Telegram API 제한으로 인해 {e.seconds}초 대기 후 다시 시도해야 합니다. (소스: {config.name})"
                )
            
            logger.info(f"[MTProto] 메시지 수집 완료: {len(messages)}개")
            
            # 메시지 청소 (스팸/불용어 필터링)
            cleaned_messages = self._clean_messages(messages)
            logger.info(f"[텔레그램 메시지 청소] {len(messages)}개 → {len(cleaned_messages)}개")
            
            return cleaned_messages
            
        except ValueError as e:
            # 세션 만료 등 명확한 오류는 그대로 전파
            logger.error(f"[MTProto 오류] {e}")
            raise
        except AuthKeyUnregisteredError:
            # 세션 만료 예외를 명확한 오류 메시지로 변환
            logger.error(f"[MTProto] 세션이 만료되었습니다. (소스: {config.name})")
            raise ValueError(
                f"MTProto 세션이 만료되었습니다. (소스: {config.name})\n"
                f"다음 명령을 실행하여 세션을 재생성하세요:\n"
                f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
            )
        except FloodWaitError as e:
            # API 제한 오류
            logger.error(f"[MTProto] API 제한으로 인해 {e.seconds}초 대기 필요합니다. (소스: {config.name})")
            raise ValueError(
                f"Telegram API 제한으로 인해 {e.seconds}초 대기 후 다시 시도해야 합니다. (소스: {config.name})"
            )
        except Exception as e:
            # 기타 예외는 로그에 상세 정보 기록
            logger.error(f"[MTProto 오류] {e}", exc_info=True)
            # 세션 관련 오류일 가능성이 있으므로 안내 추가
            error_msg = str(e).lower()
            if "auth" in error_msg or "session" in error_msg or "unauthorized" in error_msg:
                raise ValueError(
                    f"MTProto 인증 오류가 발생했습니다: {e} (소스: {config.name})\n"
                    f"세션이 만료되었을 수 있습니다. 다음 명령을 실행하여 세션을 재생성하세요:\n"
                    f"  python tele_setup.py --config config.yml --profile \"{config.name}\""
                )
            raise
        finally:
            # 클라이언트는 __aexit__에서 종료됨
            pass


class TelegramCollectorFactory:
    """
    텔레그램 수집기 Factory
    
    설정에 따라 적절한 수집기 구현체를 생성합니다.
    """
    
    @staticmethod
    def create(config: TelegramSourceConfig, request_timeout: float = 30.0) -> BaseTelegramCollector:
        """
        설정에 따라 적절한 텔레그램 수집기를 생성합니다.
        
        Args:
            config: 텔레그램 소스 설정
            request_timeout: 요청 타임아웃 (초)
            
        Returns:
            BaseTelegramCollector 구현체 (BotAPICollector 또는 MTProtoCollector)
        
        Raises:
            ValueError: 지원하지 않는 인증 방식인 경우
        """
        if config.auth_method == "bot_api":
            logger.info(f"[Factory] Bot API 수집기 생성: {config.name}")
            return BotAPICollector(request_timeout=request_timeout)
        elif config.auth_method == "mtproto":
            logger.info(f"[Factory] MTProto 수집기 생성: {config.name}")
            return MTProtoCollector(request_timeout=request_timeout)
        else:
            raise ValueError(f"지원하지 않는 인증 방식: {config.auth_method}")


class TelegramCollector:
    """
    텔레그램 수집기 통합 인터페이스
    
    Factory를 통해 적절한 구현체를 생성하고, 일관된 인터페이스를 제공합니다.
    """
    
    def __init__(self, request_timeout: float = 30.0):
        """
        텔레그램 수집기 초기화
        
        Args:
            request_timeout: 요청 타임아웃 (초)
        """
        self.request_timeout = request_timeout
        self._collector: Optional[BaseTelegramCollector] = None
    
    async def collect(
        self,
        config: TelegramSourceConfig,
        min_timestamp: Optional[datetime] = None
    ) -> List[TelegramMessage]:
        """
        텔레그램 채널/채팅방에서 메시지를 수집합니다.
        
        Args:
            config: 텔레그램 소스 설정
            min_timestamp: 최소 타임스탬프 (이 시각 이후 메시지만 수집, None이면 필터링 안 함)
            
        Returns:
            수집된 메시지 리스트 (TelegramMessage 객체)
        """
        logger.info(f"[텔레그램 수집 시작] 소스: {config.name}, 채널: {config.channel_id}")
        logger.info(f"[텔레그램 수집 설정] auth_method={config.auth_method}, max_messages={config.max_messages}, timezone=UTC+{config.timezone}")
        
        # Factory를 통해 적절한 수집기 생성
        collector = TelegramCollectorFactory.create(config, self.request_timeout)
        
        try:
            # 컨텍스트 매니저로 사용
            async with collector:
                messages = await collector.collect(config, min_timestamp)
            
            logger.info(f"[텔레그램 수집 완료] {config.name}: 총 {len(messages)}개 메시지 수집")
            
            # 수집된 메시지 상세 로그
            if messages:
                logger.info(f"[텔레그램 수집 결과 상세] {config.name}:")
                for i, msg in enumerate(messages, 1):
                    logger.info(f"  [{i}] 메시지 ID: {msg.message_id}")
                    logger.info(f"      작성자: {msg.author or 'N/A'}")
                    logger.info(f"      발행: {msg.timestamp.isoformat()}")
                    logger.info(f"      본문: {msg.text[:100]}...")
                    logger.info("")
            
            return messages
            
        except Exception as e:
            logger.error(f"[텔레그램 수집 오류] {config.name}: {e}", exc_info=True)
            raise

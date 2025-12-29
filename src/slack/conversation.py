"""
대화 히스토리 관리

채널/스레드별로 대화 히스토리를 관리하여 맥락 기반 대화를 지원합니다.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.slack.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class ConversationSession:
    """대화 세션"""

    channel_id: str
    thread_ts: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    @property
    def session_key(self) -> str:
        """세션 키 반환"""
        if self.thread_ts:
            return f"{self.channel_id}:{self.thread_ts}"
        return self.channel_id

    def is_expired(self, timeout_minutes: int) -> bool:
        """세션이 만료되었는지 확인"""
        elapsed = time.time() - self.last_activity
        return elapsed > timeout_minutes * 60

    def add_message(self, role: str, content: Any) -> None:
        """메시지 추가"""
        self.messages.append({
            "role": role,
            "content": content,
        })
        self.last_activity = time.time()

    def get_messages(self) -> list[dict[str, Any]]:
        """메시지 목록 반환"""
        return self.messages.copy()

    def truncate(self, max_messages: int) -> None:
        """히스토리 길이 제한"""
        if len(self.messages) > max_messages * 2:  # user + assistant 쌍
            # 가장 오래된 메시지부터 제거 (시스템 메시지는 유지)
            self.messages = self.messages[-(max_messages * 2):]

    def clear(self) -> None:
        """히스토리 초기화"""
        self.messages = []
        self.last_activity = time.time()


class ConversationManager:
    """대화 히스토리 관리자"""

    def __init__(self):
        """매니저 초기화"""
        self._sessions: dict[str, ConversationSession] = {}
        self._config = get_config()
        logger.info("ConversationManager 초기화 완료")

    @property
    def max_history(self) -> int:
        """최대 히스토리 턴 수"""
        return self._config.max_history

    @property
    def timeout_minutes(self) -> int:
        """세션 타임아웃 (분)"""
        return self._config.conversation_timeout

    def get_session(
        self, channel_id: str, thread_ts: str | None = None
    ) -> ConversationSession:
        """
        세션을 가져오거나 생성합니다.

        Args:
            channel_id: Slack 채널 ID
            thread_ts: 스레드 타임스탬프 (없으면 채널 레벨 대화)

        Returns:
            대화 세션
        """
        session_key = f"{channel_id}:{thread_ts}" if thread_ts else channel_id

        # 기존 세션 확인
        if session_key in self._sessions:
            session = self._sessions[session_key]

            # 만료 확인
            if session.is_expired(self.timeout_minutes):
                logger.info(f"세션 만료, 새 세션 생성: {session_key}")
                session = ConversationSession(
                    channel_id=channel_id, thread_ts=thread_ts
                )
                self._sessions[session_key] = session
            else:
                # 히스토리 길이 제한
                session.truncate(self.max_history)

            return session

        # 새 세션 생성
        logger.info(f"새 세션 생성: {session_key}")
        session = ConversationSession(channel_id=channel_id, thread_ts=thread_ts)
        self._sessions[session_key] = session

        return session

    def get_history(
        self, channel_id: str, thread_ts: str | None = None
    ) -> list[dict[str, Any]]:
        """
        대화 히스토리를 가져옵니다.

        Args:
            channel_id: Slack 채널 ID
            thread_ts: 스레드 타임스탬프

        Returns:
            메시지 히스토리
        """
        session = self.get_session(channel_id, thread_ts)
        return session.get_messages()

    def add_user_message(
        self, channel_id: str, content: str, thread_ts: str | None = None
    ) -> list[dict[str, Any]]:
        """
        사용자 메시지를 추가하고 히스토리를 반환합니다.

        Args:
            channel_id: Slack 채널 ID
            content: 메시지 내용
            thread_ts: 스레드 타임스탬프

        Returns:
            업데이트된 히스토리
        """
        session = self.get_session(channel_id, thread_ts)
        session.add_message("user", content)
        return session.get_messages()

    def add_assistant_message(
        self, channel_id: str, content: str, thread_ts: str | None = None
    ) -> None:
        """
        어시스턴트 메시지를 추가합니다.

        Args:
            channel_id: Slack 채널 ID
            content: 메시지 내용
            thread_ts: 스레드 타임스탬프
        """
        session = self.get_session(channel_id, thread_ts)
        session.add_message("assistant", content)

    def update_history(
        self,
        channel_id: str,
        messages: list[dict[str, Any]],
        thread_ts: str | None = None,
    ) -> None:
        """
        히스토리를 업데이트합니다.

        Args:
            channel_id: Slack 채널 ID
            messages: 새 메시지 목록
            thread_ts: 스레드 타임스탬프
        """
        session = self.get_session(channel_id, thread_ts)
        session.messages = messages
        session.last_activity = time.time()
        session.truncate(self.max_history)

    def clear_session(
        self, channel_id: str, thread_ts: str | None = None
    ) -> None:
        """
        세션을 초기화합니다.

        Args:
            channel_id: Slack 채널 ID
            thread_ts: 스레드 타임스탬프
        """
        session_key = f"{channel_id}:{thread_ts}" if thread_ts else channel_id

        if session_key in self._sessions:
            self._sessions[session_key].clear()
            logger.info(f"세션 초기화: {session_key}")

    def cleanup_expired_sessions(self) -> int:
        """
        만료된 세션을 정리합니다.

        Returns:
            정리된 세션 수
        """
        expired_keys = [
            key
            for key, session in self._sessions.items()
            if session.is_expired(self.timeout_minutes)
        ]

        for key in expired_keys:
            del self._sessions[key]

        if expired_keys:
            logger.info(f"만료 세션 정리: {len(expired_keys)}개")

        return len(expired_keys)

    def get_session_count(self) -> int:
        """활성 세션 수 반환"""
        return len(self._sessions)

    def get_session_info(
        self, channel_id: str, thread_ts: str | None = None
    ) -> dict[str, Any]:
        """
        세션 정보를 반환합니다.

        Args:
            channel_id: Slack 채널 ID
            thread_ts: 스레드 타임스탬프

        Returns:
            세션 정보 딕셔너리
        """
        session = self.get_session(channel_id, thread_ts)
        return {
            "session_key": session.session_key,
            "message_count": len(session.messages),
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "is_expired": session.is_expired(self.timeout_minutes),
        }


# 싱글톤 인스턴스
_manager_instance: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    """ConversationManager 싱글톤 인스턴스를 반환합니다."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ConversationManager()
    return _manager_instance

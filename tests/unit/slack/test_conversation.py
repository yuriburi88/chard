"""
대화 히스토리 관리 테스트

ConversationSession 및 ConversationManager 클래스의 단위 테스트
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.slack.conversation import (
    ConversationManager,
    ConversationSession,
    get_conversation_manager,
)


class TestConversationSession:
    """ConversationSession 테스트"""

    def test_session_creation(self):
        """세션 생성 테스트"""
        session = ConversationSession(channel_id="C12345678")

        assert session.channel_id == "C12345678"
        assert session.thread_ts is None
        assert session.messages == []
        assert session.created_at > 0
        assert session.last_activity > 0

    def test_session_with_thread(self):
        """스레드가 있는 세션 생성 테스트"""
        session = ConversationSession(
            channel_id="C12345678", thread_ts="1234567890.123456"
        )

        assert session.thread_ts == "1234567890.123456"
        assert session.session_key == "C12345678:1234567890.123456"

    def test_session_key_without_thread(self):
        """스레드 없는 세션 키 테스트"""
        session = ConversationSession(channel_id="C12345678")
        assert session.session_key == "C12345678"

    def test_add_message(self):
        """메시지 추가 테스트"""
        session = ConversationSession(channel_id="C12345678")

        session.add_message("user", "안녕하세요")
        session.add_message("assistant", "안녕하세요! 무엇을 도와드릴까요?")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "안녕하세요"
        assert session.messages[1]["role"] == "assistant"

    def test_get_messages_returns_copy(self):
        """메시지 조회가 복사본을 반환하는지 테스트"""
        session = ConversationSession(channel_id="C12345678")
        session.add_message("user", "테스트")

        messages = session.get_messages()
        messages.append({"role": "test", "content": "추가"})

        # 원본은 변경되지 않아야 함
        assert len(session.messages) == 1

    def test_truncate_messages(self):
        """히스토리 길이 제한 테스트"""
        session = ConversationSession(channel_id="C12345678")

        # 20개 메시지 추가 (10턴)
        for i in range(20):
            role = "user" if i % 2 == 0 else "assistant"
            session.add_message(role, f"메시지 {i}")

        # 5턴(10개)으로 제한
        session.truncate(max_messages=5)

        assert len(session.messages) == 10
        # 최근 메시지가 남아있어야 함
        assert session.messages[0]["content"] == "메시지 10"

    def test_clear_messages(self):
        """히스토리 초기화 테스트"""
        session = ConversationSession(channel_id="C12345678")
        session.add_message("user", "테스트")
        session.add_message("assistant", "응답")

        session.clear()

        assert session.messages == []

    def test_is_expired_false(self):
        """세션 만료 안됨 테스트"""
        session = ConversationSession(channel_id="C12345678")

        # 방금 생성된 세션은 만료되지 않음
        assert session.is_expired(timeout_minutes=30) is False

    def test_is_expired_true(self):
        """세션 만료 테스트"""
        session = ConversationSession(channel_id="C12345678")

        # last_activity를 31분 전으로 설정
        session.last_activity = time.time() - (31 * 60)

        assert session.is_expired(timeout_minutes=30) is True


class TestConversationManager:
    """ConversationManager 테스트"""

    @pytest.fixture
    def manager(self):
        """ConversationManager fixture (mock config)"""
        with patch("src.slack.conversation.get_config") as mock_config:
            config = MagicMock()
            config.max_history = 10
            config.conversation_timeout = 30
            mock_config.return_value = config

            manager = ConversationManager()
            yield manager

    def test_get_session_creates_new(self, manager):
        """새 세션 생성 테스트"""
        session = manager.get_session("C12345678")

        assert session is not None
        assert session.channel_id == "C12345678"
        assert manager.get_session_count() == 1

    def test_get_session_returns_existing(self, manager):
        """기존 세션 반환 테스트"""
        session1 = manager.get_session("C12345678")
        session1.add_message("user", "테스트")

        session2 = manager.get_session("C12345678")

        assert session1 is session2
        assert len(session2.messages) == 1

    def test_get_session_with_thread(self, manager):
        """스레드별 세션 분리 테스트"""
        session1 = manager.get_session("C12345678", "thread1")
        session2 = manager.get_session("C12345678", "thread2")

        session1.add_message("user", "스레드1")
        session2.add_message("user", "스레드2")

        assert session1 is not session2
        assert session1.messages[0]["content"] == "스레드1"
        assert session2.messages[0]["content"] == "스레드2"

    def test_get_session_expired_creates_new(self, manager):
        """만료된 세션에서 새 세션 생성 테스트"""
        session1 = manager.get_session("C12345678")
        session1.add_message("user", "이전 대화")

        # 세션을 만료시킴
        session1.last_activity = time.time() - (31 * 60)

        session2 = manager.get_session("C12345678")

        # 새 세션이 생성되어야 함
        assert len(session2.messages) == 0

    def test_get_history(self, manager):
        """히스토리 조회 테스트"""
        manager.add_user_message("C12345678", "질문입니다")
        manager.add_assistant_message("C12345678", "답변입니다")

        history = manager.get_history("C12345678")

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_add_user_message(self, manager):
        """사용자 메시지 추가 테스트"""
        history = manager.add_user_message("C12345678", "안녕하세요")

        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "안녕하세요"

    def test_update_history(self, manager):
        """히스토리 업데이트 테스트"""
        new_history = [
            {"role": "user", "content": "질문"},
            {"role": "assistant", "content": "답변"},
        ]

        manager.update_history("C12345678", new_history)
        history = manager.get_history("C12345678")

        assert len(history) == 2

    def test_clear_session(self, manager):
        """세션 초기화 테스트"""
        manager.add_user_message("C12345678", "테스트")
        manager.clear_session("C12345678")

        history = manager.get_history("C12345678")
        assert len(history) == 0

    def test_cleanup_expired_sessions(self, manager):
        """만료 세션 정리 테스트"""
        # 두 개의 세션 생성
        session1 = manager.get_session("C111")
        session2 = manager.get_session("C222")

        # 하나만 만료시킴
        session1.last_activity = time.time() - (31 * 60)

        cleaned = manager.cleanup_expired_sessions()

        assert cleaned == 1
        assert manager.get_session_count() == 1

    def test_get_session_info(self, manager):
        """세션 정보 조회 테스트"""
        manager.add_user_message("C12345678", "테스트")

        info = manager.get_session_info("C12345678")

        assert "session_key" in info
        assert "message_count" in info
        assert info["message_count"] == 1
        assert info["is_expired"] is False


class TestGetConversationManager:
    """get_conversation_manager 싱글톤 테스트"""

    def test_singleton(self):
        """싱글톤 패턴 테스트"""
        # 모듈 레벨 변수 리셋
        import src.slack.conversation as conv_module

        conv_module._manager_instance = None

        with patch("src.slack.conversation.get_config") as mock_config:
            config = MagicMock()
            config.max_history = 10
            config.conversation_timeout = 30
            mock_config.return_value = config

            manager1 = get_conversation_manager()
            manager2 = get_conversation_manager()

            assert manager1 is manager2

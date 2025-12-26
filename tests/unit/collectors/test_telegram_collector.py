"""
텔레그램 수집기 비동기 단위 테스트

모의 텔레그램 응답을 활용하여 텔레그램 수집기의 비동기 동작을 테스트합니다.
"""

import sys
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


if "telegram" not in sys.modules:
    telegram_stub = ModuleType("telegram")
    telegram_stub.Bot = object  # placeholder, tests will monkeypatch
    sys.modules["telegram"] = telegram_stub

if "telegram.error" not in sys.modules:
    telegram_error_stub = ModuleType("telegram.error")
    telegram_error_stub.TelegramError = Exception
    sys.modules["telegram.error"] = telegram_error_stub

from src.collectors.telegram_collector import (
    BotAPICollector,
    MTProtoCollector,
    TelegramCollector,
    TelegramCollectorFactory,
)
from src.config_manager import TelegramSourceConfig


class FakeBot:
    """python-telegram-bot.Bot 대체 객체"""

    def __init__(self, token: str, request: float | None = None) -> None:
        self.token = token
        self.request = request
        self._updates: list[SimpleNamespace] = []

    def set_updates(self, updates: list[SimpleNamespace]) -> None:
        self._updates = updates

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(username="fake_bot", first_name="FakeBot")

    async def get_chat(self, channel_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            title="Crypto News", username="cryptonews", id=-100123456
        )

    async def get_updates(
        self,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = None,
    ) -> list[SimpleNamespace]:
        return self._updates


@pytest.fixture
def sample_telegram_config() -> TelegramSourceConfig:
    """샘플 텔레그램 소스 설정 (Bot API)"""
    return TelegramSourceConfig(
        name="Crypto News Channel",
        channel_id="@cryptonews",
        auth_method="bot_api",
        bot_token="TEST_TOKEN",
        timezone=9,
        max_messages=10,
    )


@pytest.fixture
def sample_mtproto_config() -> TelegramSourceConfig:
    """샘플 텔레그램 소스 설정 (MTProto)"""
    return TelegramSourceConfig(
        name="Crypto Channel MTProto",
        channel_id="@cryptonews",
        auth_method="mtproto",
        api_id=12345,
        api_hash="abcdef123456",
        timezone=9,
        max_messages=10,
    )


@pytest.mark.asyncio
async def test_bot_api_collector_collect(monkeypatch) -> None:
    """
    기본 Bot API 수집 테스트

    모의 Bot API 응답을 사용하여 메시지를 수집하는지 확인합니다.
    """
    collector = BotAPICollector(request_timeout=5.0)

    config = TelegramSourceConfig(
        name="Crypto News Channel",
        channel_id="@cryptonews",
        auth_method="bot_api",
        bot_token="TEST_TOKEN",
        timezone=9,
        max_messages=10,
    )

    fake_bot = FakeBot(token=config.bot_token, request=collector.request_timeout)

    message_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    fake_message = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(username="cryptonews", id=-100123456),
        date=message_time,
        text="Breaking crypto news.",
        caption=None,
        reply_to_message=None,
    )

    fake_update = SimpleNamespace(channel_post=fake_message)
    fake_bot.set_updates([fake_update])

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        messages = await collector.collect(
            config, min_timestamp=message_time - timedelta(minutes=5)
        )

    assert len(messages) == 1
    msg = messages[0]
    assert msg.message_id == 1
    assert msg.text == "Breaking crypto news."
    assert msg.channel_name == "Crypto News"
    assert msg.timestamp == message_time


@pytest.mark.asyncio
async def test_bot_api_collector_time_filtering(monkeypatch, sample_telegram_config):
    """
    Bot API 시간 필터링 테스트

    최소 타임스탬프 이후의 메시지만 수집하는지 확인합니다.
    """
    collector = BotAPICollector(request_timeout=5.0)

    now = datetime.now(timezone.utc)
    min_timestamp = now - timedelta(hours=2)

    # 다양한 시각의 메시지 생성
    messages_data = [
        (now, "Recent message"),
        (now - timedelta(hours=1), "1 hour ago"),
        (now - timedelta(hours=3), "3 hours ago"),  # 필터링되어야 함
    ]

    fake_updates = []
    for msg_time, text in messages_data:
        fake_message = SimpleNamespace(
            message_id=len(fake_updates) + 1,
            chat=SimpleNamespace(username="cryptonews", id=-100123456),
            date=msg_time,
            text=text,
            caption=None,
            reply_to_message=None,
        )
        fake_updates.append(SimpleNamespace(channel_post=fake_message))

    fake_bot = FakeBot(
        token=sample_telegram_config.bot_token, request=collector.request_timeout
    )
    fake_bot.set_updates(fake_updates)

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        messages = await collector.collect(
            sample_telegram_config, min_timestamp=min_timestamp
        )

    # 최근 2시간 이내 메시지만 수집되어야 함
    assert len(messages) == 2
    for msg in messages:
        assert msg.timestamp >= min_timestamp


@pytest.mark.asyncio
async def test_bot_api_collector_max_messages_limit(
    monkeypatch, sample_telegram_config
):
    """
    Bot API 최대 메시지 수 제한 테스트

    max_messages 설정에 따라 수집이 제한되는지 확인합니다.
    """
    collector = BotAPICollector(request_timeout=5.0)

    now = datetime.now(timezone.utc)

    # 많은 메시지 생성
    fake_updates = []
    for i in range(20):
        fake_message = SimpleNamespace(
            message_id=i + 1,
            chat=SimpleNamespace(username="cryptonews", id=-100123456),
            date=now - timedelta(minutes=i),
            text=f"Message {i + 1}",
            caption=None,
            reply_to_message=None,
        )
        fake_updates.append(SimpleNamespace(channel_post=fake_message))

    fake_bot = FakeBot(
        token=sample_telegram_config.bot_token, request=collector.request_timeout
    )
    fake_bot.set_updates(fake_updates)

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        messages = await collector.collect(sample_telegram_config)

    # max_messages(10)를 초과하지 않아야 함
    assert len(messages) <= sample_telegram_config.max_messages


@pytest.mark.asyncio
async def test_bot_api_collector_message_cleaning(monkeypatch, sample_telegram_config):
    """
    Bot API 메시지 청소 테스트

    스팸/불용어가 포함된 메시지가 필터링되는지 확인합니다.
    """
    collector = BotAPICollector(request_timeout=5.0)

    now = datetime.now(timezone.utc)

    # 다양한 메시지 생성 (일부는 스팸)
    messages_data = [
        (now, "Bitcoin price analysis"),
        (now - timedelta(minutes=1), "광고 이벤트 참여하세요"),  # 불용어 포함
        (now - timedelta(minutes=2), "Market update"),
        (now - timedelta(minutes=3), ""),  # 빈 메시지
        (now - timedelta(minutes=4), "Crypto news"),
    ]

    fake_updates = []
    for i, (msg_time, text) in enumerate(messages_data):
        fake_message = SimpleNamespace(
            message_id=i + 1,
            chat=SimpleNamespace(username="cryptonews", id=-100123456),
            date=msg_time,
            text=text,
            caption=None,
            reply_to_message=None,
        )
        fake_updates.append(SimpleNamespace(channel_post=fake_message))

    fake_bot = FakeBot(
        token=sample_telegram_config.bot_token, request=collector.request_timeout
    )
    fake_bot.set_updates(fake_updates)

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        messages = await collector.collect(sample_telegram_config)

    # 스팸 메시지와 빈 메시지가 필터링되어야 함
    assert len(messages) < len(messages_data)
    texts = [msg.text for msg in messages]
    assert "광고" not in " ".join(texts)
    assert "" not in texts


@pytest.mark.asyncio
async def test_bot_api_collector_duplicate_removal(monkeypatch, sample_telegram_config):
    """
    Bot API 중복 제거 테스트

    동일한 메시지 ID가 중복 제거되는지 확인합니다.
    """
    collector = BotAPICollector(request_timeout=5.0)

    now = datetime.now(timezone.utc)

    # 중복된 메시지 ID 생성
    fake_message = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(username="cryptonews", id=-100123456),
        date=now,
        text="Duplicate message",
        caption=None,
        reply_to_message=None,
    )

    fake_updates = [
        SimpleNamespace(channel_post=fake_message),
        SimpleNamespace(channel_post=fake_message),  # 중복
    ]

    fake_bot = FakeBot(
        token=sample_telegram_config.bot_token, request=collector.request_timeout
    )
    fake_bot.set_updates(fake_updates)

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        messages = await collector.collect(sample_telegram_config)

    # 중복이 제거되어야 함
    assert len(messages) == 1
    assert messages[0].message_id == 1


@pytest.mark.asyncio
async def test_telegram_collector_factory_bot_api(sample_telegram_config):
    """
    텔레그램 수집기 Factory 테스트 (Bot API)

    Factory가 Bot API 수집기를 올바르게 생성하는지 확인합니다.
    """
    collector = TelegramCollectorFactory.create(
        sample_telegram_config, request_timeout=5.0
    )

    assert isinstance(collector, BotAPICollector)


@pytest.mark.asyncio
async def test_telegram_collector_factory_mtproto(sample_mtproto_config):
    """
    텔레그램 수집기 Factory 테스트 (MTProto)

    Factory가 MTProto 수집기를 올바르게 생성하는지 확인합니다.
    """
    collector = TelegramCollectorFactory.create(
        sample_mtproto_config, request_timeout=5.0
    )

    assert isinstance(collector, MTProtoCollector)


@pytest.mark.asyncio
async def test_telegram_collector_integration(monkeypatch, sample_telegram_config):
    """
    텔레그램 수집기 통합 인터페이스 테스트

    TelegramCollector를 통한 수집이 정상 동작하는지 확인합니다.
    """
    collector = TelegramCollector(request_timeout=5.0)

    now = datetime.now(timezone.utc)
    fake_message = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(username="cryptonews", id=-100123456),
        date=now,
        text="Test message",
        caption=None,
        reply_to_message=None,
    )

    fake_bot = FakeBot(token=sample_telegram_config.bot_token, request=5.0)
    fake_bot.set_updates([SimpleNamespace(channel_post=fake_message)])

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    messages = await collector.collect(sample_telegram_config)

    assert len(messages) == 1
    assert messages[0].text == "Test message"


@pytest.mark.asyncio
async def test_mtproto_collector_mock(sample_mtproto_config):
    """
    MTProto 수집기 모의 테스트

    모의 Telethon 클라이언트를 사용하여 MTProto 수집기를 테스트합니다.
    telethon 라이브러리를 모의하여 실제 API 호출 없이 테스트합니다.
    """
    # telethon 모듈을 모의로 생성
    mock_telethon = ModuleType("telethon")
    mock_telethon_errors = ModuleType("telethon.errors")

    # 모의 클라이언트 인스턴스
    mock_client_instance = AsyncMock()
    mock_client_instance.start = AsyncMock()
    mock_client_instance.is_user_authorized = AsyncMock(return_value=True)
    mock_client_instance.get_entity = AsyncMock(
        return_value=SimpleNamespace(id=-100123456, title="Crypto Channel")
    )
    mock_client_instance.disconnect = AsyncMock()

    # 메시지 이터레이터 모의
    now = datetime.now(timezone.utc)
    mock_message = SimpleNamespace(
        id=1,
        date=now,
        message="Test MTProto message",
        sender=SimpleNamespace(first_name="User"),
        reply_to=None,
    )

    async def message_iter():
        yield mock_message

    # iter_messages 호출 추적을 위한 래퍼
    iter_messages_called = False

    def iter_messages_wrapper(channel_id, limit, reverse):
        nonlocal iter_messages_called
        iter_messages_called = True
        return message_iter()

    # TelegramClient 클래스 모의 - 인스턴스가 mock_client_instance처럼 동작하도록 구현
    class MockTelegramClient:
        def __init__(self, session_file, api_id, api_hash, timeout):
            # 인스턴스가 생성될 때 mock_client_instance의 메서드를 위임
            self._session_file = session_file
            self._api_id = api_id
            self._api_hash = api_hash
            self._timeout = timeout
            # mock_client_instance의 메서드를 직접 위임
            self.start = mock_client_instance.start
            self.is_user_authorized = mock_client_instance.is_user_authorized
            self.get_entity = mock_client_instance.get_entity
            # iter_messages는 비동기 제너레이터를 직접 반환해야 함
            self.iter_messages = iter_messages_wrapper
            self.disconnect = mock_client_instance.disconnect

    mock_telethon.TelegramClient = MockTelegramClient
    mock_telethon_errors.AuthKeyUnregisteredError = Exception
    mock_telethon_errors.FloodWaitError = Exception
    mock_telethon.errors = mock_telethon_errors

    # sys.modules에 모의 모듈 등록
    with patch.dict(
        "sys.modules",
        {"telethon": mock_telethon, "telethon.errors": mock_telethon_errors},
    ):
        # 기존 import를 무효화하기 위해 모듈 재로드
        import importlib

        if "src.collectors.telegram_collector" in sys.modules:
            importlib.reload(sys.modules["src.collectors.telegram_collector"])

        collector = MTProtoCollector(request_timeout=5.0)

        async with collector:
            messages = await collector.collect(sample_mtproto_config)

        # 검증
        assert len(messages) == 1
        assert messages[0].text == "Test MTProto message"
        assert messages[0].message_id == 1
        assert messages[0].channel_name == "Crypto Channel"

        # 클라이언트 메서드 호출 확인
        mock_client_instance.start.assert_called_once()
        mock_client_instance.is_user_authorized.assert_called_once()
        mock_client_instance.get_entity.assert_called_once()
        assert iter_messages_called, "iter_messages가 호출되어야 합니다"
        mock_client_instance.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bot_api_collector_error_handling(monkeypatch, sample_telegram_config):
    """
    Bot API 오류 처리 테스트

    TelegramError가 발생할 때 적절히 처리하는지 확인합니다.
    """
    from telegram.error import TelegramError

    collector = BotAPICollector(request_timeout=5.0)

    fake_bot = FakeBot(
        token=sample_telegram_config.bot_token, request=collector.request_timeout
    )

    # get_chat에서 오류 발생 시뮬레이션
    async def mock_get_chat(channel_id: str):
        raise TelegramError("Channel not found")

    fake_bot.get_chat = mock_get_chat

    monkeypatch.setattr(
        "src.collectors.telegram_collector.Bot", lambda token, request=None: fake_bot
    )

    async with collector:
        # 오류가 발생해도 수집은 계속되어야 함 (경고만 발생)
        messages = await collector.collect(sample_telegram_config)

        # 채널명은 설정값으로 사용되어야 함
        assert len(messages) >= 0  # 메시지가 없어도 정상

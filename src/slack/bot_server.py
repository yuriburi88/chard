"""
CHARD Slack Bot 서버

Socket Mode를 사용하여 Slack 이벤트를 수신하고 처리합니다.
Claude API를 통해 자연어 대화를 지원합니다.
로컬 PC에서 공인 IP 없이 실행 가능합니다.
"""

import asyncio
import contextlib
import logging
import os
import re
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


# 프로젝트 루트 설정
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 환경변수 로드
load_dotenv(PROJECT_ROOT / "config" / ".env")
load_dotenv(PROJECT_ROOT / ".env")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 동시 요청 큐 설정
MAX_QUEUE_SIZE = 10
_request_queue: deque = deque(maxlen=MAX_QUEUE_SIZE)
_queue_lock = threading.Lock()
_processing_channels: set[str] = set()


def create_app() -> App:
    """Slack Bolt App 인스턴스를 생성합니다."""
    bot_token = os.environ.get("SLACK_BOT_TOKEN")

    if not bot_token:
        logger.error("SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        raise ValueError("SLACK_BOT_TOKEN is required")

    app = App(token=bot_token)

    # 이벤트 핸들러 등록
    _register_handlers(app)

    logger.info("Slack App 인스턴스 생성 완료")
    return app


def _register_handlers(app: App) -> None:
    """이벤트 핸들러를 등록합니다."""

    @app.event("app_mention")
    def handle_app_mention(event: dict, say, client) -> None:
        """
        봇이 멘션되었을 때 처리합니다.
        예: @CHARD 시황 알려줘
        """
        user = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # 멘션 태그 제거
        clean_text = _remove_mention(text)

        if not clean_text.strip():
            from src.slack.message_formatter import format_help_message
            help_msg = format_help_message()
            say(
                text=help_msg["text"],
                blocks=help_msg.get("blocks"),
                thread_ts=thread_ts,
            )
            return

        logger.info(f"멘션 수신: user={user}, channel={channel}, "
                    f"text={clean_text[:50]}...")

        # 동시 요청 체크
        channel_key = f"{channel}:{thread_ts}"
        if not _can_process_request(channel_key):
            say(
                text="이전 요청을 처리 중입니다. 잠시만 기다려 주세요... ⏳",
                thread_ts=thread_ts,
            )
            return

        # 분석 시작 메시지 (즉시 응답)
        from src.slack.message_formatter import format_loading_message
        loading_msg = format_loading_message("분석")
        say(
            text=loading_msg["text"],
            blocks=loading_msg.get("blocks"),
            thread_ts=thread_ts,
        )

        # 비동기 처리
        try:
            response, should_upload = _process_with_claude(
                clean_text, channel, thread_ts, user
            )

            # 응답 전송
            say(
                text=response,
                thread_ts=thread_ts,
            )

            # 파일 첨부 (분석 완료 시)
            if should_upload:
                _upload_analysis_files(client, channel, thread_ts)

        except Exception as e:
            logger.error(f"Claude 처리 실패: {e}")
            from src.slack.message_formatter import format_error_message
            error_msg = format_error_message("general", str(e)[:100])
            say(
                text=error_msg["text"],
                blocks=error_msg.get("blocks"),
                thread_ts=thread_ts,
            )

        finally:
            _release_request(channel_key)

    @app.event("message")
    def handle_message(event: dict, say, client) -> None:
        """
        DM 메시지를 처리합니다.
        (채널 메시지는 멘션이 있을 때만 응답)
        """
        # 봇 자신의 메시지는 무시
        if event.get("bot_id"):
            return

        # 서브타입이 있는 메시지 무시 (편집, 삭제 등)
        if event.get("subtype"):
            return

        # DM인 경우만 처리 (channel이 D로 시작)
        channel = event.get("channel", "")
        if not channel.startswith("D"):
            return

        user = event.get("user")
        text = event.get("text", "")

        if not text.strip():
            return

        logger.info(f"DM 수신: user={user}, text={text[:50]}...")

        # 동시 요청 체크
        channel_key = f"{channel}:dm"
        if not _can_process_request(channel_key):
            say(text="이전 요청을 처리 중입니다. 잠시만 기다려 주세요... ⏳")
            return

        # 분석 시작 메시지
        from src.slack.message_formatter import format_loading_message
        loading_msg = format_loading_message()
        say(text=loading_msg["text"])

        # 비동기 처리
        try:
            response, should_upload = _process_with_claude(
                text, channel, None, user
            )
            say(text=response)

            # 파일 첨부
            if should_upload:
                _upload_analysis_files(client, channel, None)

        except Exception as e:
            logger.error(f"Claude 처리 실패: {e}")
            from src.slack.message_formatter import format_error_message
            error_msg = format_error_message("general")
            say(text=error_msg["text"])

        finally:
            _release_request(channel_key)

    @app.event("app_home_opened")
    def handle_app_home_opened(event: dict, client) -> None:
        """앱 홈 탭이 열렸을 때 처리합니다."""
        user_id = event.get("user")

        # 홈 탭에 간단한 안내 표시
        try:
            client.views_publish(
                user_id=user_id,
                view=_get_home_view(),
            )
        except Exception as e:
            logger.error(f"홈 탭 업데이트 실패: {e}")


def _get_home_view() -> dict[str, Any]:
    """홈 탭 뷰를 반환합니다."""
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "CHARD에 오신 것을 환영합니다! 🤖",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "CHARD는 암호화폐 및 매크로 경제 뉴스를 "
                           "분석하여 트레이딩 인사이트를 제공하는 AI입니다.",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🚀 시작하기*\n"
                           "채널에서 `@CHARD`를 멘션하여 대화하세요.",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📝 예시 명령어*\n"
                           "• `@CHARD 오늘 시황 어때?`\n"
                           "• `@CHARD 비트코인 분석해줘`\n"
                           "• `@CHARD RSS만 분석해줘`\n"
                           "• `@CHARD 키워드 알려줘`",
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 DM으로도 대화할 수 있습니다 | "
                               "분석은 1-2분 소요됩니다",
                    }
                ],
            },
        ],
    }


def _can_process_request(channel_key: str) -> bool:
    """
    요청을 처리할 수 있는지 확인합니다.
    동시 요청 큐잉을 통해 중복 처리를 방지합니다.
    """
    with _queue_lock:
        if channel_key in _processing_channels:
            return False
        if len(_request_queue) >= MAX_QUEUE_SIZE:
            return False
        _processing_channels.add(channel_key)
        _request_queue.append(channel_key)
        return True


def _release_request(channel_key: str) -> None:
    """요청 처리 완료 후 큐에서 제거합니다."""
    with _queue_lock:
        _processing_channels.discard(channel_key)
        with contextlib.suppress(ValueError):
            _request_queue.remove(channel_key)


def _remove_mention(text: str) -> str:
    """텍스트에서 멘션 태그를 제거합니다."""
    # <@U12345678> 형식의 멘션 제거
    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


def _process_with_claude(
    text: str,
    channel: str,
    thread_ts: str | None,
    user: str,
) -> tuple[str, bool]:
    """
    Claude API를 사용하여 메시지를 처리합니다.

    Args:
        text: 사용자 메시지
        channel: 채널 ID
        thread_ts: 스레드 타임스탬프
        user: 사용자 ID

    Returns:
        (응답 텍스트, 파일 업로드 필요 여부)
    """
    from src.slack.claude_agent import get_agent
    from src.slack.conversation import get_conversation_manager

    # 대화 히스토리 가져오기
    conv_manager = get_conversation_manager()
    history = conv_manager.get_history(channel, thread_ts)

    # Claude Agent로 처리
    agent = get_agent()

    # 동기적으로 비동기 함수 실행
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        response, updated_history = loop.run_until_complete(
            agent.process_message(text, history)
        )

        # 히스토리 업데이트
        conv_manager.update_history(channel, updated_history, thread_ts)

        # 분석 완료 여부 확인 (파일 업로드 트리거)
        should_upload = _should_upload_files(response)

        return response, should_upload

    finally:
        loop.close()


def _should_upload_files(response: str) -> bool:
    """응답 내용을 분석하여 파일 업로드가 필요한지 판단합니다."""
    # 분석 완료 키워드 확인
    upload_keywords = ["분석 완료", "✅", "리포트", "분석 결과"]
    return any(keyword in response for keyword in upload_keywords)


def _upload_analysis_files(
    client,
    channel: str,
    thread_ts: str | None,
) -> None:
    """분석 결과 파일을 업로드합니다."""
    try:
        from src.slack.file_uploader import FileUploader, get_latest_output_dir

        output_base = PROJECT_ROOT / "output"
        latest_dir = get_latest_output_dir(output_base)

        if not latest_dir:
            logger.warning("업로드할 분석 결과 디렉토리가 없습니다")
            return

        uploader = FileUploader(client)
        results = uploader.upload_analysis_files(
            output_dir=latest_dir,
            channel=channel,
            thread_ts=thread_ts,
            include_json=True,
            include_md=True,
        )

        if results:
            logger.info(f"파일 {len(results)}개 업로드 완료")
        else:
            logger.warning("업로드된 파일이 없습니다")

    except Exception as e:
        logger.error(f"파일 업로드 실패: {e}")


def run_bot() -> None:
    """Slack Bot을 실행합니다."""
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if not app_token:
        logger.error("SLACK_APP_TOKEN 환경변수가 설정되지 않았습니다.")
        raise ValueError("SLACK_APP_TOKEN is required for Socket Mode")

    app = create_app()
    handler = SocketModeHandler(app, app_token)

    logger.info("=" * 50)
    logger.info("CHARD Slack Bot 시작")
    logger.info("Socket Mode로 연결 중...")
    logger.info("Claude API 연동 활성화")
    logger.info("파일 첨부 기능 활성화")
    logger.info("=" * 50)

    try:
        handler.start()
    except KeyboardInterrupt:
        logger.info("Bot 종료 요청 수신")
    except Exception as e:
        logger.error(f"Bot 실행 중 오류 발생: {e}")
        raise
    finally:
        logger.info("CHARD Slack Bot 종료")


if __name__ == "__main__":
    run_bot()

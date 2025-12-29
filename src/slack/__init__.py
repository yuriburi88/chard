"""
CHARD Slack 연동 모듈

Slack에서 자연어로 CHARD AI와 대화하며 시장 분석을 요청하는 기능을 제공합니다.
Claude API를 통해 사용자의 의도를 파악하고, CHARD 파이프라인을 실행합니다.
"""

from src.slack.bot_server import create_app, run_bot
from src.slack.claude_agent import ClaudeAgent, get_agent
from src.slack.conversation import ConversationManager, get_conversation_manager
from src.slack.file_uploader import FileUploader
from src.slack.message_formatter import (
    format_analysis_result,
    format_error_message,
    format_help_message,
    format_loading_message,
)


__all__ = [
    # Bot Server
    "create_app",
    "run_bot",
    # Claude Agent
    "ClaudeAgent",
    "get_agent",
    # Conversation
    "ConversationManager",
    "get_conversation_manager",
    # File Uploader
    "FileUploader",
    # Message Formatter
    "format_analysis_result",
    "format_error_message",
    "format_help_message",
    "format_loading_message",
]

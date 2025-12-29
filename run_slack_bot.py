"""
CHARD Slack Bot 실행 스크립트

Slack에서 자연어로 CHARD AI와 대화하며 시장 분석을 요청할 수 있습니다.

사용법:
    python run_slack_bot.py

필수 환경변수:
    SLACK_BOT_TOKEN - Slack Bot Token (xoxb-...)
    SLACK_APP_TOKEN - Slack App Token (xapp-...) - Socket Mode용
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.slack.bot_server import run_bot


if __name__ == "__main__":
    run_bot()

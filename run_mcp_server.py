#!/usr/bin/env python
"""
CHARD MCP 서버 실행 스크립트

Claude Desktop이나 다른 MCP 클라이언트와 연결하기 위한 진입점입니다.
"""

import sys
from pathlib import Path


# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.server import main


if __name__ == "__main__":
    main()

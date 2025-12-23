"""
CHARD MCP Server 메인 파일

MCP 서버를 실행하고 CHARD 기능을 Claude에 연결합니다.
"""

import asyncio
import sys
import os
from pathlib import Path

# CHARD 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, Resource, TextContent
except ImportError:
    print("Error: mcp package not installed. Please run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from chard_mcp.tools import register_tools
from chard_mcp.resources import register_resources


async def run_server():
    """CHARD MCP 서버 실행"""
    try:
        # 서버 생성
        server = Server("chard")

        # 도구 및 리소스 등록
        register_tools(server)
        register_resources(server)

        print("CHARD MCP Server starting...", file=sys.stderr)

        # stdio를 통한 통신 시작
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )

    except Exception as e:
        print(f"Error starting CHARD MCP server: {e}", file=sys.stderr)
        raise


def main():
    """메인 엔트리포인트"""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nCHARD MCP Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

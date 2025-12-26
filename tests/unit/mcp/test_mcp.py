"""
CHARD MCP 서버 테스트 스크립트

MCP 서버가 제대로 작동하는지 테스트합니다.
"""

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.resources import read_config, read_latest_report
from src.mcp.tools import (
    handle_get_latest_keywords,
    handle_list_rss_feeds,
    handle_list_telegram_channels,
)


async def test_tools():
    """도구 테스트"""
    print("=" * 60)
    print("CHARD MCP Tools Test")
    print("=" * 60)

    # 1. RSS 피드 목록
    print("\n1. Testing list_rss_feeds...")
    try:
        result = await handle_list_rss_feeds()
        print(result[0].text)
        print("[OK] PASS")
    except Exception as e:
        print(f"[FAIL] {e}")

    # 2. Telegram 채널 목록
    print("\n2. Testing list_telegram_channels...")
    try:
        result = await handle_list_telegram_channels()
        print(result[0].text)
        print("[OK] PASS")
    except Exception as e:
        print(f"[FAIL] {e}")

    # 3. 최신 키워드 (데이터가 있을 경우에만)
    print("\n3. Testing get_latest_keywords...")
    try:
        result = await handle_get_latest_keywords({"top_n": 5})
        print(result[0].text[:500])  # 처음 500자만 출력
        print("[OK] PASS (or no data)")
    except Exception as e:
        print(f"[WARN] No analysis data found (expected if not run yet): {e}")


async def test_resources():
    """리소스 테스트"""
    print("\n" + "=" * 60)
    print("CHARD MCP Resources Test")
    print("=" * 60)

    # 1. Config 읽기
    print("\n1. Testing read_config...")
    try:
        result = await read_config()
        config_text = result[0].text
        print(f"Config length: {len(config_text)} chars")
        print(f"First 200 chars: {config_text[:200]}...")
        print("[OK] PASS")
    except Exception as e:
        print(f"[FAIL] {e}")

    # 2. 최신 리포트 (있을 경우에만)
    print("\n2. Testing read_latest_report...")
    try:
        result = await read_latest_report()
        report_text = result[0].text
        print(f"Report length: {len(report_text)} chars")
        print(f"First 200 chars: {report_text[:200]}...")
        print("[OK] PASS (or no report)")
    except Exception as e:
        print(f"[WARN] No report found (expected if not run yet): {e}")


async def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("CHARD MCP Server Test Suite")
    print("=" * 60 + "\n")

    await test_tools()
    await test_resources()

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nIf all tests passed, your MCP server is ready to use!")
    print("Next step: Configure Claude Desktop and restart it.")


if __name__ == "__main__":
    asyncio.run(main())

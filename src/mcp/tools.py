"""
CHARD MCP Tools

CHARD 기능을 MCP 도구로 노출합니다.
"""

import json
import sys
from pathlib import Path


# CHARD 프로젝트 import
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.types import TextContent, Tool

from mcp.server import Server
from src.config_manager import ConfigManager


# Config 파일 및 .env 절대 경로
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yml"
ENV_PATH = PROJECT_ROOT / ".env"


def register_tools(server: Server):
    """CHARD 도구를 MCP 서버에 등록"""

    @server.list_tools()
    async def list_tools():
        """사용 가능한 도구 목록 반환"""
        return [
            Tool(
                name="collect_rss",
                description="RSS 피드에서 최근 뉴스를 수집합니다. 특정 피드나 모든 피드를 수집할 수 있습니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "feed_name": {
                            "type": "string",
                            "description": "수집할 RSS 피드 이름 (config.yml에 정의된 이름). 비워두면 모든 피드를 수집합니다.",
                        },
                        "hours_back": {
                            "type": "integer",
                            "description": "수집할 시간 범위 (시간 단위)",
                            "default": 24,
                        },
                    },
                },
            ),
            Tool(
                name="collect_telegram",
                description="Telegram 채널에서 최근 메시지를 수집합니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "수집할 Telegram 채널 ID (예: coinnesskr)",
                        },
                        "max_messages": {
                            "type": "integer",
                            "description": "최대 수집 메시지 수",
                            "default": 100,
                        },
                    },
                    "required": ["channel_id"],
                },
            ),
            Tool(
                name="run_full_analysis",
                description="전체 파이프라인을 실행합니다: 데이터 수집 → 키워드 분석 → 내러티브 생성 → 리포트 작성",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skip_collection": {
                            "type": "boolean",
                            "description": "데이터 수집을 건너뛰고 기존 데이터로 분석 (기본값: false)",
                            "default": False,
                        }
                    },
                },
            ),
            Tool(
                name="get_latest_keywords",
                description="최신 분석 결과에서 주요 키워드를 조회합니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "top_n": {
                            "type": "integer",
                            "description": "조회할 상위 키워드 개수",
                            "default": 10,
                        },
                        "category": {
                            "type": "string",
                            "enum": ["all", "macro", "crypto_native", "crypto_macro"],
                            "description": "키워드 카테고리 필터",
                            "default": "all",
                        },
                    },
                },
            ),
            Tool(
                name="list_rss_feeds",
                description="config.yml에 설정된 RSS 피드 목록을 조회합니다.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_telegram_channels",
                description="config.yml에 설정된 Telegram 채널 목록을 조회합니다.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """도구 호출 처리"""
        try:
            if name == "collect_rss":
                return await handle_collect_rss(arguments)
            elif name == "collect_telegram":
                return await handle_collect_telegram(arguments)
            elif name == "run_full_analysis":
                return await handle_run_full_analysis(arguments)
            elif name == "get_latest_keywords":
                return await handle_get_latest_keywords(arguments)
            elif name == "list_rss_feeds":
                return await handle_list_rss_feeds()
            elif name == "list_telegram_channels":
                return await handle_list_telegram_channels()
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [
                TextContent(
                    type="text", text=f"Error executing tool '{name}': {str(e)}"
                )
            ]


async def handle_collect_rss(args: dict):
    """RSS 수집 처리"""
    feed_name = args.get("feed_name")
    hours_back = args.get("hours_back", 24)

    config_manager = ConfigManager(str(CONFIG_PATH), str(ENV_PATH))
    app_config = config_manager.load()
    rss_sources = app_config.rss_sources

    if feed_name:
        # 특정 피드 수집
        target_feed = None
        for source in rss_sources:
            if source.name == feed_name:
                target_feed = source
                break

        if not target_feed:
            available_feeds = [s.name for s in rss_sources]
            return [
                TextContent(
                    type="text",
                    text=f"RSS 피드 '{feed_name}'를 찾을 수 없습니다.\n\n사용 가능한 피드:\n"
                    + "\n".join(f"- {name}" for name in available_feeds),
                )
            ]

        return [
            TextContent(
                type="text",
                text=f"RSS 피드 '{feed_name}'에서 최근 {hours_back}시간 동안의 기사 수집을 시작합니다.\n\n"
                + "이 작업은 실제 main.py를 실행하여 수집합니다.\n"
                + "현재는 데모 모드로, 실제 구현은 main.py와 통합이 필요합니다.",
            )
        ]
    else:
        # 모든 피드 수집
        feed_count = len(rss_sources)
        feed_list = "\n".join(f"- {s.name}" for s in rss_sources)

        return [
            TextContent(
                type="text",
                text=f"모든 RSS 피드({feed_count}개)에서 최근 {hours_back}시간 동안의 기사를 수집합니다.\n\n"
                + f"피드 목록:\n{feed_list}\n\n"
                + "실제 수집은 main.py를 실행합니다.",
            )
        ]


async def handle_collect_telegram(args: dict):
    """Telegram 수집 처리"""
    channel_id = args["channel_id"]
    max_messages = args.get("max_messages", 100)

    config_manager = ConfigManager(str(CONFIG_PATH), str(ENV_PATH))
    app_config = config_manager.load()
    telegram_sources = app_config.telegram_sources

    # 채널 존재 확인
    target_channel = None
    for source in telegram_sources:
        if source.channel_id == channel_id:
            target_channel = source
            break

    if not target_channel:
        available_channels = [s.channel_id for s in telegram_sources]
        return [
            TextContent(
                type="text",
                text=f"Telegram 채널 '{channel_id}'를 찾을 수 없습니다.\n\n사용 가능한 채널:\n"
                + "\n".join(f"- {cid}" for cid in available_channels),
            )
        ]

    return [
        TextContent(
            type="text",
            text=f"Telegram 채널 '{channel_id}'에서 최대 {max_messages}개의 메시지를 수집합니다.\n\n"
            + "실제 수집은 main.py를 실행합니다.",
        )
    ]


async def handle_run_full_analysis(args: dict):
    """전체 분석 파이프라인 실행"""
    skip_collection = args.get("skip_collection", False)

    if skip_collection:
        message = "기존 데이터로 분석을 시작합니다.\n\n"
    else:
        message = (
            "전체 파이프라인을 실행합니다:\n"
            + "1. RSS 및 Telegram 데이터 수집\n"
            + "2. 데이터 전처리 및 정규화\n"
            + "3. 키워드 추출 및 분석\n"
            + "4. 내러티브 생성\n"
            + "5. 리포트 작성\n\n"
        )

    message += "실행 중... (실제 구현은 main.py 통합 필요)\n\n"
    message += "완료 후 'get_latest_keywords' 또는 리소스 조회를 통해 결과를 확인할 수 있습니다."

    return [TextContent(type="text", text=message)]


async def handle_get_latest_keywords(args: dict):
    """최신 키워드 조회"""
    top_n = args.get("top_n", 10)
    category = args.get("category", "all")

    # 최신 output 디렉토리 찾기
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return [
            TextContent(
                type="text",
                text="분석 결과를 찾을 수 없습니다. 먼저 'run_full_analysis'를 실행하세요.",
            )
        ]

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return [TextContent(type="text", text="분석 결과를 찾을 수 없습니다.")]

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # 분석 파일 찾기 (예: analysis_*.json)
    analysis_files = list(latest_dir.glob("analysis_*.json"))

    if not analysis_files:
        return [
            TextContent(
                type="text", text=f"{date_str}의 분석 결과 파일을 찾을 수 없습니다."
            )
        ]

    # 첫 번째 분석 파일 읽기
    with open(analysis_files[0], encoding="utf-8") as f:
        analysis_data = json.load(f)

    # 키워드 추출
    keywords = analysis_data.get("aggregated_keywords", [])

    if not keywords:
        return [
            TextContent(type="text", text=f"{date_str}의 키워드 데이터가 비어있습니다.")
        ]

    # 카테고리 필터링
    if category != "all":
        keywords = [kw for kw in keywords if kw.get("category") == category]

    # 상위 N개 선택
    top_keywords = keywords[:top_n]

    # 결과 포맷팅
    result = f"📊 {date_str} 주요 키워드 (상위 {len(top_keywords)}개)\n\n"

    for i, kw in enumerate(top_keywords, 1):
        term = kw.get("term", "Unknown")
        score = kw.get("score", 0)
        cat = kw.get("category", "N/A")
        occurrence = kw.get("occurrence_count", 0)
        sources = kw.get("sources", [])

        result += f"{i}. {term}\n"
        result += f"   점수: {score:.1f}\n"
        result += f"   카테고리: {cat}\n"
        result += f"   출현 빈도: {occurrence}회\n"
        result += f"   출처: {len(sources)}개\n\n"

    return [TextContent(type="text", text=result)]


async def handle_list_rss_feeds():
    """RSS 피드 목록 조회"""
    config_manager = ConfigManager(str(CONFIG_PATH), str(ENV_PATH))
    app_config = config_manager.load()
    rss_sources = app_config.rss_sources

    result = f"[RSS] 설정된 RSS 피드 ({len(rss_sources)}개)\n\n"

    for i, source in enumerate(rss_sources, 1):
        result += f"{i}. {source.name}\n"
        result += f"   URL: {source.url}\n"
        result += f"   우선순위: {source.priority}\n"
        result += f"   최대 기사: {source.max_articles}개\n\n"

    return [TextContent(type="text", text=result)]


async def handle_list_telegram_channels():
    """Telegram 채널 목록 조회"""
    config_manager = ConfigManager(str(CONFIG_PATH), str(ENV_PATH))
    app_config = config_manager.load()
    telegram_sources = app_config.telegram_sources

    result = f"[TELEGRAM] 설정된 Telegram 채널 ({len(telegram_sources)}개)\n\n"

    for i, source in enumerate(telegram_sources, 1):
        result += f"{i}. {source.channel_id}\n"
        result += f"   이름: {source.name}\n"
        result += f"   인증 방식: {source.auth_method}\n"
        result += f"   최대 메시지: {source.max_messages}개\n\n"

    return [TextContent(type="text", text=result)]

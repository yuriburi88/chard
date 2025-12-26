"""
CHARD MCP Resources

CHARD 데이터를 MCP 리소스로 노출합니다.
"""

import json
import sys
from pathlib import Path


# CHARD 프로젝트 import
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.types import Resource, TextContent

from mcp.server import Server


# 프로젝트 경로
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yml"
OUTPUT_DIR = PROJECT_ROOT / "output"


def register_resources(server: Server):
    """CHARD 리소스를 MCP 서버에 등록"""

    @server.list_resources()
    async def list_resources():
        """사용 가능한 리소스 목록 반환"""
        return [
            Resource(
                uri="chard://config",
                name="CHARD Configuration",
                description="CHARD 프로젝트 설정 파일 (config.yml)",
                mimeType="application/x-yaml",
            ),
            Resource(
                uri="chard://reports/latest",
                name="Latest Report",
                description="최신 분석 리포트 (마크다운 형식)",
                mimeType="text/markdown",
            ),
            Resource(
                uri="chard://data/latest",
                name="Latest Collected Data",
                description="최신 수집 데이터 (JSON 형식)",
                mimeType="application/json",
            ),
            Resource(
                uri="chard://analysis/latest",
                name="Latest Analysis",
                description="최신 분석 결과 (키워드, 내러티브 등)",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str):
        """리소스 읽기"""
        try:
            if uri == "chard://config":
                return await read_config()
            elif uri == "chard://reports/latest":
                return await read_latest_report()
            elif uri == "chard://data/latest":
                return await read_latest_data()
            elif uri == "chard://analysis/latest":
                return await read_latest_analysis()
            else:
                raise ValueError(f"Unknown resource: {uri}")
        except Exception as e:
            return [
                TextContent(
                    type="text", text=f"Error reading resource '{uri}': {str(e)}"
                )
            ]


async def read_config():
    """config.yml 읽기"""
    config_path = PROJECT_ROOT / "config" / "config.yml"

    if not config_path.exists():
        return [TextContent(type="text", text="config.yml 파일을 찾을 수 없습니다.")]

    with open(config_path, encoding="utf-8") as f:
        config_content = f.read()

    return [TextContent(type="text", text=config_content)]


async def read_latest_report():
    """최신 리포트 읽기"""
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return [
            TextContent(
                type="text", text="리포트를 찾을 수 없습니다. 먼저 분석을 실행하세요."
            )
        ]

    # 날짜별 디렉토리 찾기 (최신순)
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return [TextContent(type="text", text="리포트를 찾을 수 없습니다.")]

    # 최신 디렉토리에서 리포트 파일 찾기
    latest_dir = date_dirs[0]
    report_files = list(latest_dir.glob("report_*.md"))

    if not report_files:
        return [
            TextContent(
                type="text", text=f"{latest_dir.name}의 리포트 파일을 찾을 수 없습니다."
            )
        ]

    # 가장 최근 리포트 읽기
    latest_report = sorted(report_files, reverse=True)[0]

    with open(latest_report, encoding="utf-8") as f:
        report_content = f.read()

    return [
        TextContent(type="text", text=f"# {latest_dir.name} 리포트\n\n{report_content}")
    ]


async def read_latest_data():
    """최신 수집 데이터 읽기"""
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return [TextContent(type="text", text="수집 데이터를 찾을 수 없습니다.")]

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return [TextContent(type="text", text="수집 데이터를 찾을 수 없습니다.")]

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # collected_*_raw.json 파일 찾기
    data_files = list(latest_dir.glob("collected_*_raw.json"))

    if not data_files:
        return [
            TextContent(
                type="text", text=f"{date_str}의 수집 데이터 파일을 찾을 수 없습니다."
            )
        ]

    # 모든 데이터 파일 통합
    all_items = []
    rss_count = 0
    telegram_count = 0

    for data_file in data_files:
        with open(data_file, encoding="utf-8") as f:
            items = json.load(f)
            all_items.extend(items)

            # 통계
            for item in items:
                if item.get("source") == "rss":
                    rss_count += 1
                elif item.get("source") == "telegram":
                    telegram_count += 1

    # 요약 정보 생성
    summary = f"📊 {date_str} 수집 데이터 요약\n\n"
    summary += f"전체 아이템: {len(all_items)}개\n"
    summary += f"- RSS 기사: {rss_count}개\n"
    summary += f"- Telegram 메시지: {telegram_count}개\n\n"

    # 샘플 데이터 (최근 5개)
    summary += "최근 수집 아이템 (최대 5개):\n\n"
    for i, item in enumerate(all_items[:5], 1):
        source_type = item.get("source", "Unknown")
        text = (
            item.get("text", "")[:100] + "..."
            if len(item.get("text", "")) > 100
            else item.get("text", "")
        )
        timestamp = item.get("timestamp", "N/A")

        summary += f"{i}. [{source_type}] {timestamp}\n"
        summary += f"   {text}\n\n"

    return [TextContent(type="text", text=summary)]


async def read_latest_analysis():
    """최신 분석 결과 읽기"""
    output_dir = PROJECT_ROOT / "output"

    if not output_dir.exists():
        return [TextContent(type="text", text="분석 결과를 찾을 수 없습니다.")]

    # 날짜별 디렉토리 찾기
    date_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], reverse=True)

    if not date_dirs:
        return [TextContent(type="text", text="분석 결과를 찾을 수 없습니다.")]

    latest_dir = date_dirs[0]
    date_str = latest_dir.name

    # analysis_*.json 파일 찾기
    analysis_files = list(latest_dir.glob("analysis_*.json"))

    if not analysis_files:
        return [
            TextContent(type="text", text=f"{date_str}의 분석 결과를 찾을 수 없습니다.")
        ]

    # 최신 분석 파일 읽기
    latest_analysis = sorted(analysis_files, reverse=True)[0]

    with open(latest_analysis, encoding="utf-8") as f:
        analysis_data = json.load(f)

    # 분석 요약 생성
    summary = f"📈 {date_str} 분석 결과\n\n"

    # 키워드
    keywords = analysis_data.get("aggregated_keywords", [])
    summary += f"주요 키워드: {len(keywords)}개\n\n"

    if keywords:
        summary += "상위 10개 키워드:\n"
        for i, kw in enumerate(keywords[:10], 1):
            term = kw.get("term", "Unknown")
            score = kw.get("score", 0)
            summary += f"{i}. {term} (점수: {score:.1f})\n"

    summary += "\n"

    # 내러티브
    narratives = analysis_data.get("narratives", {})
    if narratives:
        summary += "생성된 내러티브:\n"
        for category, text in narratives.items():
            if isinstance(text, list):
                summary += f"- {category}: {len(text)}개 문단\n"
            else:
                summary += f"- {category}: 생성됨\n"

    summary += "\n\n전체 JSON 데이터:\n\n"
    summary += json.dumps(analysis_data, ensure_ascii=False, indent=2)

    return [TextContent(type="text", text=summary)]

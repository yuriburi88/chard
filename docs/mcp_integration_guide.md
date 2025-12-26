# CHARD MCP 통합 가이드

## 목차
1. [MCP 서버 구축](#1-mcp-서버-구축)
2. [CHARD 프로젝트 통합](#2-chard-프로젝트-통합)
3. [Claude Desktop 연결](#3-claude-desktop-연결)
4. [실전 예제](#4-실전-예제)

---

## 1. MCP 서버 구축

### 1.1 필요한 패키지 설치

```bash
pip install mcp anthropic-mcp-sdk
```

### 1.2 MCP 서버 파일 구조

```
chard/
├── mcp/
│   ├── __init__.py
│   ├── server.py          # MCP 서버 메인
│   ├── tools.py           # 도구 정의
│   ├── resources.py       # 리소스 정의
│   └── handlers.py        # 요청 핸들러
├── main.py
└── config.yml
```

### 1.3 실제 MCP 서버 구현

#### `mcp/server.py`

```python
import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from .tools import register_tools
from .resources import register_resources


async def run_server():
    """CHARD MCP 서버 실행"""
    server = Server("chard-server")

    # 도구 및 리소스 등록
    register_tools(server)
    register_resources(server)

    # stdio를 통한 통신 시작
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(run_server())
```

#### `mcp/tools.py`

```python
from mcp.server import Server
from mcp.types import Tool, TextContent
import sys
import os

# CHARD 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_manager import ConfigManager
from src.collectors.rss_collector import RSSCollector
from src.collectors.telegram_collector import TelegramCollectorFactory


def register_tools(server: Server):
    """CHARD 도구 등록"""

    @server.list_tools()
    async def list_tools():
        """사용 가능한 도구 목록"""
        return [
            Tool(
                name="collect_rss",
                description="RSS 피드에서 최근 기사를 수집합니다",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "feed_name": {
                            "type": "string",
                            "description": "수집할 RSS 피드 이름"
                        },
                        "hours_back": {
                            "type": "integer",
                            "description": "수집할 시간 범위 (시간)",
                            "default": 24
                        }
                    },
                    "required": ["feed_name"]
                }
            ),
            Tool(
                name="collect_telegram",
                description="Telegram 채널에서 메시지를 수집합니다",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Telegram 채널 ID"
                        },
                        "max_messages": {
                            "type": "integer",
                            "description": "최대 수집 메시지 수",
                            "default": 100
                        }
                    },
                    "required": ["channel_id"]
                }
            ),
            Tool(
                name="analyze_keywords",
                description="수집된 데이터에서 키워드를 분석합니다",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "분석할 날짜 (YYYY-MM-DD)"
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "상위 N개 키워드",
                            "default": 10
                        }
                    },
                    "required": ["date"]
                }
            ),
            Tool(
                name="get_latest_report",
                description="최신 분석 리포트를 조회합니다",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "markdown"],
                            "description": "리포트 형식",
                            "default": "markdown"
                        }
                    }
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """도구 실행"""

        if name == "collect_rss":
            return await handle_collect_rss(arguments)

        elif name == "collect_telegram":
            return await handle_collect_telegram(arguments)

        elif name == "analyze_keywords":
            return await handle_analyze_keywords(arguments)

        elif name == "get_latest_report":
            return await handle_get_latest_report(arguments)

        else:
            raise ValueError(f"Unknown tool: {name}")


async def handle_collect_rss(args: dict):
    """RSS 수집 처리"""
    feed_name = args["feed_name"]
    hours_back = args.get("hours_back", 24)

    # ConfigManager를 통해 설정 로드
    config = ConfigManager("config.yml")
    rss_sources = config.get_rss_sources()

    # 해당 피드 찾기
    target_feed = None
    for source in rss_sources:
        if source.name == feed_name:
            target_feed = source
            break

    if not target_feed:
        return [TextContent(
            type="text",
            text=f"RSS 피드 '{feed_name}'를 찾을 수 없습니다."
        )]

    # RSS 수집 실행
    collector = RSSCollector()
    articles = await collector.collect(target_feed)

    return [TextContent(
        type="text",
        text=f"RSS 피드 '{feed_name}'에서 {len(articles)}개의 기사를 수집했습니다."
    )]


async def handle_collect_telegram(args: dict):
    """Telegram 수집 처리"""
    channel_id = args["channel_id"]
    max_messages = args.get("max_messages", 100)

    # Telegram 수집 실행
    # 실제 구현 필요

    return [TextContent(
        type="text",
        text=f"Telegram 채널 '{channel_id}'에서 메시지를 수집했습니다."
    )]


async def handle_analyze_keywords(args: dict):
    """키워드 분석 처리"""
    date = args["date"]
    top_n = args.get("top_n", 10)

    # 키워드 분석 실행
    # 실제 구현 필요

    return [TextContent(
        type="text",
        text=f"{date}의 상위 {top_n}개 키워드를 분석했습니다."
    )]


async def handle_get_latest_report(args: dict):
    """최신 리포트 조회"""
    format_type = args.get("format", "markdown")

    # 최신 리포트 읽기
    # 실제 구현 필요

    return [TextContent(
        type="text",
        text=f"최신 리포트 ({format_type} 형식)"
    )]
```

#### `mcp/resources.py`

```python
from mcp.server import Server
from mcp.types import Resource, TextContent
import os
import json
import glob
from datetime import datetime


def register_resources(server: Server):
    """CHARD 리소스 등록"""

    @server.list_resources()
    async def list_resources():
        """사용 가능한 리소스 목록"""
        return [
            Resource(
                uri="chard://config",
                name="Configuration",
                description="CHARD 프로젝트 설정",
                mimeType="application/yaml"
            ),
            Resource(
                uri="chard://reports/latest",
                name="Latest Report",
                description="최신 분석 리포트",
                mimeType="text/markdown"
            ),
            Resource(
                uri="chard://data/{date}",
                name="Collected Data",
                description="특정 날짜의 수집 데이터",
                mimeType="application/json"
            )
        ]

    @server.read_resource()
    async def read_resource(uri: str):
        """리소스 읽기"""

        if uri == "chard://config":
            return await read_config()

        elif uri == "chard://reports/latest":
            return await read_latest_report()

        elif uri.startswith("chard://data/"):
            date = uri.split("/")[-1]
            return await read_collected_data(date)

        else:
            raise ValueError(f"Unknown resource: {uri}")


async def read_config():
    """설정 파일 읽기"""
    with open("config.yml", "r", encoding="utf-8") as f:
        config_content = f.read()

    return [TextContent(
        type="text",
        text=config_content,
        uri="chard://config"
    )]


async def read_latest_report():
    """최신 리포트 읽기"""
    # output 디렉토리에서 가장 최근 파일 찾기
    output_dirs = sorted(glob.glob("output/20*"), reverse=True)

    if not output_dirs:
        return [TextContent(
            type="text",
            text="리포트를 찾을 수 없습니다.",
            uri="chard://reports/latest"
        )]

    latest_dir = output_dirs[0]
    report_files = glob.glob(f"{latest_dir}/report_*.md")

    if not report_files:
        return [TextContent(
            type="text",
            text="리포트 파일을 찾을 수 없습니다.",
            uri="chard://reports/latest"
        )]

    with open(report_files[0], "r", encoding="utf-8") as f:
        report_content = f.read()

    return [TextContent(
        type="text",
        text=report_content,
        uri="chard://reports/latest"
    )]


async def read_collected_data(date: str):
    """수집 데이터 읽기"""
    data_dir = f"output/{date}"

    if not os.path.exists(data_dir):
        return [TextContent(
            type="text",
            text=f"{date}의 데이터를 찾을 수 없습니다.",
            uri=f"chard://data/{date}"
        )]

    # collected_*_raw.json 파일 읽기
    data_files = glob.glob(f"{data_dir}/collected_*_raw.json")

    if not data_files:
        return [TextContent(
            type="text",
            text=f"{date}의 수집 데이터를 찾을 수 없습니다.",
            uri=f"chard://data/{date}"
        )]

    # 모든 데이터 파일 병합
    all_data = []
    for file_path in data_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_data.extend(data)

    return [TextContent(
        type="text",
        text=json.dumps({"date": date, "items": all_data}, ensure_ascii=False, indent=2),
        uri=f"chard://data/{date}"
    )]
```

---

## 2. CHARD 프로젝트 통합

### 2.1 MCP 서버 실행 스크립트 생성

`run_mcp_server.py`:

```python
#!/usr/bin/env python
"""
CHARD MCP 서버 실행 스크립트
"""

import sys
import os

# CHARD 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import run_server
import asyncio

if __name__ == "__main__":
    asyncio.run(run_server())
```

### 2.2 실행 권한 부여 (Linux/Mac)

```bash
chmod +x run_mcp_server.py
```

---

## 3. Claude Desktop 연결

### 3.1 Claude Desktop 설정 파일 수정

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "chard": {
      "command": "python",
      "args": [
        "C:\\Users\\Richard\\Test\\CHARD\\chard\\run_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\Richard\\Test\\CHARD\\chard"
      }
    }
  }
}
```

### 3.2 Claude Desktop 재시작

설정 후 Claude Desktop을 재시작하면 CHARD MCP 서버가 자동으로 연결됩니다.

---

## 4. 실전 예제

### 4.1 Claude Desktop에서 사용

```
사용자: CHARD에서 최근 24시간 동안 CoinDesk RSS 피드를 수집해줘

Claude: collect_rss 도구를 사용하여 CoinDesk 피드를 수집하겠습니다.
[MCP 도구 호출]
RSS 피드 'CoinDesk'에서 25개의 기사를 수집했습니다.
```

```
사용자: 최신 분석 리포트를 보여줘

Claude: [MCP 리소스 조회]
# CHARD 일일 리포트 - 2025-12-10

## 주요 키워드
1. 금리 인하 (점수: 275.9)
2. ETF (점수: 102.6)
...
```

### 4.2 Python 스크립트에서 사용

```python
from anthropic import Anthropic

client = Anthropic(api_key="your-api-key")

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=[
        {
            "type": "custom",
            "name": "collect_rss",
            "mcp_server": "chard"
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "CoinDesk에서 최근 뉴스를 수집해줘"
        }
    ]
)
```

---

## 5. 고급 기능

### 5.1 인증 추가

```python
# mcp/auth.py
class CHARDAuth:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify(self, request_key: str) -> bool:
        return request_key == self.api_key
```

### 5.2 로깅 추가

```python
import logging

logger = logging.getLogger("chard-mcp")
logger.setLevel(logging.INFO)

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    logger.info(f"Tool called: {name} with args: {arguments}")
    # ...
```

### 5.3 에러 핸들링

```python
from mcp.types import ErrorData

try:
    result = await handle_collect_rss(arguments)
    return result
except Exception as e:
    return ErrorData(
        code="COLLECTION_ERROR",
        message=f"RSS 수집 실패: {str(e)}"
    )
```

---

## 6. 테스트

### 6.1 MCP 서버 단독 테스트

```python
# test_mcp.py
import asyncio
from mcp.server import CHARDMCPServer

async def test_server():
    server = CHARDMCPServer()

    # 도구 목록 테스트
    tools = await server.handle_list_tools()
    print("Tools:", tools)

    # 도구 호출 테스트
    result = await server.handle_call_tool(
        "collect_rss",
        {"feed_name": "CoinDesk", "hours_back": 24}
    )
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(test_server())
```

### 6.2 실행

```bash
python test_mcp.py
```

---

## 7. 문제 해결

### MCP 서버가 연결되지 않을 때

1. **로그 확인**:
   ```bash
   # Claude Desktop 로그 확인
   tail -f ~/Library/Logs/Claude/mcp.log  # Mac
   ```

2. **Python 경로 확인**:
   ```bash
   which python
   # Claude Desktop 설정의 command와 일치하는지 확인
   ```

3. **수동 실행 테스트**:
   ```bash
   python run_mcp_server.py
   ```

---

## 8. 다음 단계

1. ✅ MCP 서버 기본 구조 생성
2. ✅ 도구 및 리소스 정의
3. ⬜ 실제 CHARD 기능 통합
4. ⬜ 인증 및 보안 추가
5. ⬜ 에러 핸들링 개선
6. ⬜ 테스트 작성
7. ⬜ 문서화 완성

---

## 참고 자료

- [MCP 공식 문서](https://modelcontextprotocol.io)
- [Anthropic MCP SDK](https://github.com/anthropics/anthropic-sdk-python)
- [MCP 서버 예제](https://github.com/anthropics/anthropic-quickstarts)

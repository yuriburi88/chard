"""
MCP (Model Context Protocol) 서버 예제

CHARD 프로젝트를 위한 MCP 서버 구축 예시입니다.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class Tool:
    """MCP 도구 정의"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class Resource:
    """MCP 리소스 정의"""
    uri: str
    name: str
    description: str
    mime_type: str


class MCPServer:
    """
    기본 MCP 서버 구현

    CHARD 프로젝트의 RSS/Telegram 수집 기능을 MCP 프로토콜로 노출합니다.
    """

    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.tools: Dict[str, Tool] = {}
        self.resources: Dict[str, Resource] = {}

    def register_tool(self, tool: Tool):
        """도구 등록"""
        self.tools[tool.name] = tool

    def register_resource(self, resource: Resource):
        """리소스 등록"""
        self.resources[resource.uri] = resource

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """초기화 요청 처리"""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self.name,
                "version": self.version
            },
            "capabilities": {
                "tools": {},
                "resources": {}
            }
        }

    async def handle_list_tools(self) -> Dict[str, Any]:
        """등록된 도구 목록 반환"""
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema
                }
                for tool in self.tools.values()
            ]
        }

    async def handle_list_resources(self) -> Dict[str, Any]:
        """등록된 리소스 목록 반환"""
        return {
            "resources": [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mime_type
                }
                for resource in self.resources.values()
            ]
        }

    async def handle_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """도구 호출 처리 (구현 필요)"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        # 실제 도구 실행 로직은 서브클래스에서 구현
        raise NotImplementedError(f"Tool {tool_name} not implemented")

    async def handle_read_resource(self, uri: str) -> Dict[str, Any]:
        """리소스 읽기 처리 (구현 필요)"""
        if uri not in self.resources:
            raise ValueError(f"Unknown resource: {uri}")

        # 실제 리소스 읽기 로직은 서브클래스에서 구현
        raise NotImplementedError(f"Resource {uri} not implemented")


class CHARDMCPServer(MCPServer):
    """
    CHARD 프로젝트용 MCP 서버

    RSS 피드 수집, Telegram 메시지 수집, 분석 결과 조회 등의 기능을 제공합니다.
    """

    def __init__(self):
        super().__init__("chard-mcp-server", "1.0.0")
        self._register_tools()
        self._register_resources()

    def _register_tools(self):
        """CHARD 도구 등록"""

        # 1. RSS 피드 수집 도구
        self.register_tool(Tool(
            name="collect_rss",
            description="RSS 피드에서 최근 기사를 수집합니다",
            input_schema={
                "type": "object",
                "properties": {
                    "feed_name": {
                        "type": "string",
                        "description": "수집할 RSS 피드 이름 (config.yml에 정의된 이름)"
                    },
                    "hours_back": {
                        "type": "integer",
                        "description": "수집할 시간 범위 (시간 단위)",
                        "default": 24
                    }
                },
                "required": ["feed_name"]
            }
        ))

        # 2. Telegram 메시지 수집 도구
        self.register_tool(Tool(
            name="collect_telegram",
            description="Telegram 채널에서 최근 메시지를 수집합니다",
            input_schema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "수집할 Telegram 채널 ID"
                    },
                    "max_messages": {
                        "type": "integer",
                        "description": "최대 수집 메시지 수",
                        "default": 100
                    }
                },
                "required": ["channel_id"]
            }
        ))

        # 3. 키워드 분석 도구
        self.register_tool(Tool(
            name="analyze_keywords",
            description="수집된 데이터에서 주요 키워드를 추출하고 분석합니다",
            input_schema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "분석할 날짜 (YYYY-MM-DD 형식)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "추출할 상위 키워드 개수",
                        "default": 10
                    }
                },
                "required": ["date"]
            }
        ))

        # 4. 내러티브 생성 도구
        self.register_tool(Tool(
            name="generate_narrative",
            description="분석 결과를 바탕으로 시장 내러티브를 생성합니다",
            input_schema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "내러티브를 생성할 날짜 (YYYY-MM-DD 형식)"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["macro", "crypto_native", "crypto_macro", "integrated"],
                        "description": "내러티브 카테고리"
                    }
                },
                "required": ["date"]
            }
        ))

    def _register_resources(self):
        """CHARD 리소스 등록"""

        # 1. 수집된 원본 데이터
        self.register_resource(Resource(
            uri="chard://collected-data/{date}",
            name="Collected Data",
            description="특정 날짜에 수집된 원본 RSS/Telegram 데이터",
            mime_type="application/json"
        ))

        # 2. 분석 결과
        self.register_resource(Resource(
            uri="chard://analysis/{date}",
            name="Analysis Results",
            description="특정 날짜의 키워드 분석 및 내러티브 결과",
            mime_type="application/json"
        ))

        # 3. 설정 파일
        self.register_resource(Resource(
            uri="chard://config",
            name="Configuration",
            description="CHARD 프로젝트 설정 (config.yml)",
            mime_type="application/yaml"
        ))

    async def handle_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """도구 호출 실행"""

        if tool_name == "collect_rss":
            return await self._collect_rss(
                feed_name=arguments["feed_name"],
                hours_back=arguments.get("hours_back", 24)
            )

        elif tool_name == "collect_telegram":
            return await self._collect_telegram(
                channel_id=arguments["channel_id"],
                max_messages=arguments.get("max_messages", 100)
            )

        elif tool_name == "analyze_keywords":
            return await self._analyze_keywords(
                date=arguments["date"],
                top_n=arguments.get("top_n", 10)
            )

        elif tool_name == "generate_narrative":
            return await self._generate_narrative(
                date=arguments["date"],
                category=arguments.get("category")
            )

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _collect_rss(self, feed_name: str, hours_back: int) -> Dict[str, Any]:
        """RSS 피드 수집 실행"""
        # 실제 구현: main.py의 collect_rss_data 함수 호출
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"RSS 피드 '{feed_name}'에서 최근 {hours_back}시간 동안의 기사를 수집했습니다."
                }
            ]
        }

    async def _collect_telegram(self, channel_id: str, max_messages: int) -> Dict[str, Any]:
        """Telegram 메시지 수집 실행"""
        # 실제 구현: main.py의 collect_telegram_data 함수 호출
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Telegram 채널 '{channel_id}'에서 최대 {max_messages}개의 메시지를 수집했습니다."
                }
            ]
        }

    async def _analyze_keywords(self, date: str, top_n: int) -> Dict[str, Any]:
        """키워드 분석 실행"""
        # 실제 구현: 분석 파이프라인 실행
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"{date}의 상위 {top_n}개 키워드를 분석했습니다."
                }
            ]
        }

    async def _generate_narrative(self, date: str, category: Optional[str]) -> Dict[str, Any]:
        """내러티브 생성 실행"""
        # 실제 구현: InsightNode 실행
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"{date}의 {category or '통합'} 내러티브를 생성했습니다."
                }
            ]
        }

    async def handle_read_resource(self, uri: str) -> Dict[str, Any]:
        """리소스 읽기 실행"""

        if uri.startswith("chard://collected-data/"):
            date = uri.split("/")[-1]
            return await self._read_collected_data(date)

        elif uri.startswith("chard://analysis/"):
            date = uri.split("/")[-1]
            return await self._read_analysis(date)

        elif uri == "chard://config":
            return await self._read_config()

        else:
            raise ValueError(f"Unknown resource: {uri}")

    async def _read_collected_data(self, date: str) -> Dict[str, Any]:
        """수집 데이터 읽기"""
        # 실제 구현: output/{date}/collected_*_raw.json 읽기
        return {
            "contents": [
                {
                    "uri": f"chard://collected-data/{date}",
                    "mimeType": "application/json",
                    "text": f'{{"date": "{date}", "data": []}}'
                }
            ]
        }

    async def _read_analysis(self, date: str) -> Dict[str, Any]:
        """분석 결과 읽기"""
        # 실제 구현: output/{date}/analysis_*.json 읽기
        return {
            "contents": [
                {
                    "uri": f"chard://analysis/{date}",
                    "mimeType": "application/json",
                    "text": f'{{"date": "{date}", "keywords": [], "narratives": {{}}}}'
                }
            ]
        }

    async def _read_config(self) -> Dict[str, Any]:
        """설정 파일 읽기"""
        # 실제 구현: config.yml 읽기
        return {
            "contents": [
                {
                    "uri": "chard://config",
                    "mimeType": "application/yaml",
                    "text": "# CHARD Configuration\n"
                }
            ]
        }


async def main():
    """MCP 서버 실행"""
    server = CHARDMCPServer()

    # 서버 시작 (실제로는 stdio나 HTTP로 통신)
    print(f"MCP Server started: {server.name} v{server.version}")
    print(f"Registered tools: {len(server.tools)}")
    print(f"Registered resources: {len(server.resources)}")

    # 도구 목록 출력
    tools = await server.handle_list_tools()
    print("\nAvailable tools:")
    for tool in tools["tools"]:
        print(f"  - {tool['name']}: {tool['description']}")

    # 리소스 목록 출력
    resources = await server.handle_list_resources()
    print("\nAvailable resources:")
    for resource in resources["resources"]:
        print(f"  - {resource['uri']}: {resource['description']}")


if __name__ == "__main__":
    asyncio.run(main())

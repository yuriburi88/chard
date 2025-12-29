"""
Claude Agent

Claude API를 사용하여 사용자의 자연어 요청을 처리하고,
CHARD 도구를 호출하여 시장 분석을 수행합니다.
"""

import asyncio
import logging
import os
from typing import Any

from anthropic import Anthropic, APIConnectionError, APIError, RateLimitError

from src.slack.config import get_config
from src.slack.tools import TOOLS, execute_tool


logger = logging.getLogger(__name__)

# 에러 메시지 정의
ERROR_MESSAGES = {
    "api_key": "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.",
    "rate_limit": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요. ⏳",
    "connection": "Claude API 연결 실패. 네트워크를 확인해 주세요. 🌐",
    "timeout": "분석 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요. ⏱️",
    "general": "죄송합니다, 오류가 발생했습니다. 😢 잠시 후 다시 시도해 주세요.",
    "tool_timeout": "도구 실행 시간 초과. 분석 범위를 줄여서 다시 시도해 주세요.",
}

# CHARD 시스템 프롬프트
SYSTEM_PROMPT = """You are CHARD, a cryptocurrency and macro-economic news assistant.
You help users analyze market news and provide trading insights in Korean.

Your capabilities (via tools):
- run_analysis: Run full analysis on recent news from all sources (RSS + Telegram)
- run_analysis_filtered: Run analysis with specific filters (source, keyword, period)
- get_latest_report: Get the most recent analysis report
- get_latest_keywords: Get trending keywords from the latest analysis

Guidelines:
- Always respond in Korean (한국어)
- Be friendly but professional
- When user asks for market analysis or news, use the appropriate tools
- Provide AI interpretation along with raw data
- If the request is ambiguous, ask clarifying questions
- Remember conversation context for follow-up questions
- Use emojis sparingly to enhance readability (📊 📈 📉 🔑 💡)
- When analysis is running, let the user know it may take 1-2 minutes
- After receiving tool results, summarize and interpret the data for the user

Common user expressions to recognize:
- "시황", "분석", "알려줘", "어때" → run_analysis or get_latest_report
- "비트코인", "이더리움", "BTC", "ETH" → keyword filter
- "RSS", "뉴스" → source: rss
- "텔레그램", "telegram" → source: telegram
- "오늘", "이번주", "12월" → period filter
- "키워드", "트렌드" → get_latest_keywords
"""


class ClaudeAgent:
    """Claude API를 사용하는 에이전트"""

    def __init__(self):
        """에이전트를 초기화합니다."""
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.client = Anthropic(api_key=self.api_key)
        self.config = get_config()

        logger.info(f"Claude Agent 초기화 완료 (model: {self.config.claude_model})")

    async def process_message(
        self,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        사용자 메시지를 처리하고 응답을 생성합니다.

        Args:
            user_message: 사용자 메시지
            conversation_history: 이전 대화 히스토리

        Returns:
            (응답 텍스트, 업데이트된 대화 히스토리)
        """
        if conversation_history is None:
            conversation_history = []

        # 사용자 메시지 추가
        conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        try:
            # Claude API 호출
            response = await self._call_claude(conversation_history)

            # Tool Use 처리 (최대 5회 반복)
            max_tool_iterations = 5
            tool_iteration = 0

            while (response.stop_reason == "tool_use"
                   and tool_iteration < max_tool_iterations):
                tool_iteration += 1
                logger.info(f"Tool Use 반복 {tool_iteration}/{max_tool_iterations}")

                # 도구 호출 결과 처리
                tool_results = await self._process_tool_calls(response)

                # assistant 응답 추가
                conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                # 도구 결과 추가
                conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

                # 다시 Claude 호출
                response = await self._call_claude(conversation_history)

            # 최대 반복 초과 시 경고
            if tool_iteration >= max_tool_iterations:
                logger.warning("Tool Use 최대 반복 횟수 초과")

            # 최종 응답 추출
            final_response = self._extract_text_response(response)

            # assistant 응답 추가
            conversation_history.append({
                "role": "assistant",
                "content": final_response,
            })

            return final_response, conversation_history

        except RateLimitError as e:
            logger.error(f"Rate limit 초과: {e}")
            return ERROR_MESSAGES["rate_limit"], conversation_history

        except APIConnectionError as e:
            logger.error(f"API 연결 실패: {e}")
            return ERROR_MESSAGES["connection"], conversation_history

        except asyncio.TimeoutError:
            logger.error("API 호출 타임아웃")
            return ERROR_MESSAGES["timeout"], conversation_history

        except APIError as e:
            logger.error(f"Claude API 에러: {e}")
            # APIError에는 status_code 대신 message 사용
            err_msg = f"{ERROR_MESSAGES['general']}\n\n오류: {str(e)[:100]}"
            return err_msg, conversation_history

        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}", exc_info=True)
            return ERROR_MESSAGES["general"], conversation_history

    async def _call_claude(
        self, messages: list[dict[str, Any]]
    ) -> Any:
        """Claude API를 호출합니다."""
        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            temperature=self.config.claude_temperature,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        return response

    async def _process_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """도구 호출을 처리하고 결과를 반환합니다."""
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_name = content_block.name
                tool_input = content_block.input
                tool_use_id = content_block.id

                logger.info(f"도구 호출: {tool_name}, 입력: {tool_input}")

                try:
                    # 도구 실행
                    result = await execute_tool(tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    })
                    logger.info(f"도구 실행 완료: {tool_name}")
                except Exception as e:
                    logger.error(f"도구 실행 실패: {tool_name}, 에러: {e}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"도구 실행 중 오류 발생: {str(e)}",
                        "is_error": True,
                    })

        return tool_results

    def _extract_text_response(self, response: Any) -> str:
        """응답에서 텍스트를 추출합니다."""
        text_parts = []
        for content_block in response.content:
            if hasattr(content_block, "text"):
                text_parts.append(content_block.text)
        return "\n".join(text_parts) if text_parts else "응답을 생성할 수 없습니다."


# 싱글톤 인스턴스
_agent_instance: ClaudeAgent | None = None


def get_agent() -> ClaudeAgent:
    """Claude Agent 싱글톤 인스턴스를 반환합니다."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ClaudeAgent()
    return _agent_instance

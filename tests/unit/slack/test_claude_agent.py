"""
Claude Agent 테스트

Claude API 연동 및 Tool Use 처리 테스트
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.slack.claude_agent import (
    ClaudeAgent,
    ERROR_MESSAGES,
    SYSTEM_PROMPT,
    get_agent,
)


class TestSystemPrompt:
    """시스템 프롬프트 테스트"""

    def test_system_prompt_contains_chard(self):
        """시스템 프롬프트에 CHARD가 포함되어 있는지 테스트"""
        assert "CHARD" in SYSTEM_PROMPT

    def test_system_prompt_korean_response(self):
        """시스템 프롬프트에 한국어 응답 지시가 있는지 테스트"""
        assert "Korean" in SYSTEM_PROMPT or "한국어" in SYSTEM_PROMPT

    def test_system_prompt_tools_mentioned(self):
        """시스템 프롬프트에 도구가 언급되어 있는지 테스트"""
        assert "run_analysis" in SYSTEM_PROMPT
        assert "get_latest_report" in SYSTEM_PROMPT


class TestErrorMessages:
    """에러 메시지 테스트"""

    def test_error_messages_defined(self):
        """필수 에러 메시지가 정의되어 있는지 테스트"""
        assert "api_key" in ERROR_MESSAGES
        assert "rate_limit" in ERROR_MESSAGES
        assert "connection" in ERROR_MESSAGES
        assert "timeout" in ERROR_MESSAGES
        assert "general" in ERROR_MESSAGES

    def test_error_messages_not_empty(self):
        """에러 메시지가 비어있지 않은지 테스트"""
        for key, message in ERROR_MESSAGES.items():
            assert len(message) > 0, f"{key} 에러 메시지가 비어있음"


class TestClaudeAgentInit:
    """ClaudeAgent 초기화 테스트"""

    def test_init_without_api_key(self):
        """API 키 없이 초기화 시 에러 테스트"""
        with patch.dict("os.environ", {}, clear=True):
            with patch("src.slack.claude_agent.get_config"):
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    ClaudeAgent()

    def test_init_with_api_key(self):
        """API 키가 있을 때 초기화 테스트"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("src.slack.claude_agent.get_config") as mock_config:
                config = MagicMock()
                config.claude_model = "claude-sonnet-4-20250514"
                mock_config.return_value = config

                with patch("src.slack.claude_agent.Anthropic"):
                    agent = ClaudeAgent()

                    assert agent.api_key == "test-key"
                    assert agent.config is not None


class TestClaudeAgentProcessMessage:
    """ClaudeAgent.process_message 테스트"""

    @pytest.fixture
    def mock_agent(self):
        """모의 ClaudeAgent fixture"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("src.slack.claude_agent.get_config") as mock_config:
                config = MagicMock()
                config.claude_model = "claude-sonnet-4-20250514"
                config.claude_max_tokens = 4096
                config.claude_temperature = 0.7
                mock_config.return_value = config

                with patch("src.slack.claude_agent.Anthropic") as mock_anthropic:
                    agent = ClaudeAgent()
                    agent.client = MagicMock()
                    yield agent

    @pytest.mark.asyncio
    async def test_process_message_simple(self, mock_agent):
        """단순 메시지 처리 테스트"""
        # 응답 모킹
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(text="안녕하세요!")]

        mock_agent.client.messages.create = MagicMock(return_value=mock_response)

        response, history = await mock_agent.process_message("안녕")

        assert response == "안녕하세요!"
        assert len(history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_process_message_with_history(self, mock_agent):
        """히스토리와 함께 메시지 처리 테스트"""
        existing_history = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(text="후속 답변")]

        mock_agent.client.messages.create = MagicMock(return_value=mock_response)

        response, history = await mock_agent.process_message(
            "후속 질문", existing_history
        )

        assert response == "후속 답변"
        assert len(history) == 4  # 2 기존 + 2 새로운

    @pytest.mark.asyncio
    async def test_process_message_tool_use(self, mock_agent):
        """Tool Use 처리 테스트"""
        # 첫 번째 응답: Tool Use
        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "get_latest_keywords"
        tool_use_block.input = {"limit": 5}
        tool_use_block.id = "tool_123"
        tool_use_response.content = [tool_use_block]

        # 두 번째 응답: 최종 텍스트
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MagicMock(text="키워드 분석 결과입니다.")]

        mock_agent.client.messages.create = MagicMock(
            side_effect=[tool_use_response, final_response]
        )

        with patch("src.slack.claude_agent.execute_tool") as mock_execute:
            mock_execute.return_value = "Bitcoin: 95점"

            response, history = await mock_agent.process_message("키워드 알려줘")

            assert "키워드 분석 결과" in response
            mock_execute.assert_called_once()


class TestClaudeAgentErrorHandling:
    """ClaudeAgent 에러 처리 테스트"""

    @pytest.fixture
    def mock_agent(self):
        """모의 ClaudeAgent fixture"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("src.slack.claude_agent.get_config") as mock_config:
                config = MagicMock()
                config.claude_model = "claude-sonnet-4-20250514"
                config.claude_max_tokens = 4096
                config.claude_temperature = 0.7
                mock_config.return_value = config

                with patch("src.slack.claude_agent.Anthropic"):
                    agent = ClaudeAgent()
                    agent.client = MagicMock()
                    yield agent

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_agent):
        """Rate Limit 에러 테스트"""
        from anthropic import RateLimitError

        mock_agent.client.messages.create = MagicMock(
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={}
            )
        )

        response, history = await mock_agent.process_message("테스트")

        assert ERROR_MESSAGES["rate_limit"] in response

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_agent):
        """연결 에러 테스트"""
        from anthropic import APIConnectionError

        mock_agent.client.messages.create = MagicMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        response, history = await mock_agent.process_message("테스트")

        assert ERROR_MESSAGES["connection"] in response

    @pytest.mark.asyncio
    async def test_general_error(self, mock_agent):
        """일반 에러 테스트"""
        mock_agent.client.messages.create = MagicMock(
            side_effect=Exception("Unknown error")
        )

        response, history = await mock_agent.process_message("테스트")

        assert "오류가 발생" in response


class TestClaudeAgentExtractText:
    """텍스트 추출 테스트"""

    @pytest.fixture
    def agent(self):
        """ClaudeAgent fixture"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("src.slack.claude_agent.get_config") as mock_config:
                config = MagicMock()
                config.claude_model = "claude-sonnet-4-20250514"
                mock_config.return_value = config

                with patch("src.slack.claude_agent.Anthropic"):
                    yield ClaudeAgent()

    def test_extract_single_text(self, agent):
        """단일 텍스트 블록 추출 테스트"""
        response = MagicMock()
        response.content = [MagicMock(text="단일 응답")]

        result = agent._extract_text_response(response)
        assert result == "단일 응답"

    def test_extract_multiple_text(self, agent):
        """다중 텍스트 블록 추출 테스트"""
        response = MagicMock()
        block1 = MagicMock(text="첫 번째")
        block2 = MagicMock(text="두 번째")
        response.content = [block1, block2]

        result = agent._extract_text_response(response)
        assert "첫 번째" in result
        assert "두 번째" in result

    def test_extract_empty_response(self, agent):
        """빈 응답 처리 테스트"""
        response = MagicMock()
        response.content = []

        result = agent._extract_text_response(response)
        assert "응답을 생성할 수 없습니다" in result


class TestGetAgent:
    """get_agent 싱글톤 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        import src.slack.claude_agent as agent_module

        agent_module._agent_instance = None

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("src.slack.claude_agent.get_config") as mock_config:
                config = MagicMock()
                config.claude_model = "claude-sonnet-4-20250514"
                mock_config.return_value = config

                with patch("src.slack.claude_agent.Anthropic"):
                    agent1 = get_agent()
                    agent2 = get_agent()

                    assert agent1 is agent2

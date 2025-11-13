"""
GeminiClient에 대한 단위 테스트.

Pro 전환을 고려한 설정 옵션화 및 재시도 로직을 검증합니다.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# GeminiClient를 직접 import (langchain 의존성 없이 테스트)
import importlib.util
from pathlib import Path

LLM_CLIENT_MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "workflows" / "llm_client.py"
LLM_CLIENT_SPEC = importlib.util.spec_from_file_location("llm_client_module", LLM_CLIENT_MODULE_PATH)
llm_client_module = importlib.util.module_from_spec(LLM_CLIENT_SPEC)
assert LLM_CLIENT_SPEC.loader is not None
LLM_CLIENT_SPEC.loader.exec_module(llm_client_module)  # type: ignore[call-arg]

GeminiClient = llm_client_module.GeminiClient
GEMINI_FLASH_MODELS = llm_client_module.GEMINI_FLASH_MODELS
GEMINI_PRO_MODELS = llm_client_module.GEMINI_PRO_MODELS
SUPPORTED_GEMINI_MODELS = llm_client_module.SUPPORTED_GEMINI_MODELS


class TestModelNameNormalization:
    """
    모델명 정규화 기능을 검증합니다.
    """

    @staticmethod
    def test_normalize_flash_alias() -> None:
        """
        "flash" 별칭이 올바르게 정규화되는지 확인합니다.
        """
        normalized = GeminiClient._normalize_model_name("flash")
        assert normalized == "gemini-2.0-flash-exp"

    @staticmethod
    def test_normalize_pro_alias() -> None:
        """
        "pro" 별칭이 올바르게 정규화되는지 확인합니다.
        """
        normalized = GeminiClient._normalize_model_name("pro")
        assert normalized == "gemini-2.0-pro-exp"

    @staticmethod
    def test_normalize_flash_without_exp() -> None:
        """
        "gemini-2.0-flash" 형태가 "gemini-2.0-flash-exp"로 정규화되는지 확인합니다.
        """
        normalized = GeminiClient._normalize_model_name("gemini-2.0-flash")
        assert normalized == "gemini-2.0-flash-exp"

    @staticmethod
    def test_normalize_pro_without_exp() -> None:
        """
        "gemini-2.0-pro" 형태가 "gemini-2.0-pro-exp"로 정규화되는지 확인합니다.
        """
        normalized = GeminiClient._normalize_model_name("gemini-2.0-pro")
        assert normalized == "gemini-2.0-pro-exp"

    @staticmethod
    def test_preserves_already_normalized() -> None:
        """
        이미 정규화된 모델명은 그대로 유지되는지 확인합니다.
        """
        for model in SUPPORTED_GEMINI_MODELS:
            normalized = GeminiClient._normalize_model_name(model)
            assert normalized == model

    @staticmethod
    def test_raises_error_for_invalid_model() -> None:
        """
        지원되지 않는 모델명에 대해 ValueError가 발생하는지 확인합니다.
        """
        with pytest.raises(ValueError, match="지원되지 않는 Gemini 모델명"):
            GeminiClient._normalize_model_name("invalid-model")


class TestModelTypeDetection:
    """
    모델 타입 감지 기능을 검증합니다.
    """

    @staticmethod
    def test_detects_flash_models() -> None:
        """
        Flash 모델이 올바르게 감지되는지 확인합니다.
        """
        for model in GEMINI_FLASH_MODELS:
            model_type = GeminiClient._detect_model_type(model)
            assert model_type == "flash"

    @staticmethod
    def test_detects_pro_models() -> None:
        """
        Pro 모델이 올바르게 감지되는지 확인합니다.
        """
        for model in GEMINI_PRO_MODELS:
            model_type = GeminiClient._detect_model_type(model)
            assert model_type == "pro"


class TestGeminiClientInitialization:
    """
    GeminiClient 초기화를 검증합니다.
    """

    @staticmethod
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    @patch("src.workflows.llm_client.ChatGoogleGenerativeAI")
    def test_initializes_with_default_model(mock_chat: MagicMock) -> None:
        """
        기본 모델로 초기화되는지 확인합니다.
        """
        client = GeminiClient()
        assert client.model == "gemini-2.0-flash-exp"
        assert client.model_type == "flash"
        mock_chat.assert_called_once()

    @staticmethod
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    @patch("src.workflows.llm_client.ChatGoogleGenerativeAI")
    def test_initializes_with_pro_model(mock_chat: MagicMock) -> None:
        """
        Pro 모델로 초기화되는지 확인합니다.
        """
        client = GeminiClient(model="pro")
        assert client.model == "gemini-2.0-pro-exp"
        assert client.model_type == "pro"
        mock_chat.assert_called_once()

    @staticmethod
    @patch.dict(os.environ, {}, clear=True)
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    def test_raises_error_when_api_key_missing() -> None:
        """
        API 키가 없을 때 ValueError가 발생하는지 확인합니다.
        """
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            GeminiClient()

    @staticmethod
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", False)
    def test_raises_error_when_langchain_unavailable() -> None:
        """
        langchain-google-genai가 없을 때 ImportError가 발생하는지 확인합니다.
        """
        with pytest.raises(ImportError, match="langchain-google-genai"):
            GeminiClient()


class TestGeminiClientAPI:
    """
    GeminiClient API 호출을 검증합니다.
    """

    @staticmethod
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    @patch("src.workflows.llm_client.ChatGoogleGenerativeAI")
    async def test_generate_content_async_success(mock_chat_class: MagicMock) -> None:
        """
        API 호출이 성공하는지 확인합니다.
        """
        mock_response = MagicMock()
        mock_response.content = '{"result": "success"}'
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_llm
        
        client = GeminiClient()
        result = await client.generate_content_async("test prompt")
        
        assert result == '{"result": "success"}'
        mock_llm.ainvoke.assert_called_once()

    @staticmethod
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    @patch("src.workflows.llm_client.ChatGoogleGenerativeAI")
    async def test_generate_content_async_with_json_format(mock_chat_class: MagicMock) -> None:
        """
        JSON 형식 요청이 올바르게 처리되는지 확인합니다.
        """
        mock_response = MagicMock()
        mock_response.content = '{"result": "success"}'
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_llm
        
        client = GeminiClient()
        result = await client.generate_content_async("test prompt", response_format="json")
        
        assert result == '{"result": "success"}'
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "JSON 형식" in call_args[0].content

    @staticmethod
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"})
    @patch("src.workflows.llm_client.LANGCHAIN_AVAILABLE", True)
    @patch("src.workflows.llm_client.ChatGoogleGenerativeAI")
    async def test_generate_content_async_raises_on_empty_response(mock_chat_class: MagicMock) -> None:
        """
        빈 응답에 대해 ValueError가 발생하는지 확인합니다.
        """
        mock_response = MagicMock()
        mock_response.content = ""
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_llm
        
        client = GeminiClient()
        
        with pytest.raises(ValueError, match="빈 응답"):
            await client.generate_content_async("test prompt")


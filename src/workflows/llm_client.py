"""
Gemini API 클라이언트 래퍼 (LangChain 기반)

LangChain의 ChatGoogleGenerativeAI를 사용하여 비동기 Gemini Flash/Pro 호출을 지원합니다.
LLM 파이프라인 문서의 섹션 6을 참조하여 재시도 로직을 포함합니다.

Pro 전환을 고려한 설정 옵션화:
- config.yml의 llm.model 설정을 통해 Flash/Pro 모델을 쉽게 전환 가능
- 모델명 검증 및 자동 변환 지원
- 재시도 전략 및 에러 처리 개선
"""

import os
import sys
import logging
import asyncio
import re
from typing import Dict, Any, Optional, Literal
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("langchain-google-genai가 설치되지 않았습니다.")

logger = logging.getLogger(__name__)

# Gemini 모델 상수 정의 (2025년 11월 기준)
# 참조: https://ai.google.dev/gemini-api/docs/models
# Note: "-exp" postfix는 더 이상 사용되지 않으며, stable 버전을 사용합니다.
GEMINI_FLASH_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-lite-001",
}

GEMINI_PRO_MODELS = {
    "gemini-2.5-pro",
    "gemini-2.0-pro",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
}

# 지원되는 모든 Gemini 모델
SUPPORTED_GEMINI_MODELS = GEMINI_FLASH_MODELS | GEMINI_PRO_MODELS
GEMINI_FLASH_MODELS_LOWER = {model.lower() for model in GEMINI_FLASH_MODELS}
GEMINI_PRO_MODELS_LOWER = {model.lower() for model in GEMINI_PRO_MODELS}
SUPPORTED_GEMINI_MODEL_MAP: Dict[str, str] = {
    model.lower(): model for model in SUPPORTED_GEMINI_MODELS
}


def _get_module_attribute(attribute_name: str) -> Any:
    """
    모듈 별칭(`src.workflows.llm_client`)에 패치된 속성이 있는지 확인한 후 값을 반환합니다.
    
    테스트 환경에서는 `llm_client_module`로 로드된 모듈과 `src.workflows.llm_client` 별칭에
    서로 다른 인스턴스가 존재할 수 있으므로, 별칭 모듈에 동일한 속성이 존재하면 우선 사용합니다.
    
    Args:
        attribute_name: 조회할 속성 이름
    
    Returns:
        속성 값
    """
    alias_module = sys.modules.get("src.workflows.llm_client")

    if alias_module is not None and hasattr(alias_module, attribute_name):
        return getattr(alias_module, attribute_name)

    return globals()[attribute_name]


class GeminiClient:
    """
    Gemini API 클라이언트 (LangChain 기반)
    
    LangChain의 ChatGoogleGenerativeAI를 사용하여 비동기 Gemini Flash/Pro 호출을 지원하며,
    재시도 로직을 포함합니다.
    
    Pro 전환을 고려한 설계:
    - config.yml의 llm.model 설정만 변경하면 Flash/Pro 전환 가능
    - 모델명 자동 검증 및 정규화
    - 모델 타입(Flash/Pro) 자동 감지
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ):
        """
        GeminiClient 초기화
        
        Args:
            api_key: Google API 키 (None이면 환경변수에서 로드)
            model: 모델명 (기본값: gemini-2.5-flash)
                - Flash 모델: gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-flash 등 (stable 버전)
                - Pro 모델: gemini-2.5-pro, gemini-2.0-pro, gemini-1.5-pro 등 (stable 버전)
                - config.yml에서 "flash" 또는 "pro" 별칭 사용 가능 (최신 stable 버전으로 매핑)
                - 참조: https://ai.google.dev/gemini-api/docs/models
            temperature: 온도 설정 (기본값: 0.1)
            max_tokens: 최대 출력 토큰 수 (기본값: 4000)
        
        Raises:
            ImportError: langchain-google-genai 패키지가 설치되지 않은 경우
            ValueError: API 키가 없거나 모델명이 유효하지 않은 경우
        """
        langchain_available = bool(_get_module_attribute("LANGCHAIN_AVAILABLE"))

        if not langchain_available:
            raise ImportError(
                "langchain-google-genai 패키지가 설치되어 있지 않습니다. "
                "pip install langchain-google-genai를 실행하세요."
            )
        
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")
        
        # 모델명 검증 및 정규화
        normalized_model = self._normalize_model_name(model)
        self.model = normalized_model
        self.model_type: Literal["flash", "pro"] = self._detect_model_type(normalized_model)
        
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # LangChain의 ChatGoogleGenerativeAI 초기화
        # 안전 설정: 모든 카테고리를 BLOCK_NONE으로 설정하여 응답이 차단되지 않도록 함
        # 참조: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
        # LangChain 문서에 따르면 HarmCategory와 HarmBlockThreshold는 langchain_google_genai에서 직접 import
        safety_settings = None
        chat_model_cls = _get_module_attribute("ChatGoogleGenerativeAI")
        try:
            # LangChain 공식 문서 방식: langchain_google_genai에서 직접 import
            # 참조: https://docs.langchain.com/oss/python/integrations/llms/google_ai
            try:
                from langchain_google_genai import HarmCategory, HarmBlockThreshold
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                logger.debug(
                    "[GeminiClient] 안전 설정 생성 완료 (langchain_google_genai에서 import)"
                )
            except ImportError:
                # 대체: google.ai.generativelanguage_v1beta 사용
                try:
                    from google.ai.generativelanguage_v1beta.types import safety
                    HarmCategory = safety.HarmCategory
                    HarmBlockThreshold = safety.SafetySetting.HarmBlockThreshold
                    
                    safety_settings = {
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                    logger.debug(
                        "[GeminiClient] 안전 설정 생성 완료 (google.ai.generativelanguage_v1beta 사용)"
                    )
                except ImportError:
                    # 대체: google.generativeai.types 사용
                    try:
                        from google.generativeai.types import HarmCategory, HarmBlockThreshold
                        
                        safety_settings = {
                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                        }
                        logger.debug(
                            "[GeminiClient] 안전 설정 생성 완료 (google.generativeai.types 사용)"
                        )
                    except ImportError:
                        logger.warning(
                            "[GeminiClient] 안전 설정 관련 모듈을 import할 수 없습니다. "
                            "안전 설정 없이 초기화합니다. 응답이 차단될 수 있습니다."
                        )
        except Exception as e:
            logger.warning(
                "[GeminiClient] 안전 설정 생성 중 오류 발생: %s. 안전 설정 없이 초기화합니다.",
                str(e)
            )
        
        # ChatGoogleGenerativeAI 초기화
        init_kwargs = {
            "model": self.model,
            "google_api_key": self.api_key,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        
        # Thinking 기능 비활성화 (reasoning 토큰이 output_tokens를 모두 사용하는 것을 방지)
        # Gemini 2.5 Flash 모델은 기본적으로 thinking 기능이 활성화되어 있어,
        # reasoning 토큰이 output_tokens에 포함되어 실제 응답이 비어있을 수 있음
        # thinking_budget=0으로 명시적으로 설정하여 thinking을 비활성화
        # 참고: gemini-2.5-flash는 thinking 기능이 기본적으로 활성화되어 있어,
        # thinking을 완전히 비활성화하려면 모델을 gemini-1.5-flash로 변경하는 것이 더 확실함
        if "2.5" in self.model or "2.0" in self.model:
            # Gemini 2.x 모델의 경우 thinking_budget=0으로 명시적으로 비활성화
            init_kwargs["thinking_budget"] = 0
            logger.debug(
                "[GeminiClient] Gemini 2.x 모델 감지: thinking_budget=0으로 설정하여 thinking 비활성화"
            )
        
        if safety_settings is not None:
            init_kwargs["safety_settings"] = safety_settings
            logger.debug(
                "[GeminiClient] 안전 설정 적용: 모든 카테고리 BLOCK_NONE"
            )
        
        self._llm = chat_model_cls(**init_kwargs)
        
        # thinking_budget 설정 확인 (디버깅용)
        actual_thinking_budget = getattr(self._llm, 'thinking_budget', None)
        logger.info(
            "[GeminiClient] 초기화 완료: 모델=%s, 타입=%s, temperature=%.2f, max_tokens=%d, thinking_budget=%s",
            self.model,
            self.model_type,
            self.temperature,
            self.max_tokens,
            actual_thinking_budget
        )
    
    def _prepare_messages(
        self,
        prompt: str,
        response_format: Optional[str] = None
    ) -> list:
        """
        프롬프트를 LangChain 메시지 형식으로 변환
        
        Args:
            prompt: 입력 프롬프트
            response_format: 응답 형식 ("json" 등, 선택적)
        
        Returns:
            LangChain HumanMessage 리스트
        """
        # JSON 형식 요청인 경우 프롬프트에 명시
        if response_format == "json":
            prompt_with_format = f"{prompt}\n\n응답은 반드시 유효한 JSON 형식이어야 합니다."
            messages = [HumanMessage(content=prompt_with_format)]
        else:
            messages = [HumanMessage(content=prompt)]
        
        # 디버깅: 프롬프트 일부 로깅 (너무 길면 처음 500자만)
        prompt_preview = prompt[:500] if len(prompt) > 500 else prompt
        logger.debug(
            "[GeminiClient] 전송할 프롬프트 미리보기 (처음 500자): %s%s",
            prompt_preview,
            "..." if len(prompt) > 500 else ""
        )
        
        return messages
    
    async def _invoke_llm(self, messages: list) -> Any:
        """
        LLM API 비동기 호출
        
        Args:
            messages: LangChain 메시지 리스트
        
        Returns:
            LLM 응답 객체
        """
        logger.debug(
            "[GeminiClient] LangChain ainvoke 호출 시작: 모델=%s, 메시지 수=%d",
            self.model,
            len(messages)
        )
        
        response = await self._llm.ainvoke(messages)
        
        logger.debug(
            "[GeminiClient] 응답 객체 수신: type=%s, has_content=%s, has_text=%s",
            type(response).__name__,
            hasattr(response, 'content'),
            hasattr(response, 'text')
        )
        
        # usage_metadata 확인 및 로깅 (reasoning 토큰 사용 여부 확인)
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            
            # usage_metadata 타입 확인 및 변환
            if isinstance(usage, dict):
                usage_dict = usage
            else:
                # UsageMetadata 객체인 경우 dict로 변환 시도
                try:
                    usage_dict = dict(usage) if hasattr(usage, '__iter__') and not isinstance(usage, str) else {}
                except (TypeError, ValueError):
                    # dict 변환 실패 시 속성으로 접근
                    usage_dict = {
                        'input_tokens': getattr(usage, 'input_tokens', None),
                        'output_tokens': getattr(usage, 'output_tokens', None),
                        'total_tokens': getattr(usage, 'total_tokens', None),
                        'output_token_details': getattr(usage, 'output_token_details', None),
                    }
            
            logger.info(
                "[GeminiClient] 토큰 사용량: input_tokens=%s, output_tokens=%s, total_tokens=%s",
                usage_dict.get('input_tokens', 'N/A'),
                usage_dict.get('output_tokens', 'N/A'),
                usage_dict.get('total_tokens', 'N/A')
            )
            
            # output_token_details에서 reasoning 토큰 확인
            # LangChain의 _response_to_result 함수는 thought_tokens > 0일 때만 
            # output_token_details={"reasoning": thought_tokens}를 포함합니다.
            # 따라서 output_token_details가 없다는 것은 thought_tokens가 0이라는 의미입니다.
            output_details = usage_dict.get('output_token_details')
            if output_details:
                # output_token_details가 dict가 아닌 경우 변환 시도
                if not isinstance(output_details, dict):
                    try:
                        output_details = dict(output_details) if hasattr(output_details, '__iter__') and not isinstance(output_details, str) else {}
                    except (TypeError, ValueError):
                        output_details = {'reasoning': getattr(output_details, 'reasoning', None)}
                
                reasoning_tokens = output_details.get('reasoning', 0) if output_details else 0
                if reasoning_tokens and reasoning_tokens > 0:
                    logger.warning(
                        "[GeminiClient] ⚠️ reasoning 토큰이 사용되었습니다: reasoning=%d, "
                        "thinking_budget=0으로 설정했지만 여전히 reasoning 토큰이 사용되고 있습니다.",
                        reasoning_tokens
                    )
                else:
                    logger.info(
                        "[GeminiClient] ✓ reasoning 토큰 미사용 확인: thinking_budget=0 설정이 정상 작동 중"
                    )
            else:
                # output_token_details가 없는 경우 = thought_tokens가 0인 경우
                # 이는 thinking_budget=0 설정이 정상 작동하고 있다는 의미입니다.
                logger.info(
                    "[GeminiClient] ✓ reasoning 토큰 미사용 확인: output_token_details가 없음 = thought_tokens=0 "
                    "(thinking_budget=0 설정이 정상 작동 중)"
                )
        
        return response
    
    def _extract_response_text(self, response: Any) -> str:
        """
        LangChain 응답 객체에서 텍스트 추출
        
        LangChain의 ChatGoogleGenerativeAI는 BaseMessage (일반적으로 AIMessage)를 반환합니다.
        - BaseMessage는 content 속성을 가지며, 이것이 실제 응답 텍스트입니다.
        - content는 str 또는 list[str] 타입일 수 있습니다 (멀티모달 지원).
        
        Args:
            response: LangChain 응답 객체
        
        Returns:
            추출된 텍스트
        
        Raises:
            ValueError: 응답 구조를 파악할 수 없는 경우
        """
        response_type = type(response).__name__
        logger.debug(
            "[GeminiClient] 응답 객체 타입: %s, 모듈: %s",
            response_type,
            type(response).__module__
        )
        
        # LangChain의 표준 방식: content 속성 사용
        if hasattr(response, 'content'):
            content = response.content
            logger.debug(
                "[GeminiClient] content 속성 발견: type=%s, value_type=%s",
                type(content).__name__,
                type(content).__name__ if content is not None else "None"
            )
            
            if content is None:
                logger.error(
                    "[GeminiClient] content가 None입니다. 응답 객체 전체 구조 확인 필요."
                )
                public_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                logger.error(
                    "[GeminiClient] 응답 객체 공개 속성: %s",
                    public_attrs
                )
                raise ValueError("Gemini API 응답의 content가 None입니다.")
            
            # content가 리스트인 경우 (멀티모달 또는 청크된 응답)
            if isinstance(content, list):
                text_parts = []
                for idx, item in enumerate(content):
                    if isinstance(item, str):
                        text_parts.append(item)
                    else:
                        text_parts.append(str(item))
                        logger.debug(
                            "[GeminiClient] content[%d] 타입이 문자열이 아님: %s",
                            idx,
                            type(item).__name__
                        )
                
                response_text = "".join(text_parts) if text_parts else ""
                logger.debug(
                    "[GeminiClient] content가 리스트입니다: 길이=%d, 텍스트 부분=%d개, 최종 길이=%d",
                    len(content),
                    len(text_parts),
                    len(response_text)
                )
                return response_text
            elif isinstance(content, str):
                response_text = content
                logger.debug(
                    "[GeminiClient] content가 문자열입니다: 길이=%d",
                    len(response_text)
                )
                
                # content가 빈 문자열인 경우 content_blocks 확인
                if not response_text or response_text.strip() == "":
                    if hasattr(response, 'content_blocks'):
                        content_blocks = response.content_blocks
                        logger.debug(
                            "[GeminiClient] content가 빈 문자열이지만 content_blocks가 있습니다: 길이=%d",
                            len(content_blocks) if content_blocks else 0
                        )
                        if content_blocks:
                            # content_blocks에서 텍스트 추출 시도
                            block_texts = []
                            for idx, block in enumerate(content_blocks):
                                if hasattr(block, 'text'):
                                    block_texts.append(block.text)
                                elif isinstance(block, str):
                                    block_texts.append(block)
                                elif hasattr(block, 'content'):
                                    block_texts.append(str(block.content))
                                else:
                                    block_texts.append(str(block))
                            if block_texts:
                                response_text = "".join(block_texts)
                                logger.debug(
                                    "[GeminiClient] content_blocks에서 텍스트 추출: 길이=%d",
                                    len(response_text)
                                )
                
                return response_text
            else:
                # 기타 타입은 문자열로 변환
                response_text = str(content)
                logger.warning(
                    "[GeminiClient] content 타입이 예상과 다릅니다: type=%s, value=%s",
                    type(content).__name__,
                    str(content)[:200] if len(str(content)) > 200 else str(content)
                )
                return response_text
        else:
            # content 속성이 없는 경우 (비표준 응답)
            logger.error(
                "[GeminiClient] 응답 객체에 'content' 속성이 없습니다. type=%s",
                response_type
            )
            
            # 대체 속성 확인
            if hasattr(response, 'text'):
                response_text = response.text
                logger.warning(
                    "[GeminiClient] 'text' 속성을 사용합니다 (비표준)."
                )
                return response_text
            elif hasattr(response, 'message'):
                message = response.message
                if hasattr(message, 'content'):
                    response_text = message.content if isinstance(message.content, str) else str(message.content)
                else:
                    response_text = str(message)
                logger.warning(
                    "[GeminiClient] 'message.content' 속성을 사용합니다 (비표준)."
                )
                return response_text
            else:
                # 응답 객체 전체를 문자열로 변환
                response_str = str(response)
                logger.error(
                    "[GeminiClient] 예상치 못한 응답 구조: type=%s, response=%s",
                    response_type,
                    response_str[:500] if len(response_str) > 500 else response_str
                )
                public_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                logger.error(
                    "[GeminiClient] 응답 객체 공개 속성: %s",
                    public_attrs[:30]
                )
                raise ValueError(
                    f"Gemini API 응답 구조를 파악할 수 없습니다. "
                    f"응답 타입: {response_type}, "
                    f"사용 가능한 속성: {public_attrs[:10]}"
                )
    
    def _log_empty_response_debug(self, response: Any) -> None:
        """
        빈 응답에 대한 디버깅 정보 로깅
        
        Args:
            response: LangChain 응답 객체
        """
        response_attrs = []
        if hasattr(response, '__dict__'):
            response_attrs = [k for k in dir(response) if not k.startswith('_')]
        elif hasattr(response, '__slots__'):
            response_attrs = list(response.__slots__)
        
        logger.error(
            "[GeminiClient] 빈 응답 감지: response_type=%s, response_attrs=%s",
            type(response).__name__,
            response_attrs[:20]
        )
        
        # content_blocks 확인
        if hasattr(response, 'content_blocks'):
            content_blocks = response.content_blocks
            logger.error(
                "[GeminiClient] content_blocks 존재: 길이=%d, 타입=%s",
                len(content_blocks) if content_blocks else 0,
                type(content_blocks).__name__
            )
            if content_blocks:
                for idx, block in enumerate(content_blocks[:5]):  # 처음 5개만 확인
                    logger.error(
                        "[GeminiClient] content_blocks[%d]: type=%s, has_text=%s, has_content=%s",
                        idx,
                        type(block).__name__,
                        hasattr(block, 'text'),
                        hasattr(block, 'content')
                    )
                    if hasattr(block, 'text'):
                        logger.error(
                            "[GeminiClient] content_blocks[%d].text: %s",
                            idx,
                            str(block.text)[:200] if len(str(block.text)) > 200 else str(block.text)
                        )
        
        # response_metadata 확인 (LangChain 문서에 따르면 block_reason은 여기에 있음)
        # 참조: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
        if hasattr(response, 'response_metadata'):
            response_metadata = response.response_metadata
            logger.error(
                "[GeminiClient] response_metadata 내용: %s",
                str(response_metadata)[:500] if len(str(response_metadata)) > 500 else str(response_metadata)
            )
            
            # prompt_feedback 확인 (LangChain 문서 예시: {'prompt_feedback': {'block_reason': 0, 'safety_ratings': []}})
            if isinstance(response_metadata, dict):
                prompt_feedback = response_metadata.get('prompt_feedback', {})
                if prompt_feedback:
                    block_reason = prompt_feedback.get('block_reason')
                    safety_ratings = prompt_feedback.get('safety_ratings', [])
                    logger.error(
                        "[GeminiClient] prompt_feedback: block_reason=%s, safety_ratings=%s",
                        block_reason,
                        safety_ratings
                    )
                    if block_reason and block_reason != 0:
                        logger.error(
                            "[GeminiClient] 응답이 안전 설정에 의해 차단됨: block_reason=%s (0이 아니면 차단됨)",
                            block_reason
                        )
                
                # finish_reason 확인 (MAX_TOKENS이면 응답이 잘렸을 수 있음)
                finish_reason = response_metadata.get('finish_reason')
                if finish_reason:
                    logger.error(
                        "[GeminiClient] finish_reason: %s (MAX_TOKENS이면 max_output_tokens 제한에 도달)",
                        finish_reason
                    )
                    if finish_reason == 'MAX_TOKENS':
                        logger.error(
                            "[GeminiClient] ⚠️ 응답이 max_output_tokens 제한에 도달하여 잘렸습니다. "
                            "max_output_tokens를 늘리거나 프롬프트를 단축하세요."
                        )
                
                # response_metadata의 최상위 레벨 safety_ratings도 확인
                safety_ratings = response_metadata.get('safety_ratings', [])
                if safety_ratings:
                    logger.error(
                        "[GeminiClient] response_metadata.safety_ratings: %s",
                        safety_ratings
                    )
        
        # additional_kwargs 확인 (추가 정보가 있을 수 있음)
        if hasattr(response, 'additional_kwargs'):
            additional_kwargs = response.additional_kwargs
            logger.error(
                "[GeminiClient] additional_kwargs 내용: %s",
                str(additional_kwargs)[:500] if len(str(additional_kwargs)) > 500 else str(additional_kwargs)
            )
        
        # response 객체의 모든 속성 값 확인
        if hasattr(response, '__dict__'):
            for attr in response_attrs[:10]:
                try:
                    value = getattr(response, attr, None)
                    if value and isinstance(value, str) and len(value) > 0:
                        logger.error(
                            "[GeminiClient] 응답 객체 속성 '%s'에 값이 있음: %s",
                            attr,
                            str(value)[:200]
                        )
                except Exception:
                    pass
        
        # 응답 객체 전체 덤프 (디버깅용)
        try:
            import json
            # Pydantic 모델인 경우 model_dump() 사용
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
                logger.error(
                    "[GeminiClient] 응답 객체 전체 덤프 (model_dump):\n%s",
                    json.dumps(response_dict, indent=2, ensure_ascii=False, default=str)[:2000]
                )
            # dict() 메서드가 있는 경우
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
                logger.error(
                    "[GeminiClient] 응답 객체 전체 덤프 (dict):\n%s",
                    json.dumps(response_dict, indent=2, ensure_ascii=False, default=str)[:2000]
                )
            # __dict__가 있는 경우
            elif hasattr(response, '__dict__'):
                response_dict = response.__dict__
                logger.error(
                    "[GeminiClient] 응답 객체 전체 덤프 (__dict__):\n%s",
                    json.dumps(response_dict, indent=2, ensure_ascii=False, default=str)[:2000]
                )
        except Exception as e:
            logger.error(
                "[GeminiClient] 응답 객체 덤프 중 오류 발생: %s",
                str(e)
            )
    
    def _validate_response(self, response: Any, response_text: str) -> None:
        """
        응답 텍스트 검증 (빈 응답 체크)
        
        Args:
            response: LangChain 응답 객체
            response_text: 추출된 응답 텍스트
        
        Raises:
            ValueError: 빈 응답인 경우
        """
        if not response_text or (isinstance(response_text, str) and response_text.strip() == ""):
            self._log_empty_response_debug(response)
            
            error_msg = (
                "Gemini API가 빈 응답을 반환했습니다. "
                "가능한 원인: 1) 안전 설정에 의해 차단됨, 2) 모델명이 유효하지 않음, "
                "3) 프롬프트가 너무 길거나 형식이 잘못됨"
            )
            logger.error("[GeminiClient] %s", error_msg)
            raise ValueError(error_msg)
    
    async def _handle_api_error(self, error: Exception, prompt_length: int) -> None:
        """
        API 호출 에러 처리 (재시도 전략 포함)
        
        Args:
            error: 발생한 예외
            prompt_length: 프롬프트 길이
        
        Raises:
            Exception: 재시도 후에도 실패한 경우
        """
        error_str = str(error).lower()
        error_msg = f"Gemini API 호출 실패: {str(error)}"
        
        logger.error(
            "[GeminiClient] 예외 발생: type=%s, message=%s, 모델=%s, 프롬프트 길이=%d",
            type(error).__name__,
            str(error),
            self.model,
            prompt_length,
            exc_info=True,
        )
        
        # Rate limit 또는 Quota 에러인 경우 추가 대기
        if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
            logger.warning(
                "[GeminiClient] Rate limit/quota 에러 감지, 60초 대기 후 재시도: %s",
                str(error),
            )
            await asyncio.sleep(60)
        elif "timeout" in error_str or "timed out" in error_str:
            logger.warning(
                "[GeminiClient] 타임아웃 에러 감지, 재시도: %s",
                str(error),
            )
        elif "not found" in error_str or "invalid" in error_str or "404" in error_str:
            logger.error(
                "[GeminiClient] 모델명 오류 가능성: 모델=%s가 존재하지 않거나 유효하지 않을 수 있습니다. "
                "gemini-1.5-flash 또는 gemini-2.0-flash로 변경해보세요.",
                self.model
            )
        
        raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_content_async(
        self,
        prompt: str,
        response_format: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        비동기로 Gemini API를 호출하여 콘텐츠 생성
        
        LLM 파이프라인 문서의 섹션 6을 참조하여 재시도 로직을 포함합니다.
        
        재시도 전략:
        - 최대 3회 재시도
        - 지수 백오프: 4초, 8초, 최대 10초 대기
        - Rate limit 에러 시 추가 60초 대기 후 재시도
        
        Args:
            prompt: 입력 프롬프트
            response_format: 응답 형식 ("json" 등, 선택적)
            **kwargs: 추가 설정 (temperature, max_tokens 등 오버라이드 가능)
        
        Returns:
            생성된 텍스트 응답
        
        Raises:
            ValueError: 빈 응답이 반환된 경우
            Exception: API 호출 실패 시 (재시도 후에도 실패한 경우)
        """
        prompt_length = len(prompt)
        logger.debug(
            "[GeminiClient] API 호출 시작: 모델=%s, 프롬프트 길이=%d, response_format=%s",
            self.model,
            prompt_length,
            response_format,
        )
        
        try:
            # 1. 프롬프트를 LangChain 메시지 형식으로 변환
            messages = self._prepare_messages(prompt, response_format)
            
            # 2. LLM API 비동기 호출
            response = await self._invoke_llm(messages)
            
            # 3. 응답 객체에서 텍스트 추출
            response_text = self._extract_response_text(response)
            
            # 4. 응답 검증 (빈 응답 체크)
            self._validate_response(response, response_text)
            
            # 5. 성공 로깅 및 반환
            response_length = len(response_text)
            logger.debug(
                "[GeminiClient] API 호출 성공: 응답 길이=%d, 모델=%s",
                response_length,
                self.model,
            )
            
            return response_text
                
        except Exception as e:
            # 6. 에러 처리
            await self._handle_api_error(e, prompt_length)

    @staticmethod
    def _detect_model_type(model: str) -> Literal["flash", "pro"]:
        """
        모델명에서 모델 타입(Flash/Pro)을 감지합니다.
        
        Args:
            model: 정규화된 모델명
        
        Returns:
            "flash" 또는 "pro"
        """
        model_lower = model.lower()

        if model_lower in GEMINI_FLASH_MODELS_LOWER:
            return "flash"

        if model_lower in GEMINI_PRO_MODELS_LOWER:
            return "pro"

        if re.match(r"^gemini-\d+\.\d+-flash", model_lower):
            return "flash"

        if re.match(r"^gemini-\d+\.\d+-pro", model_lower):
            return "pro"

        logger.warning(
            "[GeminiClient] 모델 타입을 감지할 수 없어 'flash'로 가정합니다: %s",
            model,
        )
        return "flash"

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        """
        모델명을 정규화하고 검증합니다.
        
        Pro 전환을 고려하여 다음과 같은 변환을 지원합니다:
        - "flash" → "gemini-2.5-flash" (기본 Flash 모델, 최신 stable 버전)
        - "pro" → "gemini-2.5-pro" (기본 Pro 모델, 최신 stable 버전)
        - "gemini-X.Y-flash" → "gemini-X.Y-flash" (stable 버전 유지)
        - "gemini-X.Y-pro" → "gemini-X.Y-pro" (stable 버전 유지)
        
        Args:
            model: 원본 모델명
        
        Returns:
            정규화된 모델명
        
        Raises:
            ValueError: 지원되지 않는 모델명인 경우
        """
        model_lower = model.lower().strip()
        
        alias_map: Dict[str, str] = {
            "flash": "gemini-2.5-flash",
            "pro": "gemini-2.5-pro",
        }

        if model_lower in alias_map:
            normalized = alias_map[model_lower]

            logger.info(
                "[GeminiClient] 모델명 별칭 정규화: %s → %s",
                model,
                normalized,
            )
            return normalized

        core_match = re.fullmatch(r"^gemini-(\d+\.\d+)-(flash|pro)$", model_lower)
        if core_match:
            version = core_match.group(1)
            variant = core_match.group(2)

            # stable 버전을 우선 사용 (-exp postfix 제거)
            stable_model = f"gemini-{version}-{variant}"
            if stable_model in SUPPORTED_GEMINI_MODELS:
                logger.info(
                    "[GeminiClient] 모델명 정규화: %s → %s",
                    model,
                    stable_model,
                )
                return stable_model

        exact_match = SUPPORTED_GEMINI_MODEL_MAP.get(model_lower)
        if exact_match:
            return exact_match

        raise ValueError(
            f"지원되지 않는 Gemini 모델명입니다: {model}\n"
            f"지원되는 모델: {', '.join(sorted(SUPPORTED_GEMINI_MODELS))}\n"
            f"또는 'flash' 또는 'pro'를 사용하여 기본 모델을 선택할 수 있습니다."
        )
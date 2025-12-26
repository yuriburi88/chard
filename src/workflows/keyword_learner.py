"""
LLM 기반 키워드 학습 시스템

- 자주 등장하는 키워드를 LLM으로 분석
- Macro / Crypto Native / Crypto-Macro 카테고리로 자동 분류
- 분류 결과를 DynamicKeywordManager로 전달
"""

import asyncio
import json
import logging

from src.workflows.llm_client import GeminiClient


logger = logging.getLogger(__name__)


class KeywordLearner:
    """
    LLM을 사용하여 키워드를 자동으로 카테고리별로 분류합니다.
    """

    def __init__(self, llm_client: GeminiClient):
        """
        Args:
            llm_client: GeminiClient 인스턴스
        """
        self.llm_client = llm_client

    def learn_keywords(
        self,
        top_keywords: list[dict],
        top_n: int = 30,
        min_frequency: int = 2,
    ) -> dict[str, list[str]]:
        """
        상위 N개 키워드를 LLM으로 분석하여 카테고리별로 분류합니다.

        Args:
            top_keywords: KeywordExtractor에서 추출한 상위 키워드 리스트
                          [{"term": "BTC", "score": 95, ...}, ...]
            top_n: 상위 몇 개 키워드를 학습할지 (기본 30개)
            min_frequency: 최소 출현 빈도 (이보다 낮으면 제외)

        Returns:
            {
                "macro": ["금리 인하", "연준", ...],
                "crypto_native": ["BTC", "ETH", ...],
                "crypto_macro": ["업비트 해킹", "규제", ...]
            }
        """
        # 상위 N개 + 최소 빈도 필터링
        filtered_keywords = [
            kw
            for kw in top_keywords[:top_n]
            if len(kw.get("sources", [])) >= min_frequency
        ]

        if not filtered_keywords:
            logger.warning("학습할 키워드가 없습니다. (필터링 후 0개)")
            return {"macro": [], "crypto_native": [], "crypto_macro": []}

        # LLM에 전달할 키워드 리스트 생성
        keyword_terms = [
            kw.get("term", "") for kw in filtered_keywords if kw.get("term")
        ]

        if not keyword_terms:
            logger.warning("학습할 키워드가 없습니다. (term이 없음)")
            return {"macro": [], "crypto_native": [], "crypto_macro": []}

        logger.info(f"키워드 학습 시작: {len(keyword_terms)}개 키워드")

        # LLM으로 분류
        try:
            categorized = self._categorize_with_llm(keyword_terms)
            logger.info(
                f"키워드 학습 완료: Macro={len(categorized.get('macro', []))}, "
                f"Crypto Native={len(categorized.get('crypto_native', []))}, "
                f"Crypto-Macro={len(categorized.get('crypto_macro', []))}"
            )
            return categorized
        except Exception as e:
            logger.error(f"키워드 학습 실패: {e}", exc_info=True)
            return {"macro": [], "crypto_native": [], "crypto_macro": []}

    def _categorize_with_llm(self, keywords: list[str]) -> dict[str, list[str]]:
        """
        LLM을 사용하여 키워드를 카테고리별로 분류합니다.

        Args:
            keywords: 분류할 키워드 리스트

        Returns:
            {"macro": [...], "crypto_native": [...], "crypto_macro": [...]}
        """
        prompt = self._build_categorization_prompt(keywords)

        # LLM 비동기 호출을 동기로 래핑 (이벤트 루프가 이미 실행 중인 경우 고려)
        try:
            # 이미 실행 중인 이벤트 루프 체크
            try:
                asyncio.get_running_loop()
                # 이미 실행 중이면 새로운 스레드에서 실행
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(
                            self.llm_client.generate_content_async(prompt)
                        )
                    )
                    response = future.result()
            except RuntimeError:
                # 실행 중인 루프가 없으면 새로 생성하여 실행
                response = asyncio.run(self.llm_client.generate_content_async(prompt))

        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}", exc_info=True)
            raise

        # 응답 파싱
        categorized = self._parse_categorization_response(response)

        return categorized

    def _build_categorization_prompt(self, keywords: list[str]) -> str:
        """
        키워드 분류를 위한 LLM 프롬프트를 생성합니다.

        Args:
            keywords: 분류할 키워드 리스트

        Returns:
            LLM 프롬프트 문자열
        """
        keywords_str = ", ".join(keywords)

        prompt = f"""
다음 키워드들을 디지털 자산 시장의 세 가지 카테고리로 분류해주세요:

**키워드 리스트**:
{keywords_str}

**카테고리 정의**:

1. **Macro (거시경제)**:
   - 거시경제, 중앙은행 통화정책, 금리, 인플레이션, GDP 성장률, 실업률
   - 외환 시장, 국채 수익률, 전통 금융 시장 지표
   - 예시: "금리 인하", "연준", "인플레이션", "GDP", "외환 시장"

2. **Crypto Native (암호화폐 고유 이슈)**:
   - 특정 암호화폐 프로젝트(비트코인, 이더리움, 솔라나 등)
   - 블록체인 기술, 스마트 컨트랙트, DeFi, NFT, Web3
   - 암호화폐 생태계 내부 트렌드 (AI, RWA, Meme 등)
   - 예시: "BTC", "ETH", "솔라나", "AI", "DeFi", "NFT"

3. **Crypto-Macro (암호화폐-거시경제 교차 이슈)**:
   - 암호화폐 관련 규제, 정책, 법률
   - 거래소 해킹, 보안 사고
   - 기관 투자, ETF, 전통 금융의 암호화폐 진입
   - 스테이블코인, CBDC
   - 예시: "규제", "업비트 해킹", "ETF", "스테이블코인", "기관 투자"

**분류 규칙**:
- 각 키워드는 하나 이상의 카테고리에 속할 수 있습니다 (중복 가능)
- 애매한 경우, 가장 관련성이 높은 카테고리를 선택하세요
- 암호화폐와 거시경제가 모두 관련된 경우 "crypto_macro"로 분류하세요

**출력 형식** (JSON):
{{
  "macro": ["키워드1", "키워드2", ...],
  "crypto_native": ["키워드3", "키워드4", ...],
  "crypto_macro": ["키워드5", "키워드6", ...]
}}

**중요**: 반드시 JSON 형식으로만 응답하세요. 다른 설명은 포함하지 마세요.
"""
        return prompt

    def _parse_categorization_response(self, response: str) -> dict[str, list[str]]:
        """
        LLM 응답을 파싱하여 카테고리별 키워드 딕셔너리로 변환합니다.

        Args:
            response: LLM의 JSON 응답

        Returns:
            {"macro": [...], "crypto_native": [...], "crypto_macro": [...]}
        """
        try:
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            response_cleaned = response.strip()

            # 코드 블록 제거
            if response_cleaned.startswith("```json"):
                response_cleaned = response_cleaned[7:]  # "```json" 제거
            elif response_cleaned.startswith("```"):
                response_cleaned = response_cleaned[3:]  # "```" 제거

            if response_cleaned.endswith("```"):
                response_cleaned = response_cleaned[:-3]

            response_cleaned = response_cleaned.strip()

            # JSON 파싱
            categorized = json.loads(response_cleaned)

            # 기본 구조 검증
            result = {
                "macro": categorized.get("macro", []),
                "crypto_native": categorized.get("crypto_native", []),
                "crypto_macro": categorized.get("crypto_macro", []),
            }

            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM 응답 JSON 파싱 실패: {e}")
            logger.error(f"응답 내용: {response[:500]}")
            return {"macro": [], "crypto_native": [], "crypto_macro": []}
        except Exception as e:
            logger.error(f"LLM 응답 파싱 중 오류: {e}", exc_info=True)
            return {"macro": [], "crypto_native": [], "crypto_macro": []}

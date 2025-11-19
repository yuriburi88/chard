"""
전처리 파이프라인 모듈

수집된 데이터를 분석에 적합한 형태로 전처리합니다.
- 언어 감지: 텍스트의 언어를 자동 감지하여 필터링
- 불용어/스팸 처리: 노이즈 제거 및 품질 향상
- 토큰 길이 제한: LLM 입력 제한에 맞게 텍스트 길이 조정
"""

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logging.warning("langdetect가 설치되지 않았습니다. 언어 감지 기능이 비활성화됩니다.")

import tiktoken
from src.collectors.models import Article, TelegramMessage, CollectedItem, MetadataValue

logger = logging.getLogger(__name__)

# langdetect 재현성 보장을 위한 시드 설정
if LANGDETECT_AVAILABLE:
    DetectorFactory.seed = 0


@dataclass
class PreprocessingConfig:
    """전처리 설정"""
    # 언어 감지 설정
    language_detection_enabled: bool = True
    allowed_languages: List[str] = field(default_factory=lambda: ["ko", "en"])  # 허용 언어 코드
    min_text_length_for_detection: int = 10  # 언어 감지를 위한 최소 텍스트 길이
    
    # 불용어/스팸 처리 설정
    spam_filter_enabled: bool = True
    min_content_length: int = 10  # 최소 본문 길이 (문자 수)
    max_content_length: int = 100000  # 최대 본문 길이 (문자 수)
    
    # 스팸 키워드 패턴 (불용어)
    spam_keywords: List[str] = field(default_factory=lambda: [
        '광고', 'advertisement', 'promotion', 'spam',
        '홍보', '이벤트', 'event', 'giveaway',
        '무료', 'free', 'click here', '지금 가입',
        '특가', '할인', 'discount', 'sale'
    ])
    
    # 토큰 길이 제한 설정
    token_limit_enabled: bool = True
    max_tokens_per_item: int = 50000  # 항목당 최대 토큰 수
    token_encoding: str = "cl100k_base"  # tiktoken 인코딩 (GPT-4/Gemini 호환)
    
    # 장문 메시지 분할 설정
    split_long_messages: bool = True  # 장문 메시지 분할 기능 토글
    max_tokens_per_segment: int = 4000  # 분할된 세그먼트당 최대 토큰 수
    segment_overlap_tokens: int = 200  # 세그먼트 간 토큰 오버랩 크기
    
    # 텍스트 정규화 설정
    normalize_whitespace: bool = True  # 연속된 공백 정규화
    remove_urls: bool = False  # URL 제거 여부 (기본값: 유지)
    remove_mentions: bool = False  # @멘션 제거 여부 (기본값: 유지)


class Preprocessor:
    """
    전처리 파이프라인 클래스
    
    수집된 데이터를 분석에 적합한 형태로 전처리합니다.
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """
        Preprocessor 초기화
        
        Args:
            config: 전처리 설정 (None이면 기본값 사용)
        """
        self.config = config or PreprocessingConfig()
        
        # tiktoken 인코더 초기화
        try:
            self.token_encoder = tiktoken.get_encoding(self.config.token_encoding)
            logger.info(f"[Preprocessor] 토큰 인코더 초기화 완료: {self.config.token_encoding}")
        except Exception as e:
            logger.error(f"[Preprocessor] 토큰 인코더 초기화 실패: {e}")
            self.token_encoder = None
        
        # 언어 감지 사용 가능 여부 확인
        if self.config.language_detection_enabled and not LANGDETECT_AVAILABLE:
            logger.warning("[Preprocessor] langdetect가 설치되지 않아 언어 감지가 비활성화됩니다.")
            self.config.language_detection_enabled = False

        # 장문 메시지 분할 설정 로깅
        self._log_segmentation_config()

        # 장문 메시지 분할 설정 검증
        self._validate_segmentation_config()
    
    async def preprocess_articles(
        self,
        articles: List[Article]
    ) -> List[Article]:
        """
        Article 리스트를 전처리합니다.
        
        Args:
            articles: 전처리할 Article 리스트
            
        Returns:
            전처리된 Article 리스트
        """
        logger.info(f"[Preprocessor] Article 전처리 시작: {len(articles)}개")
        
        processed_articles: List[Article] = []
        stats = {
            "total": len(articles),
            "language_filtered": 0,
            "spam_filtered": 0,
            "token_filtered": 0,
            "length_filtered": 0,
            "passed": 0
        }
        
        for article in articles:
            try:
                # 1. 기본 검증 (빈 텍스트 체크)
                if not article.content or not article.content.strip():
                    logger.debug(f"[Preprocessor] 빈 본문 제외: source={article.source}, title={article.title[:50]}")
                    stats["length_filtered"] += 1
                    continue
                
                # 2. 텍스트 정규화
                normalized_content = self._normalize_text(article.content)
                normalized_title = self._normalize_text(article.title)
                
                if not normalized_content or len(normalized_content.strip()) < self.config.min_content_length:
                    logger.debug(f"[Preprocessor] 너무 짧은 본문 제외: source={article.source}, 길이={len(normalized_content)}")
                    stats["length_filtered"] += 1
                    continue
                
                if len(normalized_content) > self.config.max_content_length:
                    logger.debug(f"[Preprocessor] 너무 긴 본문 제외: source={article.source}, 길이={len(normalized_content)}")
                    stats["length_filtered"] += 1
                    continue
                
                # 3. 언어 감지
                if self.config.language_detection_enabled:
                    detected_lang = await self._detect_language(normalized_content)
                    if detected_lang and detected_lang not in self.config.allowed_languages:
                        logger.debug(f"[Preprocessor] 허용되지 않은 언어 제외: source={article.source}, 언어={detected_lang}")
                        stats["language_filtered"] += 1
                        continue
                
                # 4. 스팸/불용어 필터링
                if self.config.spam_filter_enabled:
                    if self._is_spam(normalized_content) or self._is_spam(normalized_title):
                        logger.debug(f"[Preprocessor] 스팸으로 판단된 항목 제외: source={article.source}, title={article.title[:50]}")
                        stats["spam_filtered"] += 1
                        continue
                
                # 5. 토큰 길이 제한
                if self.config.token_limit_enabled and self.token_encoder:
                    token_count = len(self.token_encoder.encode(normalized_content))
                    if token_count > self.config.max_tokens_per_item:
                        logger.debug(f"[Preprocessor] 토큰 제한 초과 제외: source={article.source}, 토큰={token_count}")
                        stats["token_filtered"] += 1
                        continue
                
                # 6. 전처리된 Article 생성
                processed_article = Article(
                    title=normalized_title,
                    url=article.url,
                    content=normalized_content,
                    source=article.source,
                    published_at=article.published_at,
                    source_type=article.source_type,
                    description=self._normalize_text(article.description) if article.description else None,
                    author=article.author,
                    tags=article.tags,
                    telegram_message_ids=article.telegram_message_ids,
                    telegram_message_count=article.telegram_message_count
                )
                
                processed_articles.append(processed_article)
                stats["passed"] += 1
                
            except Exception as e:
                logger.error(f"[Preprocessor] Article 전처리 중 오류 발생: source={article.source}, error={e}")
                continue
        
        # 통계 로깅
        logger.info(
            f"[Preprocessor] Article 전처리 완료: "
            f"전체={stats['total']}, 통과={stats['passed']}, "
            f"언어필터={stats['language_filtered']}, 스팸필터={stats['spam_filtered']}, "
            f"토큰필터={stats['token_filtered']}, 길이필터={stats['length_filtered']}"
        )
        
        return processed_articles
    
    async def preprocess_collected_items(
        self,
        items: List[CollectedItem]
    ) -> List[CollectedItem]:
        """
        CollectedItem 리스트를 전처리합니다.
        
        Args:
            items: 전처리할 CollectedItem 리스트
            
        Returns:
            전처리된 CollectedItem 리스트
        """
        logger.info(f"[Preprocessor] CollectedItem 전처리 시작: {len(items)}개")
        
        processed_items: List[CollectedItem] = []
        stats = {
            "total": len(items),
            "language_filtered": 0,
            "spam_filtered": 0,
            "token_filtered": 0,
            "length_filtered": 0,
            "split_replaced": 0,
            "split_segments": 0,
            "passed": 0
        }
        
        for item in items:
            try:
                # 1. 기본 검증
                if not item.text or not item.text.strip():
                    logger.debug(f"[Preprocessor] 빈 텍스트 제외: source={item.source_name}")
                    stats["length_filtered"] += 1
                    continue
                
                # 2. 텍스트 정규화
                normalized_text = self._normalize_text(item.text)
                
                if not normalized_text or len(normalized_text.strip()) < self.config.min_content_length:
                    logger.debug(f"[Preprocessor] 너무 짧은 텍스트 제외: source={item.source_name}, 길이={len(normalized_text)}")
                    stats["length_filtered"] += 1
                    continue
                
                if len(normalized_text) > self.config.max_content_length:
                    logger.debug(f"[Preprocessor] 너무 긴 텍스트 제외: source={item.source_name}, 길이={len(normalized_text)}")
                    stats["length_filtered"] += 1
                    continue
                
                # 3. 언어 감지
                if self.config.language_detection_enabled:
                    detected_lang = await self._detect_language(normalized_text)
                    if detected_lang and detected_lang not in self.config.allowed_languages:
                        logger.debug(f"[Preprocessor] 허용되지 않은 언어 제외: source={item.source_name}, 언어={detected_lang}")
                        stats["language_filtered"] += 1
                        continue
                
                # 4. 스팸/불용어 필터링
                if self.config.spam_filter_enabled:
                    if self._is_spam(normalized_text):
                        logger.debug(f"[Preprocessor] 스팸으로 판단된 항목 제외: source={item.source_name}")
                        stats["spam_filtered"] += 1
                        continue
                
                # 5. 토큰 길이 제한
                if self.config.token_limit_enabled and self.token_encoder:
                    token_count = len(self.token_encoder.encode(normalized_text))
                    if token_count > self.config.max_tokens_per_item:
                        if self.config.split_long_messages:
                            split_items = self._split_collected_item(
                                original_item=item,
                                normalized_text=normalized_text,
                                token_count=token_count
                            )

                            if not split_items:
                                logger.warning(
                                    "[Preprocessor] 토큰 제한 초과 항목 분할 실패: "
                                    f"source={item.source_name}, token_count={token_count}"
                                )
                                stats["token_filtered"] += 1
                                continue

                            processed_items.extend(split_items)
                            stats["split_replaced"] += 1
                            stats["split_segments"] += len(split_items)

                            logger.info(
                                "[Preprocessor] 토큰 제한 초과 항목 분할 완료: "
                                f"source={item.source_name}, "
                                f"segment_count={len(split_items)}, "
                                f"original_token_count={token_count}"
                            )
                            stats["passed"] += len(split_items)
                            continue

                        logger.debug(
                            f"[Preprocessor] 토큰 제한 초과 제외: source={item.source_name}, 토큰={token_count}"
                        )
                        stats["token_filtered"] += 1
                        continue
                
                # 6. 전처리된 CollectedItem 생성
                processed_item = CollectedItem(
                    source_type=item.source_type,
                    source_name=item.source_name,
                    timestamp=item.timestamp,
                    text=normalized_text,
                    metadata=item.metadata
                )
                
                processed_items.append(processed_item)
                stats["passed"] += 1
                
            except Exception as e:
                logger.error(f"[Preprocessor] CollectedItem 전처리 중 오류 발생: source={item.source_name}, error={e}")
                continue
        
        # 통계 로깅
        logger.info(
            f"[Preprocessor] CollectedItem 전처리 완료: "
            f"전체={stats['total']}, 통과={stats['passed']}, "
            f"언어필터={stats['language_filtered']}, 스팸필터={stats['spam_filtered']}, "
            f"토큰필터={stats['token_filtered']}, 길이필터={stats['length_filtered']}, "
            f"분할대체={stats['split_replaced']}, 분할세그먼트={stats['split_segments']}"
        )
        
        return processed_items
    
    def _split_collected_item(
        self,
        original_item: CollectedItem,
        normalized_text: str,
        token_count: int
    ) -> List[CollectedItem]:
        """
        토큰 제한을 초과한 CollectedItem을 세그먼트로 분할합니다.
        
        Args:
            original_item: 분할 대상 CollectedItem
            normalized_text: 전처리된 텍스트
            token_count: 원본 텍스트의 토큰 수
        
        Returns:
            분할된 CollectedItem 리스트
        """
        try:
            segments = self._split_text_to_segments(
                text=normalized_text,
                max_tokens=self.config.max_tokens_per_segment
            )
            boundaries = (
                self._segment_boundaries
                if hasattr(self, "_segment_boundaries")
                else []
            )
        except Exception as error:
            logger.error(
                "[Preprocessor] CollectedItem 분할 중 오류 발생: "
                f"source={original_item.source_name}, error={error}"
            )
            return []

        if not segments:
            logger.warning(
                "[Preprocessor] CollectedItem 분할 결과가 비어 있습니다: "
                f"source={original_item.source_name}, token_count={token_count}"
            )
            return []

        original_id = self._extract_original_identifier(original_item)
        total_segments = len(segments)
        overlap_tokens = self._resolve_overlap_tokens(self.config.max_tokens_per_segment)
        split_items: List[CollectedItem] = []

        current_token_start = 0

        for segment_text in segments:
            boundary = None
            if boundaries and len(boundaries) == len(segments):
                boundary = boundaries[len(split_items)]

            segment_token_count = (
                len(self.token_encoder.encode(segment_text))
                if self.token_encoder
                else len(segment_text) // 4
            )

            if boundary:
                segment_start, segment_end = boundary
            else:
                segment_start = current_token_start
                segment_end = segment_start + segment_token_count

            segment_metadata = self._build_segment_metadata(
                base_metadata=original_item.metadata,
                original_id=original_id,
                segment_index=len(split_items),
                segment_count=total_segments,
                segment_token_start=segment_start,
                segment_token_end=min(segment_end, token_count)
            )

            split_item = CollectedItem(
                source_type=original_item.source_type,
                source_name=original_item.source_name,
                timestamp=original_item.timestamp,
                text=segment_text,
                metadata=segment_metadata
            )
            split_items.append(split_item)

            next_start = segment_end - overlap_tokens
            current_token_start = max(next_start, 0)

        return split_items
    
    def _extract_original_identifier(self, item: CollectedItem) -> MetadataValue:
        """
        CollectedItem에서 원본 메시지를 식별할 수 있는 메타데이터를 추출합니다.
        
        Args:
            item: 원본 CollectedItem 객체
        
        Returns:
            원본 메시지 ID 또는 None
        """
        metadata = item.metadata or {}

        candidate_keys = [
            "message_id",
            "original_message_id",
            "id",
            "document_id",
            "article_id"
        ]

        for key in candidate_keys:
            value = metadata.get(key)
            if isinstance(value, (str, int)):
                return value

        return None

    def _build_segment_metadata(
        self,
        base_metadata: Dict[str, MetadataValue],
        original_id: Optional[MetadataValue],
        segment_index: int,
        segment_count: int,
        segment_token_start: int,
        segment_token_end: int
    ) -> Dict[str, MetadataValue]:
        """
        세그먼트 메타데이터를 생성합니다.
        
        Args:
            base_metadata: 원본 메타데이터
            original_id: 원본 메시지 ID
            segment_index: 세그먼트 인덱스 (0부터 시작)
            segment_count: 전체 세그먼트 수
            segment_token_start: 세그먼트 시작 토큰 위치
            segment_token_end: 세그먼트 종료 토큰 위치
        
        Returns:
            보강된 메타데이터 딕셔너리
        """
        segment_metadata = dict(base_metadata)

        if original_id is not None:
            segment_metadata["original_message_id"] = original_id

        segment_metadata["segment_index"] = segment_index
        segment_metadata["segment_count"] = segment_count
        segment_metadata["segment_range_tokens"] = {
            "start": segment_token_start,
            "end": segment_token_end
        }

        return segment_metadata
    
    def _normalize_text(self, text: str) -> str:
        """
        텍스트를 정규화합니다.
        
        Args:
            text: 정규화할 텍스트
            
        Returns:
            정규화된 텍스트
        """
        if not text:
            return ""
        
        # 연속된 공백 정규화
        if self.config.normalize_whitespace:
            text = re.sub(r'\s+', ' ', text)
        
        # URL 제거 (선택적)
        if self.config.remove_urls:
            text = re.sub(r'https?://\S+', '', text)
        
        # @멘션 제거 (선택적)
        if self.config.remove_mentions:
            text = re.sub(r'@\w+', '', text)
        
        return text.strip()
    
    async def _detect_language(self, text: str) -> Optional[str]:
        """
        텍스트의 언어를 감지합니다.
        
        Args:
            text: 언어를 감지할 텍스트
            
        Returns:
            언어 코드 (예: "ko", "en") 또는 None (감지 실패 시)
        """
        if not self.config.language_detection_enabled or not LANGDETECT_AVAILABLE:
            return None
        
        if len(text.strip()) < self.config.min_text_length_for_detection:
            return None
        
        try:
            # langdetect는 동기 함수이지만, 비동기 컨텍스트에서 사용 가능
            detected = detect(text)
            logger.debug(f"[Preprocessor] 언어 감지 결과: {detected} (텍스트 길이: {len(text)})")
            return detected
        except LangDetectException as e:
            logger.debug(f"[Preprocessor] 언어 감지 실패: {e}")
            return None
        except Exception as e:
            logger.warning(f"[Preprocessor] 언어 감지 중 예상치 못한 오류: {e}")
            return None
    
    def _is_spam(self, text: str) -> bool:
        """
        텍스트가 스팸인지 판단합니다.
        
        Args:
            text: 판단할 텍스트
            
        Returns:
            스팸이면 True, 아니면 False
        """
        if not text:
            return False
        
        text_lower = text.lower()
        
        # 스팸 키워드 체크
        for keyword in self.config.spam_keywords:
            if keyword.lower() in text_lower:
                logger.debug(f"[Preprocessor] 스팸 키워드 발견: '{keyword}' in '{text[:50]}...'")
                return True
        
        return False

    def _log_segmentation_config(self) -> None:
        """
        장문 메시지 분할 관련 설정 값을 상세히 로깅합니다.
        """
        logger.info(
            "[Preprocessor] 장문 메시지 분할 설정 로드: "
            f"split_long_messages={self.config.split_long_messages}, "
            f"max_tokens_per_segment={self.config.max_tokens_per_segment}, "
            f"segment_overlap_tokens={self.config.segment_overlap_tokens}"
        )

    def _validate_segmentation_config(self) -> None:
        """
        장문 메시지 분할 설정 값이 유효한지 검증합니다.
        
        Raises:
            ValueError: 잘못된 설정 값이 발견된 경우
        """
        if not self.config.split_long_messages:
            if self.config.segment_overlap_tokens < 0:
                logger.warning(
                    "[Preprocessor] segment_overlap_tokens가 0 미만입니다. 0으로 보정합니다. "
                    f"현재 값={self.config.segment_overlap_tokens}"
                )
                self.config.segment_overlap_tokens = 0
            return

        if self.config.max_tokens_per_segment <= 0:
            raise ValueError(
                "[Preprocessor] max_tokens_per_segment는 1 이상의 정수여야 합니다. "
                f"현재 값={self.config.max_tokens_per_segment}"
            )

        if self.config.segment_overlap_tokens < 0:
            raise ValueError(
                "[Preprocessor] segment_overlap_tokens는 0 이상의 정수여야 합니다. "
                f"현재 값={self.config.segment_overlap_tokens}"
            )

        if self.config.segment_overlap_tokens >= self.config.max_tokens_per_segment:
            logger.warning(
                "[Preprocessor] segment_overlap_tokens가 max_tokens_per_segment 이상입니다. "
                "자동으로 max_tokens_per_segment-1로 조정합니다. "
                f"현재 segment_overlap_tokens={self.config.segment_overlap_tokens}, "
                f"max_tokens_per_segment={self.config.max_tokens_per_segment}"
            )
            self.config.segment_overlap_tokens = max(self.config.max_tokens_per_segment - 1, 0)

        if self.config.max_tokens_per_segment > self.config.max_tokens_per_item:
            logger.warning(
                "[Preprocessor] max_tokens_per_segment가 max_tokens_per_item을 초과합니다. "
                "세그먼트 생성 시 토큰 제한이 예상과 다르게 동작할 수 있습니다. "
                f"max_tokens_per_segment={self.config.max_tokens_per_segment}, "
                f"max_tokens_per_item={self.config.max_tokens_per_item}"
            )

        if self.config.split_long_messages and not self.token_encoder:
            logger.warning(
                "[Preprocessor] split_long_messages가 활성화되었지만 토큰 인코더를 사용할 수 없습니다. "
                "후속 단계에서 문자 기반 분할 로직이 필요합니다."
            )

        # 분할 경계 캐시 초기화
        self._segment_boundaries: List[tuple[int, int]] = []
    
    def count_tokens(self, text: str) -> int:
        """
        텍스트의 토큰 수를 계산합니다.
        
        Args:
            text: 토큰 수를 계산할 텍스트
            
        Returns:
            토큰 수
        """
        if not self.token_encoder:
            # 대략적인 추정 (문자 수 / 4)
            return len(text) // 4
        
        return len(self.token_encoder.encode(text))
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        텍스트를 지정된 토큰 수로 자릅니다.
        
        Args:
            text: 자를 텍스트
            max_tokens: 최대 토큰 수
            
        Returns:
            잘린 텍스트
        """
        if not self.token_encoder:
            # 대략적인 추정 (토큰 수 * 4)
            max_chars = max_tokens * 4
            return text[:max_chars]
        
        tokens = self.token_encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.token_encoder.decode(truncated_tokens)
    
    async def chunk_messages(
        self,
        records: List[Dict[str, Any]],
        max_tokens: int = 50000
    ) -> List[List[Dict[str, Any]]]:
        """
        레코드를 토큰 제한을 고려하여 청크로 분할합니다.
        
        LLM 파이프라인 문서의 섹션 2.2를 참조하여 구현되었습니다.
        - 소스별 그룹화: RSS와 텔레그램을 별도 그룹으로 구성하여 컨텍스트 유지
        - 시간순 정렬: 각 청크 내에서 시간순으로 정렬하여 시간적 맥락 보존
        - 토큰 제한: tiktoken을 사용하여 정확한 토큰 수 계산
        
        Args:
            records: 정규화된 데이터 레코드 리스트 (Dict 형식)
                각 레코드는 다음 형식을 가져야 합니다:
                {
                    "source": "rss" | "telegram",
                    "timestamp": "ISO 8601 형식 문자열",
                    "text": "원본 텍스트",
                    "meta": {...}
                }
            max_tokens: 각 청크의 최대 토큰 수 (기본값: 50000)
        
        Returns:
            청크 리스트 (각 청크는 레코드 리스트)
            각 청크는 시간순으로 정렬되어 있습니다.
        """
        from collections import defaultdict
        
        logger.info(
            f"[Preprocessor] 청크 생성 시작: 전체 레코드={len(records)}개, "
            f"최대 토큰 수={max_tokens}"
        )
        
        if not records:
            logger.warning("[Preprocessor] 빈 레코드 리스트입니다.")
            return []
        
        # 1. 소스별로 그룹화
        by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for record in records:
            source = record.get("source", "unknown")
            by_source[source].append(record)
        
        logger.info(
            f"[Preprocessor] 소스별 그룹화 완료: "
            f"소스 종류={list(by_source.keys())}, "
            f"각 소스별 레코드 수={[(k, len(v)) for k, v in by_source.items()]}"
        )
        
        # 2. 각 소스 그룹 내에서 시간순 정렬
        for source in by_source:
            try:
                by_source[source].sort(
                    key=lambda r: self._parse_timestamp(r.get("timestamp", ""))
                )
            except Exception as e:
                logger.warning(
                    f"[Preprocessor] 소스 '{source}'의 시간순 정렬 실패: {e}. "
                    f"원본 순서 유지합니다."
                )
        
        # 3. 소스별로 순회하면서 토큰 제한을 고려하여 청크 생성
        all_chunks: List[List[Dict[str, Any]]] = []
        
        for source, source_records in by_source.items():
            logger.info(
                f"[Preprocessor] 소스 '{source}' 청크 생성 시작: "
                f"레코드 수={len(source_records)}개"
            )
            
            source_chunks = self._create_chunks_for_source(
                source_records=source_records,
                max_tokens=max_tokens,
                source_name=source
            )
            
            all_chunks.extend(source_chunks)
            
            logger.info(
                f"[Preprocessor] 소스 '{source}' 청크 생성 완료: "
                f"생성된 청크 수={len(source_chunks)}개"
            )
        
        # 4. 최종 통계 로깅
        total_tokens = sum(
            sum(self._estimate_record_tokens(record) for record in chunk)
            for chunk in all_chunks
        )
        
        logger.info(
            f"[Preprocessor] 청크 생성 완료: "
            f"전체 청크 수={len(all_chunks)}개, "
            f"평균 청크 크기={len(records) / len(all_chunks) if all_chunks else 0:.1f}개 레코드/청크, "
            f"전체 예상 토큰 수={total_tokens:,}개"
        )
        
        # 각 청크의 상세 정보 로깅
        for i, chunk in enumerate(all_chunks):
            chunk_tokens = sum(
                self._estimate_record_tokens(record) for record in chunk
            )
            chunk_sources = set(record.get("source", "unknown") for record in chunk)
            
            logger.debug(
                f"[Preprocessor] 청크 {i+1}/{len(all_chunks)}: "
                f"레코드 수={len(chunk)}개, "
                f"예상 토큰 수={chunk_tokens:,}개, "
                f"소스={list(chunk_sources)}"
            )
        
        return all_chunks
    
    def _create_chunks_for_source(
        self,
        source_records: List[Dict[str, Any]],
        max_tokens: int,
        source_name: str
    ) -> List[List[Dict[str, Any]]]:
        """
        특정 소스의 레코드들을 토큰 제한을 고려하여 청크로 분할합니다.
        
        Args:
            source_records: 소스별로 그룹화되고 시간순 정렬된 레코드 리스트
            max_tokens: 각 청크의 최대 토큰 수
            source_name: 소스 이름 (로깅용)
        
        Returns:
            청크 리스트
        """
        chunks: List[List[Dict[str, Any]]] = []
        current_chunk: List[Dict[str, Any]] = []
        current_tokens = 0
        
        for record in source_records:
            # 레코드의 토큰 수 추정
            record_tokens = self._estimate_record_tokens(record)
            
            # 현재 청크에 추가하면 토큰 제한을 초과하는 경우
            if current_tokens + record_tokens > max_tokens and current_chunk:
                # 현재 청크를 저장하고 새 청크 시작
                chunks.append(current_chunk)
                logger.debug(
                    f"[Preprocessor] 소스 '{source_name}' 청크 완료: "
                    f"레코드 수={len(current_chunk)}개, "
                    f"토큰 수={current_tokens:,}개"
                )
                
                current_chunk = [record]
                current_tokens = record_tokens
            else:
                # 현재 청크에 추가
                current_chunk.append(record)
                current_tokens += record_tokens
        
        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk)
            logger.debug(
                f"[Preprocessor] 소스 '{source_name}' 마지막 청크 완료: "
                f"레코드 수={len(current_chunk)}개, "
                f"토큰 수={current_tokens:,}개"
            )
        
        return chunks
    
    def _estimate_record_tokens(self, record: Dict[str, Any]) -> int:
        """
        레코드의 예상 토큰 수를 계산합니다.
        
        텍스트와 메타데이터를 모두 고려하여 토큰 수를 추정합니다.
        
        Args:
            record: 정규화된 데이터 레코드
        
        Returns:
            예상 토큰 수
        """
        if not self.token_encoder:
            # 대략적인 추정 (문자 수 / 4)
            text = record.get("text", "")
            meta = record.get("meta", {})
            meta_text = " ".join(str(v) for v in meta.values() if v)
            total_text = f"{text} {meta_text}"
            return len(total_text) // 4
        
        # 정확한 토큰 수 계산
        text = record.get("text", "")
        meta = record.get("meta", {})
        
        # 메타데이터도 토큰 수에 포함
        meta_text = " ".join(str(v) for v in meta.values() if v)
        total_text = f"{text} {meta_text}"
        
        return len(self.token_encoder.encode(total_text))
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        타임스탬프 문자열을 datetime 객체로 변환합니다.
        
        Args:
            timestamp_str: ISO 8601 형식의 타임스탬프 문자열
        
        Returns:
            datetime 객체
        """
        from dateutil import parser
        
        if isinstance(timestamp_str, datetime):
            return timestamp_str
        
        try:
            return parser.parse(timestamp_str)
        except Exception as e:
            logger.warning(
                f"[Preprocessor] 타임스탬프 파싱 실패: '{timestamp_str}', "
                f"오류={e}. 최소값 반환합니다."
            )
            # 파싱 실패 시 최소값 반환 (정렬 시 앞에 오도록)
            return datetime.min.replace(tzinfo=None)

    def _split_text_to_segments(
        self,
        text: str,
        max_tokens: Optional[int] = None
    ) -> List[str]:
        """
        장문 텍스트를 토큰 기준으로 분할합니다.
        
        Args:
            text: 분할할 원본 텍스트
            max_tokens: 세그먼트당 최대 토큰 수 (None이면 설정값 사용)
        
        Returns:
            토큰 기준으로 분할된 텍스트 세그먼트 리스트
        
        Raises:
            ValueError: 잘못된 토큰 제한 값이 전달된 경우
            RuntimeError: 토큰 인코더를 사용할 수 없는 경우
        """
        effective_max_tokens = max_tokens or self.config.max_tokens_per_segment
        overlap_tokens = self._resolve_overlap_tokens(effective_max_tokens)

        if effective_max_tokens <= 0:
            raise ValueError(
                "[Preprocessor] 세그먼트당 최대 토큰 수는 1 이상의 정수여야 합니다. "
                f"effective_max_tokens={effective_max_tokens}"
            )

        if not text:
            logger.info("[Preprocessor] 빈 텍스트 입력: 세그먼트가 생성되지 않습니다.")
            self._segment_boundaries = []
            return []

        if self.token_encoder:
            return self._split_with_token_encoder(
                text=text,
                max_tokens=effective_max_tokens,
                overlap_tokens=overlap_tokens
            )

        logger.warning(
            "[Preprocessor] 토큰 인코더를 사용할 수 없어 문자 기반 분할을 수행합니다."
        )

        return self._split_without_token_encoder(
            text=text,
            max_tokens=effective_max_tokens,
            overlap_tokens=overlap_tokens
        )

    def _resolve_overlap_tokens(self, max_tokens: int) -> int:
        """
        장문 분할 시 사용할 오버랩 토큰 수를 계산합니다.
        
        Args:
            max_tokens: 세그먼트당 최대 토큰 수
        
        Returns:
            유효한 오버랩 토큰 수
        """
        if max_tokens <= 1:
            return 0

        desired_overlap = self.config.segment_overlap_tokens
        overlap = max(0, min(desired_overlap, max_tokens - 1))

        if overlap < desired_overlap:
            logger.warning(
                "[Preprocessor] segment_overlap_tokens 조정: "
                f"요청된 값={desired_overlap}, 적용 값={overlap}, "
                f"max_tokens={max_tokens}"
            )

        return overlap

    def _split_with_token_encoder(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int
    ) -> List[str]:
        """
        토큰 인코더를 사용하여 텍스트를 분할합니다.
        
        Args:
            text: 분할할 텍스트
            max_tokens: 세그먼트당 최대 토큰 수
            overlap_tokens: 세그먼트 간 토큰 오버랩 크기
        
        Returns:
            토큰 기반 세그먼트 리스트
        """
        tokens = self.token_encoder.encode(text)
        total_tokens = len(tokens)
        boundaries: List[tuple[int, int]] = []

        if total_tokens <= max_tokens:
            logger.info(
                "[Preprocessor] 텍스트 토큰 수가 제한 이하입니다. 단일 세그먼트 반환. "
                f"total_tokens={total_tokens}, max_tokens={max_tokens}"
            )
            self._segment_boundaries = [(0, total_tokens)]
            return [text]

        segments: List[str] = []
        start_index = 0
        segment_index = 0

        while start_index < total_tokens:
            end_index = min(start_index + max_tokens, total_tokens)
            segment_tokens = tokens[start_index:end_index]
            segment_text = self.token_encoder.decode(segment_tokens)

            segments.append(segment_text)
            boundaries.append((start_index, end_index))

            logger.debug(
                "[Preprocessor] 토큰 세그먼트 생성: "
                f"index={segment_index}, start_token={start_index}, end_token={end_index}, "
                f"segment_token_count={len(segment_tokens)}, overlap_tokens={overlap_tokens}"
            )

            if end_index >= total_tokens:
                break

            start_index = max(0, end_index - overlap_tokens)
            segment_index += 1

        logger.info(
            "[Preprocessor] 토큰 기반 텍스트 분할 완료: "
            f"total_tokens={total_tokens}, max_tokens={max_tokens}, "
            f"overlap_tokens={overlap_tokens}, segment_count={len(segments)}"
        )

        self._segment_boundaries = boundaries
        return segments

    def _split_without_token_encoder(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int
    ) -> List[str]:
        """
        토큰 인코더를 사용할 수 없는 경우 문자 기반으로 텍스트를 분할합니다.
        
        Args:
            text: 분할할 텍스트
            max_tokens: 세그먼트당 최대 토큰 수(문자 수 추정에 사용)
            overlap_tokens: 세그먼트 간 토큰 오버랩 크기(문자 수 추정에 사용)
        
        Returns:
            문자 기반 세그먼트 리스트
        """
        estimated_chars_per_token = 4
        max_chars = max_tokens * estimated_chars_per_token
        overlap_chars = overlap_tokens * estimated_chars_per_token
        total_chars = len(text)
        boundaries: List[tuple[int, int]] = []

        if max_chars <= 0:
            raise ValueError(
                "[Preprocessor] 문자 기반 분할에 사용할 최대 문자 수가 1 이상이어야 합니다. "
                f"max_chars={max_chars}"
            )

        if total_chars <= max_chars:
            logger.info(
                "[Preprocessor] 텍스트 길이가 제한 이하입니다. 단일 세그먼트 반환. "
                f"total_chars={total_chars}, max_chars={max_chars}"
            )
            estimated_tokens = total_chars // estimated_chars_per_token
            self._segment_boundaries = [(0, estimated_tokens)]
            return [text]

        segments: List[str] = []
        start_index = 0
        segment_index = 0

        while start_index < total_chars:
            end_index = min(start_index + max_chars, total_chars)
            segment_text = text[start_index:end_index]

            segments.append(segment_text)
            estimated_start = start_index // estimated_chars_per_token
            estimated_end = end_index // estimated_chars_per_token
            boundaries.append((estimated_start, estimated_end))

            logger.debug(
                "[Preprocessor] 문자 세그먼트 생성: "
                f"index={segment_index}, start_char={start_index}, end_char={end_index}, "
                f"segment_char_count={len(segment_text)}, overlap_chars={overlap_chars}"
            )

            if end_index >= total_chars:
                break

            start_index = max(0, end_index - overlap_chars)
            segment_index += 1

        logger.info(
            "[Preprocessor] 문자 기반 텍스트 분할 완료: "
            f"total_chars={total_chars}, max_chars={max_chars}, "
            f"overlap_chars={overlap_chars}, segment_count={len(segments)}"
        )

        self._segment_boundaries = boundaries
        return segments


# 모듈 레벨 함수: Preprocessor 인스턴스를 사용하여 청크 생성
async def chunk_messages(
    records: List[Dict[str, Any]],
    max_tokens: int = 50000,
    token_encoding: str = "cl100k_base"
) -> List[List[Dict[str, Any]]]:
    """
    레코드를 토큰 제한을 고려하여 청크로 분할합니다.
    
    LLM 파이프라인 문서의 섹션 2.2를 참조하여 구현되었습니다.
    이 함수는 Preprocessor 인스턴스를 내부적으로 생성하여 사용합니다.
    
    Args:
        records: 정규화된 데이터 레코드 리스트 (Dict 형식)
        max_tokens: 각 청크의 최대 토큰 수 (기본값: 50000)
        token_encoding: tiktoken 인코딩 방식 (기본값: "cl100k_base")
    
    Returns:
        청크 리스트 (각 청크는 레코드 리스트)
    """
    preprocessor = Preprocessor(
        config=PreprocessingConfig(token_encoding=token_encoding)
    )
    return await preprocessor.chunk_messages(records, max_tokens)


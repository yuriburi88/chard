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
from src.collectors.models import Article, TelegramMessage, CollectedItem

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
                        logger.debug(f"[Preprocessor] 토큰 제한 초과 제외: source={item.source_name}, 토큰={token_count}")
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
            f"토큰필터={stats['token_filtered']}, 길이필터={stats['length_filtered']}"
        )
        
        return processed_items
    
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


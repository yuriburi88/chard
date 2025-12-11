"""
동적 키워드 학습 및 관리 시스템

- 고정 키워드와 동적 학습 키워드를 병합
- JSON 캐시 기반으로 24시간 TTL 관리
- LLM을 통해 자주 등장하는 키워드를 자동 분류
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


class DynamicKeywordManager:
    """
    동적 키워드를 관리하는 클래스

    - JSON 캐시 파일로 학습된 키워드 저장
    - TTL(Time To Live) 기반으로 만료된 키워드 자동 삭제
    - 카테고리별 키워드 조회 및 업데이트
    """

    def __init__(
        self,
        cache_file: str = "dynamic_keywords_cache.json",
        ttl_hours: int = 24,
    ):
        """
        Args:
            cache_file: 동적 키워드를 저장할 JSON 파일 경로
            ttl_hours: 키워드 유효 시간(기본 24시간)
        """
        self.cache_file = Path(cache_file)
        self.ttl_hours = ttl_hours
        self.cache: Dict[str, Dict] = {}

        # 캐시 로드
        self._load_cache()

        # 만료된 키워드 제거
        self._cleanup_expired()

    def _load_cache(self) -> None:
        """JSON 캐시 파일에서 동적 키워드를 로드합니다."""
        if not self.cache_file.exists():
            logger.info(f"캐시 파일이 없습니다: {self.cache_file}. 빈 캐시로 시작합니다.")
            self.cache = {}
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
            logger.info(f"캐시 로드 완료: {len(self.cache)}개의 동적 키워드")
        except Exception as e:
            logger.error(f"캐시 로드 실패: {e}. 빈 캐시로 시작합니다.")
            self.cache = {}

    def _save_cache(self) -> None:
        """현재 캐시를 JSON 파일로 저장합니다."""
        try:
            # 부모 디렉토리 생성
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.info(f"캐시 저장 완료: {len(self.cache)}개의 동적 키워드")
        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")

    def _cleanup_expired(self) -> None:
        """TTL이 만료된 키워드를 캐시에서 제거합니다."""
        now = datetime.now()
        expired_keywords = []

        for keyword, data in self.cache.items():
            added_at_str = data.get("added_at")
            if not added_at_str:
                # added_at이 없는 경우 삭제
                expired_keywords.append(keyword)
                continue

            try:
                added_at = datetime.fromisoformat(added_at_str)
                age = now - added_at

                if age > timedelta(hours=self.ttl_hours):
                    expired_keywords.append(keyword)
            except Exception as e:
                logger.warning(f"키워드 '{keyword}' 만료 시간 파싱 실패: {e}")
                expired_keywords.append(keyword)

        # 만료된 키워드 삭제
        for keyword in expired_keywords:
            del self.cache[keyword]

        if expired_keywords:
            logger.info(f"만료된 {len(expired_keywords)}개의 키워드 제거: {expired_keywords[:5]}...")
            self._save_cache()

    def update_keywords(
        self,
        learned_keywords: Dict[str, List[str]],
    ) -> None:
        """
        LLM이 학습한 새로운 키워드를 캐시에 추가합니다.

        Args:
            learned_keywords: {"macro": ["keyword1", ...], "crypto_native": [...], ...}
        """
        now = datetime.now().isoformat()
        added_count = 0

        for category, keywords in learned_keywords.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()

                # 이미 있는 키워드는 업데이트 (시간 갱신)
                if keyword_lower in self.cache:
                    self.cache[keyword_lower]["added_at"] = now
                    # categories를 리스트로 관리 (JSON 직렬화 가능)
                    if category not in self.cache[keyword_lower]["categories"]:
                        self.cache[keyword_lower]["categories"].append(category)
                else:
                    # 새로운 키워드 추가
                    self.cache[keyword_lower] = {
                        "original": keyword,
                        "categories": [category],  # 리스트로 저장 (JSON 직렬화 가능)
                        "added_at": now,
                    }
                    added_count += 1

        logger.info(f"동적 키워드 업데이트 완료: {added_count}개 추가, 총 {len(self.cache)}개")
        self._save_cache()

    def get_keywords_by_category(self, category: str) -> Set[str]:
        """
        특정 카테고리에 속한 동적 키워드를 반환합니다.

        Args:
            category: "macro", "crypto_native", "crypto_macro"

        Returns:
            해당 카테고리의 키워드 세트 (소문자)
        """
        keywords = set()

        for keyword, data in self.cache.items():
            categories = data.get("categories", [])
            if category in categories:
                keywords.add(keyword)

        return keywords

    def get_all_keywords(self) -> Dict[str, Set[str]]:
        """
        모든 동적 키워드를 카테고리별로 반환합니다.

        Returns:
            {"macro": {...}, "crypto_native": {...}, "crypto_macro": {...}}
        """
        result = {
            "macro": set(),
            "crypto_native": set(),
            "crypto_macro": set(),
        }

        for keyword, data in self.cache.items():
            categories = data.get("categories", [])
            for category in categories:
                if category in result:
                    result[category].add(keyword)

        return result

    def clear_cache(self) -> None:
        """캐시를 완전히 초기화합니다. (테스트 용도)"""
        self.cache = {}
        self._save_cache()
        logger.info("동적 키워드 캐시 초기화 완료")

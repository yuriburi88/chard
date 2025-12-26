# CHARD 코딩 컨벤션 가이드

이 문서는 CHARD 프로젝트의 코딩 스타일과 규칙을 정의합니다.

## 1. 네이밍 컨벤션

### 1.1 변수명
```python
# snake_case 사용
user_name = "john"
article_count = 10
is_valid = True

# 상수는 UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://api.example.com"
```

### 1.2 함수명
```python
# snake_case 사용, 동사로 시작
def fetch_articles():
    pass

def calculate_score(data: dict) -> float:
    pass

async def collect_rss_feed(url: str) -> list:
    pass

# Private 함수는 _ 접두사
def _parse_response(response):
    pass
```

### 1.3 클래스명
```python
# PascalCase 사용
class RSSCollector:
    pass

class TelegramMessageParser:
    pass

class BaseCollector(ABC):
    pass
```

### 1.4 파일명
```
# snake_case 사용
rss_collector.py
telegram_collector.py
langgraph_pipeline.py

# 테스트 파일은 test_ 접두사
test_rss_collector.py
test_telegram_collector.py
```

### 1.5 모듈/패키지명
```
# 소문자, 짧고 명확하게
src/
├── collectors/
├── workflows/
├── report/
└── utils/
```

---

## 2. Import 순서 및 구조

isort 설정에 따라 자동 정렬됩니다. 수동 작성 시 아래 순서를 따릅니다:

```python
# 1. 표준 라이브러리
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# 2. 서드파티 라이브러리
import httpx
import yaml
from langchain import LLM
from pydantic import BaseModel

# 3. 로컬 모듈 (프로젝트 내부)
from src.collectors.rss_collector import RSSCollector
from src.utils.async_utils import run_async
```

### Import 규칙
- 와일드카드 import(`from module import *`) 금지
- 각 그룹 사이에 빈 줄 1개
- 알파벳 순서로 정렬

---

## 3. Type Hints 사용 가이드

### 3.1 기본 타입
```python
def process_article(title: str, score: float, tags: list[str]) -> dict:
    pass

def get_articles(limit: int = 10) -> list[dict]:
    pass
```

### 3.2 Optional과 Union
```python
from typing import Optional, Union

def fetch_data(url: str, timeout: Optional[int] = None) -> Optional[dict]:
    pass

def parse_value(value: Union[str, int]) -> str:
    pass

# Python 3.10+ 스타일
def parse_value(value: str | int) -> str:
    pass
```

### 3.3 복잡한 타입
```python
from typing import Any, Callable, Dict, List, TypeVar

# Dict와 List
def process_items(items: List[Dict[str, Any]]) -> Dict[str, int]:
    pass

# Callable
def apply_filter(data: list, filter_fn: Callable[[dict], bool]) -> list:
    pass

# TypeVar (제네릭)
T = TypeVar("T")

def first_item(items: List[T]) -> Optional[T]:
    return items[0] if items else None
```

### 3.4 클래스 메서드
```python
class Article:
    def __init__(self, title: str, content: str) -> None:
        self.title = title
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Article":
        return cls(data["title"], data["content"])
```

---

## 4. Docstring 작성 가이드 (Google 스타일)

### 4.1 함수 Docstring
```python
def collect_articles(
    source_url: str,
    max_count: int = 100,
    hours_back: int = 24
) -> list[dict]:
    """RSS 피드에서 기사를 수집합니다.

    Args:
        source_url: RSS 피드 URL
        max_count: 최대 수집 기사 수 (기본값: 100)
        hours_back: 수집할 기간 (시간 단위, 기본값: 24)

    Returns:
        수집된 기사 목록. 각 기사는 title, link, published 키를 포함합니다.

    Raises:
        httpx.HTTPError: HTTP 요청 실패 시
        ValueError: 유효하지 않은 URL인 경우

    Example:
        >>> articles = collect_articles("https://example.com/feed")
        >>> len(articles)
        42
    """
    pass
```

### 4.2 클래스 Docstring
```python
class RSSCollector:
    """RSS 피드 수집기.

    RSS 피드를 파싱하여 기사 목록을 반환합니다.
    비동기 HTTP 클라이언트를 사용하여 병렬 수집을 지원합니다.

    Attributes:
        sources: RSS 소스 설정 목록
        client: HTTP 클라이언트 인스턴스

    Example:
        >>> collector = RSSCollector(sources)
        >>> articles = await collector.collect()
    """

    def __init__(self, sources: list[dict]) -> None:
        """RSSCollector를 초기화합니다.

        Args:
            sources: RSS 소스 설정 목록
        """
        self.sources = sources
```

### 4.3 모듈 Docstring
```python
"""RSS 수집 모듈.

이 모듈은 RSS 피드를 수집하고 파싱하는 기능을 제공합니다.

주요 컴포넌트:
    - RSSCollector: 메인 수집기 클래스
    - parse_feed: RSS 피드 파싱 함수
    - filter_by_date: 날짜 기반 필터링 함수

사용 예시:
    from src.collectors.rss_collector import RSSCollector

    collector = RSSCollector(sources)
    articles = await collector.collect()
"""
```

---

## 5. 코드 포맷팅

### 5.1 라인 길이
- 최대 88자 (Black 기본값)

### 5.2 들여쓰기
- 4 스페이스 (탭 사용 금지)

### 5.3 문자열
```python
# 작은따옴표 또는 큰따옴표 일관되게 사용 (Black이 자동 처리)
name = "CHARD"
message = f"Hello, {name}!"

# 여러 줄 문자열
long_text = """
이것은 여러 줄에 걸친
긴 문자열입니다.
"""
```

### 5.4 컬렉션
```python
# 여러 줄로 작성 시 후행 콤마 사용
sources = [
    "source1",
    "source2",
    "source3",
]

config = {
    "name": "CHARD",
    "version": "0.1.0",
    "debug": True,
}
```

---

## 6. 에러 처리

```python
# 구체적인 예외 사용
try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.TimeoutException:
    logger.warning(f"Timeout: {url}")
    return []
except httpx.HTTPStatusError as e:
    logger.error(f"HTTP error {e.response.status_code}: {url}")
    raise

# 커스텀 예외 정의
class CollectionError(Exception):
    """데이터 수집 중 발생한 에러."""
    pass
```

---

## 7. 로깅

```python
import logging

logger = logging.getLogger(__name__)

# 로그 레벨별 사용
logger.debug("상세 디버그 정보")
logger.info("일반 정보")
logger.warning("경고 메시지")
logger.error("에러 발생")
logger.exception("예외 발생 (스택 트레이스 포함)")
```

---

## 8. 도구 실행 명령어

```bash
# 코드 포맷팅
python -m black .
python -m isort .

# 린팅
python -m ruff check .
python -m ruff check . --fix  # 자동 수정

# 타입 체크
python -m mypy src/

# 테스트
python -m pytest
python -m pytest --cov=src  # 커버리지 포함
```

---

*최종 수정일: 2024-12-26*

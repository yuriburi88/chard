# CHARD Collectors 모듈

데이터 수집을 담당하는 모듈입니다.

## 구조

```
collectors/
├── __init__.py
├── models.py              # 데이터 모델 정의
├── article_factory.py     # Article 생성 팩토리
├── rss_collector.py       # RSS 피드 수집기
├── telegram_collector.py  # Telegram 메시지 수집기
└── economic_calendar_collector.py  # 경제 캘린더 수집기
```

## 데이터 모델 (`models.py`)

### Article
RSS 피드에서 수집한 기사 데이터 모델

```python
@dataclass
class Article:
    title: str
    content: str
    source: str
    url: str
    timestamp: datetime
    tags: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
```

### TelegramMessage
Telegram 채널에서 수집한 메시지 데이터 모델

```python
@dataclass
class TelegramMessage:
    channel_id: str
    channel_name: str
    message_id: int
    content: str
    timestamp: datetime
    meta: dict = field(default_factory=dict)
```

### CollectedItem
정규화된 수집 아이템 (모든 소스에서 공통으로 사용)

```python
@dataclass
class CollectedItem:
    source: str          # "rss", "telegram", "economic_calendar"
    source_name: str     # 소스 이름 (예: "CoinDesk", "cryptonews")
    text: str            # 본문 텍스트
    timestamp: datetime
    meta: dict = field(default_factory=dict)
```

## 수집기

### RSSCollector (`rss_collector.py`)

RSS 피드에서 기사를 수집합니다.

**주요 기능:**
- 여러 RSS 피드 동시 수집
- 시간 기반 필터링 (특정 기간 내 기사만 수집)
- 중복 제거
- 태그 추출

**사용 예시:**
```python
from src.collectors.rss_collector import RSSCollector
from src.config_manager import RSSSourceConfig

config = RSSSourceConfig(
    name="CoinDesk",
    url="https://www.coindesk.com/feed/",
    priority=1,
    max_articles=50
)

collector = RSSCollector()
articles = await collector.collect(config, min_timestamp=some_datetime)
```

### TelegramCollector (`telegram_collector.py`)

Telegram 채널에서 메시지를 수집합니다.

**지원 인증 방식:**
- `bot_api`: Telegram Bot API 사용
- `mtproto`: MTProto API 사용 (Telethon)

**사용 예시:**
```python
from src.collectors.telegram_collector import TelegramCollector
from src.config_manager import TelegramSourceConfig

config = TelegramSourceConfig(
    name="Crypto News",
    channel_id="cryptonews",
    auth_method="bot_api",
    max_messages=100
)

collector = TelegramCollector.create(config, bot_token="YOUR_BOT_TOKEN")
messages = await collector.collect(config, min_timestamp=some_datetime)
```

### EconomicCalendarCollector (`economic_calendar_collector.py`)

경제 캘린더 이벤트를 수집합니다.

**사용 예시:**
```python
from src.collectors.economic_calendar_collector import collect_economic_calendar

events = await collect_economic_calendar(
    countries=["united states", "south korea"],
    start_date=date.today(),
    end_date=date.today() + timedelta(days=7)
)
```

## 설정

수집기 설정은 `config/config.yml`에서 관리됩니다:

```yaml
rss_sources:
  - name: "CoinDesk"
    url: "https://www.coindesk.com/feed/"
    priority: 1
    max_articles: 50

telegram_sources:
  - name: "Crypto News"
    channel_id: "cryptonews"
    auth_method: "bot_api"
    max_messages: 100
```

# CHARD 설정 파일 레퍼런스

이 문서는 `config.yml` 파일의 모든 설정 항목을 설명합니다.

## 목차
1. [수집 기간 설정](#1-수집-기간-설정-collection_period)
2. [RSS 소스 설정](#2-rss-소스-설정-rss_sources)
3. [Economic Calendar 설정](#3-economic-calendar-설정-economic_calendar)
4. [Telegram 소스 설정](#4-telegram-소스-설정-telegram_sources)
5. [LLM 설정](#5-llm-설정-llm)
6. [전처리 설정](#6-전처리-설정-preprocessing)
7. [정규화 설정](#7-정규화-설정-normalization)
8. [내러티브 설정](#8-내러티브-설정-narrative)
9. [출력 설정](#9-출력-설정-output)

---

## 1. 수집 기간 설정 (`collection_period`)

데이터 수집 기간을 설정합니다.

```yaml
collection_period:
  mode: days_back      # "recent_hours" 또는 "days_back"
  days_back: 1         # mode가 "days_back"일 때 사용
  recent_hours: 24     # mode가 "recent_hours"일 때 사용
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `mode` | string | `days_back` | 수집 모드 선택 |
| `days_back` | integer | `1` | N일 전 00:00부터 현재까지 수집 |
| `recent_hours` | integer | `24` | 현재 시간 기준 N시간 전부터 수집 |

**모드 차이 예시** (현재 11/24 16:44인 경우):
- `mode: recent_hours, recent_hours: 24` → 11/23 16:44 ~ 현재
- `mode: days_back, days_back: 1` → 11/23 00:00 ~ 현재
- `mode: days_back, days_back: 3` → 11/21 00:00 ~ 현재

---

## 2. RSS 소스 설정 (`rss_sources`)

RSS 피드 수집 소스 목록을 정의합니다.

```yaml
rss_sources:
  - name: CoinDesk
    url: https://www.coindesk.com/arc/outboundfeeds/rss?outputType=xml
    priority: 1.1
    timezone: 0
    max_articles: 5000
    hours_back: 24
```

| 항목 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | O | 소스 식별 이름 (고유해야 함) |
| `url` | string | O | RSS 피드 URL |
| `priority` | float | O | 중요도 가중치 (1.0 기준, 높을수록 중요) |
| `timezone` | integer | O | 소스의 타임존 (UTC 기준 오프셋, 예: 한국=9, 미국 동부=-5) |
| `max_articles` | integer | O | 최대 수집 기사 수 |
| `hours_back` | integer | O | 개별 소스의 수집 기간 (시간) |

**주요 RSS 소스 예시:**
- 한국: BlockMedia, Informax 시리즈 (timezone: 9)
- 미국: CoinDesk, CoinTelegraph, Yahoo Finance (timezone: 0 또는 -5)
- 글로벌: The Block, Decrypt, CryptoSlate (timezone: 0)

---

## 3. Economic Calendar 설정 (`economic_calendar`)

경제 지표 캘린더 수집을 설정합니다.

```yaml
economic_calendar:
  enabled: true
  countries:
    - united states
    - china
    - japan
  importance: high
  days_back: 7
  days_forward: 14
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | `true` | Economic Calendar 수집 활성화 |
| `countries` | list | - | 수집할 국가 목록 (소문자) |
| `importance` | string | `high` | 중요도 필터: `high`, `medium`, `low`, `all` |
| `days_back` | integer | `7` | 과거 데이터 수집 기간 (일) |
| `days_forward` | integer | `14` | 미래 예정 일정 수집 기간 (일) |

**지원 국가:**
`united states`, `china`, `japan`, `eurozone`, `canada`, `australia`, `united kingdom`, `germany`, `france`, `south korea` 등

---

## 4. Telegram 소스 설정 (`telegram_sources`)

Telegram 채널 수집을 설정합니다.

```yaml
telegram_sources:
  - name: rich_kim88
    auth_method: mtproto
    channel_id: coinnesskr
    tg_cred_id: eric
    session_file: secrets/telegram_sessions/tg_cred_eric.session
    max_messages: 5000
```

| 항목 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | O | 소스 식별 이름 |
| `auth_method` | string | O | 인증 방식 (`mtproto` 또는 `bot`) |
| `channel_id` | string | O | Telegram 채널 ID 또는 username |
| `tg_cred_id` | string | O | 자격 증명 ID (.env 파일 참조) |
| `session_file` | string | O | 세션 파일 경로 |
| `max_messages` | integer | O | 최대 수집 메시지 수 |

**인증 방식:**
- `mtproto`: Telethon 라이브러리 사용 (개인 계정)
- `bot`: python-telegram-bot 사용 (봇 계정)

---

## 5. LLM 설정 (`llm`)

LLM(대규모 언어 모델) 설정입니다.

```yaml
llm:
  model: gemini-2.5-flash
  provider: google
  max_tokens: 8000
  temperature: 0.1
  chunk_size: 50000
  parallel_concurrency: 3
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `model` | string | - | 사용할 모델 이름 |
| `provider` | string | - | LLM 제공자 (`google`, `openai`) |
| `max_tokens` | integer | `8000` | 최대 출력 토큰 수 |
| `temperature` | float | `0.1` | 출력 다양성 (0.0~1.0, 낮을수록 일관성) |
| `chunk_size` | integer | `50000` | 입력 청크 크기 (토큰) |
| `parallel_concurrency` | integer | `3` | 병렬 처리 동시성 |

**지원 모델:**
- Google: `gemini-2.5-flash`, `gemini-2.5-pro`
- OpenAI: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`

---

## 6. 전처리 설정 (`preprocessing`)

메시지 전처리 옵션입니다.

```yaml
preprocessing:
  split_long_messages: true
  max_tokens_per_segment: 4000
  segment_overlap_tokens: 200
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `split_long_messages` | boolean | `true` | 긴 메시지 분할 활성화 |
| `max_tokens_per_segment` | integer | `4000` | 세그먼트당 최대 토큰 수 |
| `segment_overlap_tokens` | integer | `200` | 세그먼트 간 겹치는 토큰 수 |

---

## 7. 정규화 설정 (`normalization`)

키워드 정규화 및 임베딩 설정입니다.

```yaml
normalization:
  embedding_threshold: 0.90
  dbscan_min_samples: 2
  llm_verification_enabled: true
  llm_verification_top_n: 30
  embedding_provider: google
  embedding_model: models/text-embedding-004
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `embedding_threshold` | float | `0.90` | 임베딩 유사도 임계값 (높을수록 엄격) |
| `dbscan_min_samples` | integer | `2` | DBSCAN 클러스터 최소 샘플 수 |
| `llm_verification_enabled` | boolean | `true` | LLM 검증 활성화 |
| `llm_verification_top_n` | integer | `30` | 검증할 상위 키워드 수 |
| `embedding_provider` | string | `google` | 임베딩 제공자 |
| `embedding_model` | string | - | 임베딩 모델 이름 |

---

## 8. 내러티브 설정 (`narrative`)

내러티브 생성 설정입니다.

```yaml
narrative:
  enable_segmentation: true
  crypto_paragraphs: 2
  integrated_paragraphs: 3
  min_category_confidence: 0.5
  category_thresholds:
    macro: 0.4
    crypto: 0.3
  dynamic_keywords:
    enabled: true
    learning_top_n: 30
    min_frequency: 4
    ttl_hours: 24
    cache_file: "dynamic_keywords_cache.json"
```

### 기본 설정

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enable_segmentation` | boolean | `true` | 내러티브 세분화 활성화 |
| `crypto_paragraphs` | integer | `2` | Crypto 내러티브 문단 수 |
| `integrated_paragraphs` | integer | `3` | 통합 내러티브 문단 수 |
| `min_category_confidence` | float | `0.5` | 최소 카테고리 신뢰도 (deprecated) |

### 카테고리 임계값 (`category_thresholds`)

2-카테고리 시스템(Macro, Crypto)의 분류 임계값입니다.

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `macro` | float | `0.4` | 거시경제 카테고리 임계값 |
| `crypto` | float | `0.3` | 암호화폐 카테고리 임계값 |

### 동적 키워드 설정 (`dynamic_keywords`)

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | boolean | `true` | 동적 키워드 학습 활성화 |
| `learning_top_n` | integer | `30` | 학습할 상위 키워드 수 |
| `min_frequency` | integer | `4` | 최소 출현 빈도 |
| `ttl_hours` | integer | `24` | 키워드 유효 시간 |
| `cache_file` | string | - | 캐시 파일 경로 |

---

## 9. 출력 설정 (`output`)

출력 및 로깅 설정입니다.

```yaml
output:
  top_keywords_count: 10
  summary_paragraphs: 4
  log_level: INFO
  log_filename_strategy: timestamp
  log_fixed_window_days: 10
  display_timezone: 9
  output_dir: output
```

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `top_keywords_count` | integer | `10` | 출력할 상위 키워드 수 |
| `summary_paragraphs` | integer | `4` | 요약 문단 수 (세분화 비활성화 시) |
| `log_level` | string | `INFO` | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `log_filename_strategy` | string | `timestamp` | 로그 파일명 전략 |
| `log_fixed_window_days` | integer | `10` | 로그 보관 기간 (일) |
| `display_timezone` | integer | `9` | 출력 타임존 (한국=9) |
| `output_dir` | string | `output` | 출력 디렉토리 경로 |

---

## 환경 변수 (`.env`)

민감한 정보는 `.env` 파일에 저장합니다.

```bash
# Google API (Gemini)
GOOGLE_API_KEY=your_google_api_key

# OpenAI API (선택사항)
OPENAI_API_KEY=your_openai_api_key

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

---

*최종 수정일: 2024-12-26*

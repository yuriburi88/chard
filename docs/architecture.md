# CHARD 시스템 아키텍처

## 개요

CHARD (Crypto Hybrid Analysis for Research & Development)는 암호화폐 및 매크로 경제 뉴스를 수집하고 분석하여 트레이딩 인사이트를 생성하는 플랫폼입니다.

## 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CHARD Platform                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │   RSS Feeds  │  │   Telegram   │  │  Economic Calendar       │   │
│  │  (CoinDesk,  │  │  Channels    │  │  (Investing.com)         │   │
│  │  TheBlock..) │  │              │  │                          │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
│         │                 │                       │                  │
│         └─────────────────┼───────────────────────┘                  │
│                           ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Data Collection Layer                       │ │
│  │   src/collectors/                                              │ │
│  │   ├── rss_collector.py                                         │ │
│  │   ├── telegram_collector.py                                    │ │
│  │   └── economic_calendar_collector.py                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                          │
│                           ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Preprocessing Layer                         │ │
│  │   src/preprocessor.py                                          │ │
│  │   src/normalizer.py                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                          │
│                           ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                   Analysis Pipeline (LangGraph)                │ │
│  │   src/workflows/                                               │ │
│  │   ├── langgraph_pipeline.py (오케스트레이션)                     │ │
│  │   ├── nodes/                                                   │ │
│  │   │   ├── collector_node.py (청킹)                              │ │
│  │   │   ├── keyword_extractor_node.py (키워드 추출)                │ │
│  │   │   ├── aggregator_node.py (키워드 통합)                       │ │
│  │   │   └── insight_node.py (인사이트 생성)                        │ │
│  │   └── normalization/                                           │ │
│  │       ├── embedding_cluster.py (임베딩 클러스터링)                │ │
│  │       └── llm_verifier.py (LLM 검증)                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                          │
│                           ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      Report Generation                         │ │
│  │   src/report/report_builder.py                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                           │                                          │
│                           ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                         Storage                                │ │
│  │   src/storage.py → output/YYYY-MM-DD/                          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                        MCP Integration                               │
│   src/mcp/                                                          │
│   ├── server.py (MCP 서버)                                          │
│   ├── tools.py (도구 정의)                                          │
│   └── resources.py (리소스 정의)                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 디렉토리 구조

```
chard/
├── main.py                    # CLI 엔트리포인트
├── run_mcp_server.py          # MCP 서버 실행
├── config/
│   ├── config.yml             # 메인 설정
│   └── .env.example           # 환경변수 템플릿
├── src/
│   ├── config_manager.py      # 설정 관리
│   ├── preprocessor.py        # 전처리
│   ├── normalizer.py          # 정규화
│   ├── storage.py             # 저장소 관리
│   ├── collectors/            # 데이터 수집
│   ├── workflows/             # 분석 파이프라인
│   ├── report/                # 리포트 생성
│   ├── mcp/                   # MCP 서버
│   └── utils/                 # 유틸리티
├── tests/
│   ├── unit/                  # 단위 테스트
│   ├── integration/           # 통합 테스트
│   └── fixtures/              # 테스트 픽스처
├── scripts/
│   ├── verification/          # 검증 스크립트
│   ├── generation/            # 생성 스크립트
│   ├── setup/                 # 설정 스크립트
│   └── examples/              # 예제
├── docs/                      # 문서
├── output/                    # 출력 디렉토리
└── logs/                      # 로그
```

## 데이터 흐름

### 1. 데이터 수집 단계
```
RSS Feeds ──┬──> RSSCollector ────────┬──> Article 객체
            │                         │
Telegram ───┼──> TelegramCollector ───┼──> TelegramMessage 객체
            │                         │
Econ Cal ───┴──> EconCalCollector ────┴──> CollectedItem 객체
                                      │
                                      ▼
                              DataNormalizer
                                      │
                                      ▼
                            Unified Records (dict)
```

### 2. 분석 파이프라인 단계
```
Unified Records
       │
       ▼
┌──────────────┐
│collector_node│ ──> 토큰 제한에 맞게 청킹
└──────┬───────┘
       │
       ▼
┌────────────────────┐
│keyword_extractor   │ ──> 각 청크에서 키워드 추출 (LLM)
│  (병렬 실행)        │
└──────┬─────────────┘
       │
       ▼
┌──────────────┐
│aggregator    │ ──> 키워드 통합, 동의어 그룹화
│  node        │     임베딩 클러스터링, LLM 검증
└──────┬───────┘
       │
       ▼
┌──────────────┐
│insight_node  │ ──> 내러티브 및 트레이딩 인사이트 생성
└──────┬───────┘
       │
       ▼
  Final State
```

### 3. 출력 생성 단계
```
Final State
     │
     ├──> report_builder.py ──> Markdown 리포트
     │
     └──> storage.py ──> JSON 파일 (raw, analysis, report)
                    │
                    ▼
            output/YYYY-MM-DD/
            ├── collected_HHMMSS_raw.json
            ├── analysis_HHMMSS.json
            └── report_HHMMSS.md
```

## 외부 의존성

### LLM 서비스
- **Google Gemini API**: 키워드 추출, 동의어 검증, 인사이트 생성

### 데이터 소스
- **RSS Feeds**: CoinDesk, The Block, Decrypt 등
- **Telegram**: Bot API 또는 MTProto
- **Economic Calendar**: Investing.com (investpy)

### 임베딩 서비스
- **Sentence Transformers**: 키워드 임베딩 (선택적)

## MCP 통합

CHARD는 Model Context Protocol (MCP)을 통해 Claude Desktop과 통합됩니다.

### 사용 가능한 도구
- `collect_rss`: RSS 피드 수집
- `collect_telegram`: Telegram 메시지 수집
- `run_full_analysis`: 전체 파이프라인 실행
- `get_latest_keywords`: 최신 키워드 조회
- `list_rss_feeds`: RSS 피드 목록
- `list_telegram_channels`: Telegram 채널 목록

### 사용 가능한 리소스
- `chard://config`: 설정 파일
- `chard://reports/latest`: 최신 리포트
- `chard://data/latest`: 최신 수집 데이터
- `chard://analysis/latest`: 최신 분석 결과

## 설정

### 환경변수
```bash
GOOGLE_API_KEY=your-gemini-api-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash
```

### 주요 설정 (`config/config.yml`)
```yaml
collection_period:
  mode: days_back  # "days_back" 또는 "fixed_date_range"
  days_back: 1

llm:
  model: gemini-2.5-flash
  provider: google
  max_tokens: 8000

output:
  top_keywords_count: 10
  summary_paragraphs: 4
```

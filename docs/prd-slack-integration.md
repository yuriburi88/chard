# PRD: CHARD Slack 연동

> Slack에서 자연어로 CHARD AI와 대화하며 시장 분석을 요청하는 기능

## 1. Introduction/Overview

CHARD와 Slack을 연동하여, 사용자가 Slack에서 **자연어로 CHARD AI와 대화**하며 시장 분석을 요청하고 결과를 받아볼 수 있는 기능입니다. Claude API를 통해 사용자의 의도를 파악하고, 기존 CHARD MCP 도구를 활용하여 분석을 실행합니다. 정해진 명령어 없이도 "CHARD야 12월 비트코인 뉴스 분석해줘"와 같은 자연스러운 대화가 가능합니다.

### 해결하려는 문제
- 정해진 명령어를 외워야 하는 불편함
- 후속 질문이나 맥락 기반 대화가 불가능한 한계
- 분석 결과에 대한 추가 설명이나 해석을 받기 어려움
- 터미널에 직접 접속하여 `main.py`를 실행해야 하는 번거로움

### 핵심 차별점
| 기존 방식 (명령어) | 새로운 방식 (Claude 연동) |
|-------------------|--------------------------|
| `/chard rss 비트코인` | "비트코인 RSS 뉴스만 분석해줘" |
| 명령어 오타 시 에러 | 자연어 이해로 유연한 처리 |
| 결과만 전달 | 결과 + AI 해석/요약 제공 |
| 후속 질문 불가 | "왜 이게 1위야?" 가능 |
| 맥락 없음 | 대화 히스토리 유지 |

## 2. Goals

| ID | 목표 | 측정 기준 |
|----|------|----------|
| G1 | 자연어로 분석 요청 가능 | 다양한 표현으로 동일 기능 실행 |
| G2 | 대화형 AI 경험 제공 | 후속 질문, 맥락 기반 응답 지원 |
| G3 | MCP 도구 자동 선택 | Claude가 적절한 도구를 판단하여 호출 |
| G4 | 분석 결과 AI 해석 제공 | 단순 데이터 + AI 인사이트 |
| G5 | 파일 첨부 지원 | JSON/MD 파일 자동 첨부 |

## 3. User Stories

### US-1: 자연어 분석 요청
> "트레이더로서, 'CHARD야 오늘 시황 어때?'라고 자연스럽게 물어보면 시장 분석 결과를 받아보고 싶다. 정확한 명령어를 외울 필요 없이."

### US-2: 기간 지정 분석
> "분석가로서, '12월 한 달간 뉴스 분석해줘' 또는 '지난주 비트코인 동향 알려줘'처럼 기간을 자유롭게 지정하고 싶다."

### US-3: 후속 질문
> "트레이더로서, 분석 결과를 받은 후 '왜 비트코인이 1위야?' 또는 '이더리움 관련 뉴스만 더 자세히'라고 추가 질문하고 싶다."

### US-4: 결과 해석 요청
> "신규 사용자로서, 분석 결과가 나오면 'AI야 이게 무슨 뜻이야?' 또는 '투자 관점에서 요약해줘'라고 요청하고 싶다."

### US-5: 소스 선택 분석
> "분석가로서, 'RSS만 분석해줘' 또는 '텔레그램 뉴스만 보여줘'처럼 소스를 지정하고 싶다."

### US-6: 파일 다운로드
> "데이터 분석가로서, Slack에서 JSON 분석 파일을 다운로드하여 추가 분석에 활용하고 싶다."

## 4. Functional Requirements

### 4.1 Slack Bot 서버

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-1.1 | `src/slack/bot_server.py` 모듈 생성 | P0 |
| FR-1.2 | Slack Bot Token을 사용한 인증 구현 | P0 |
| FR-1.3 | Socket Mode를 통한 이벤트 수신 | P0 |
| FR-1.4 | 로컬 PC에서 실행 가능한 상시 대기 서버 | P0 |
| FR-1.5 | 서버 시작/종료 로깅 | P1 |

### 4.2 Claude API 연동

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-2.1 | `src/slack/claude_agent.py` 모듈 생성 | P0 |
| FR-2.2 | Claude API를 통한 자연어 의도 파악 | P0 |
| FR-2.3 | Tool Use 기능으로 MCP 도구 호출 | P0 |
| FR-2.4 | 대화 히스토리 관리 (채널/스레드별) | P0 |
| FR-2.5 | 시스템 프롬프트로 CHARD 역할 정의 | P0 |
| FR-2.6 | 스트리밍 응답 지원 (선택적) | P2 |

### 4.3 MCP 도구 정의 (Claude Tool Use)

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-3.1 | `run_analysis` - 전체 분석 실행 | P0 |
| FR-3.2 | `run_analysis_filtered` - 소스/키워드 필터 분석 | P0 |
| FR-3.3 | `get_latest_report` - 최근 분석 결과 조회 | P0 |
| FR-3.4 | `get_latest_keywords` - 최근 키워드 조회 | P0 |
| FR-3.5 | `list_available_sources` - 사용 가능한 소스 목록 | P1 |
| FR-3.6 | `get_report_by_date` - 특정 날짜 리포트 조회 | P1 |

### 4.4 자연어 처리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-4.1 | 다양한 분석 요청 표현 인식 | P0 |
| FR-4.2 | 기간 표현 파싱 (오늘, 이번주, 12월, 지난달 등) | P0 |
| FR-4.3 | 소스 지정 표현 인식 (RSS, 텔레그램, 뉴스 등) | P0 |
| FR-4.4 | 키워드 추출 (비트코인, 이더리움, 금리 등) | P0 |
| FR-4.5 | 후속 질문 맥락 연결 | P0 |
| FR-4.6 | 모호한 요청 시 명확화 질문 | P1 |

### 4.5 응답 생성

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-5.1 | 분석 시작 시 "분석 중..." 즉시 응답 | P0 |
| FR-5.2 | 분석 결과 + AI 해석 응답 | P0 |
| FR-5.3 | Slack Block Kit 형식으로 구조화 | P1 |
| FR-5.4 | 자연스러운 한국어 응답 | P0 |
| FR-5.5 | 이모지 및 포맷팅 활용 | P1 |

### 4.6 파일 첨부

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-6.1 | `*_summary.json` 파일 첨부 | P0 |
| FR-6.2 | `*_summary.md` 파일 첨부 | P0 |
| FR-6.3 | 파일 업로드 실패 시 재시도 (최대 3회) | P1 |

### 4.7 에러 처리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-7.1 | 파이프라인 실패 시 친절한 에러 메시지 | P0 |
| FR-7.2 | Claude API 에러 시 폴백 응답 | P0 |
| FR-7.3 | 이해 못한 요청 시 안내 메시지 | P0 |
| FR-7.4 | 에러 발생 시 로그 파일 첨부 (선택적) | P1 |

### 4.8 설정 관리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-8.1 | `config/slack.yml` 설정 파일 생성 | P0 |
| FR-8.2 | Slack Bot Token `.env`에서 로드 | P0 |
| FR-8.3 | Slack App Token `.env`에서 로드 | P0 |
| FR-8.4 | Claude API Key `.env`에서 로드 | P0 |
| FR-8.5 | 대화 히스토리 최대 길이 설정 | P1 |
| FR-8.6 | Claude 모델 선택 설정 | P1 |

## 5. Non-Goals (Out of Scope)

| 항목 | 이유 |
|------|------|
| 예약 분석 (스케줄링) | Phase 2에서 구현 예정 |
| 다중 채널 동시 전송 | 요청 채널에만 응답 |
| 음성 메시지 인식 | 복잡도 증가 |
| 이미지/차트 생성 | 1차에서는 텍스트 + 파일만 |
| 사용자별 개인화 설정 | 향후 고려 |
| 클라우드 서버 배포 | 로컬 PC 실행 기준 |

## 6. Design Considerations

### 6.1 대화 예시

```
[사용자] @CHARD 오늘 시황 어때?
    │
    ▼
[CHARD] 안녕하세요! 오늘의 시장 분석을 시작할게요. 잠시만 기다려주세요... ⏳
    │
    ▼ (Claude가 run_analysis 도구 호출)
    │
[CHARD] 📊 2025년 12월 29일 시장 분석 결과입니다.

        🔑 오늘의 핵심 키워드
        1. 비트코인 (1,122점) - ETF 관련 뉴스 급증
        2. S&P500 (129점) - 연말 랠리 기대감
        3. GDP (117점) - 4분기 성장률 전망

        📈 시장 심리: 중립 (신뢰도 65%)
        📉 변동성: 증가 예상 (신뢰도 78%)

        💡 AI 해석
        비트코인 ETF 관련 뉴스가 가장 많이 언급되고 있어요.
        특히 순유출 관련 우려가 있지만, 장기적으로는...

        [JSON 파일] [MD 파일]
```

```
[사용자] 왜 비트코인이 1위야?
    │
    ▼ (맥락 유지 - 이전 대화 참조)
    │
[CHARD] 비트코인이 1위인 이유를 분석해볼게요.

        오늘 수집된 255개 뉴스 중 29개(11.4%)가 비트코인을
        직접 언급했어요. 주요 원인은:

        1. 비트코인 ETF 순유출 3일 연속 - 투자자 우려
        2. 연말 세금 매도 압력
        3. 기관 투자자 포지션 조정

        관련 뉴스를 더 자세히 보여드릴까요?
```

```
[사용자] 12월 한 달간 RSS만 분석해줘
    │
    ▼
[CHARD] 12월 1일부터 29일까지 RSS 뉴스만 분석할게요.
        데이터가 많아서 2-3분 정도 걸릴 수 있어요... ⏳
    │
    ▼ (Claude가 run_analysis_filtered 도구 호출)
    │
[CHARD] 📊 12월 RSS 뉴스 분석 완료!

        총 1,847개 기사 분석 (RSS만)
        ...
```

### 6.2 시스템 프롬프트

```
You are CHARD, a cryptocurrency and macro-economic news analysis assistant.
You help users analyze market news and provide trading insights.

Your capabilities (via tools):
- run_analysis: Run full analysis on recent news
- run_analysis_filtered: Run analysis with source/keyword/period filters
- get_latest_report: Get the most recent analysis report
- get_latest_keywords: Get trending keywords

Guidelines:
- Respond in Korean, friendly but professional tone
- When user asks for analysis, use appropriate tools
- Provide AI interpretation along with raw data
- If request is ambiguous, ask clarifying questions
- Remember conversation context for follow-up questions
- Use emojis sparingly to enhance readability
```

### 6.3 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                         Slack                                │
│    사용자: "@CHARD 12월 비트코인 뉴스 분석해줘"               │
└───────────────────────────┬─────────────────────────────────┘
                            │ Socket Mode
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Slack Bot Server                           │
│                 (src/slack/bot_server.py)                    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Claude Agent                            │    │
│  │           (src/slack/claude_agent.py)               │    │
│  │                                                      │    │
│  │  ┌────────────────────────────────────────────┐     │    │
│  │  │           Claude API (Tool Use)            │     │    │
│  │  │                                            │     │    │
│  │  │  1. 자연어 의도 파악                        │     │    │
│  │  │  2. 적절한 도구 선택                        │     │    │
│  │  │  3. 결과 해석 및 응답 생성                  │     │    │
│  │  └───────────────────┬────────────────────────┘     │    │
│  │                      │ Tool Call                     │    │
│  │                      ▼                               │    │
│  │  ┌────────────────────────────────────────────┐     │    │
│  │  │           CHARD Tools                      │     │    │
│  │  │        (MCP 도구 래퍼)                     │     │    │
│  │  │                                            │     │    │
│  │  │  • run_analysis()                          │     │    │
│  │  │  • run_analysis_filtered()                 │     │    │
│  │  │  • get_latest_report()                     │     │    │
│  │  │  • get_latest_keywords()                   │     │    │
│  │  └───────────────────┬────────────────────────┘     │    │
│  │                      │                               │    │
│  └──────────────────────┼───────────────────────────────┘    │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHARD Pipeline                             │
│              (src/workflows/langgraph_pipeline.py)           │
│                                                              │
│   수집 → 전처리 → 키워드 추출 → 통합 → 인사이트 생성          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Output                                  │
│               output/YYYY-MM-DD/                             │
│                                                              │
│   • analysis_*.json                                          │
│   • report_*.md                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 설정 파일 구조 (`config/slack.yml`)

```yaml
slack:
  enabled: true

  # Socket Mode 설정 (로컬 실행용)
  socket_mode: true

  # 허용된 채널 (비어있으면 모든 채널)
  allowed_channels: []

# Claude 설정
claude:
  model: "claude-sonnet-4-20250514"  # 또는 claude-3-haiku-20240307 (비용 절약)
  max_tokens: 4096
  temperature: 0.7

  # 대화 히스토리 설정
  conversation:
    max_history: 10           # 최대 대화 턴 수
    timeout_minutes: 30       # 대화 세션 타임아웃

# 분석 설정
analysis:
  timeout_seconds: 300        # 분석 타임아웃 (5분)
  max_queue_size: 5           # 대기열 최대 크기

# 응답 설정
response:
  include_files: true         # 파일 첨부 여부
  include_json: true          # JSON 파일 첨부
  include_markdown: true      # MD 파일 첨부

# 에러 알림
error:
  include_log: true           # 에러 시 로그 파일 첨부
```

### 6.5 환경변수 (`.env`)

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# 기존 CHARD 설정
GOOGLE_API_KEY=your-gemini-api-key
```

## 7. Technical Considerations

### 7.1 의존성
```
# 기존
slack-sdk>=3.0.0
slack-bolt>=1.18.0
aiohttp

# 추가
anthropic>=0.18.0    # Claude API 클라이언트
```

### 7.2 디렉토리 구조
```
src/
└── slack/
    ├── __init__.py
    ├── bot_server.py       # Slack Bot 서버 (메인)
    ├── claude_agent.py     # Claude API 연동 및 Tool Use
    ├── tools.py            # CHARD 도구 정의 (Claude용)
    ├── message_formatter.py # Slack 메시지 포맷터
    └── conversation.py     # 대화 히스토리 관리
config/
└── slack.yml              # Slack + Claude 설정
```

### 7.3 Claude Tool Use 정의 예시

```python
tools = [
    {
        "name": "run_analysis",
        "description": "Run full market analysis on recent news from all sources",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 1)",
                    "default": 1
                }
            }
        }
    },
    {
        "name": "run_analysis_filtered",
        "description": "Run market analysis with filters",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["rss", "telegram", "all"],
                    "description": "Data source to analyze"
                },
                "keyword": {
                    "type": "string",
                    "description": "Keyword to filter news (e.g., 'bitcoin', 'ethereum')"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to analyze"
                }
            }
        }
    },
    {
        "name": "get_latest_report",
        "description": "Get the most recent analysis report",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_latest_keywords",
        "description": "Get the top trending keywords from the latest analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of keywords to return",
                    "default": 10
                }
            }
        }
    }
]
```

### 7.4 비용 예상

| 모델 | 입력 | 출력 | 대화당 예상 비용 |
|------|------|------|-----------------|
| Claude Sonnet | $3/1M | $15/1M | ~$0.02-0.05 |
| Claude Haiku | $0.25/1M | $1.25/1M | ~$0.002-0.005 |

**추천**:
- 개발/테스트: Haiku (저렴)
- 프로덕션: Sonnet (품질)

### 7.5 Socket Mode 사용 이유
- **공인 IP/도메인 불필요**: 로컬 PC에서 실행 가능
- **방화벽 설정 불필요**: 아웃바운드 연결만 사용
- **ngrok 등 터널링 불필요**: Slack이 직접 푸시

### 7.6 에러 처리 전략
- Claude API 타임아웃 시 재시도 (최대 3회)
- 분석 실패 시 친절한 에러 메시지 + 재시도 안내
- Rate Limit 시 대기 후 재시도

### 7.7 보안 고려사항
- 모든 API Key는 `.env`에만 저장 (git 제외)
- 대화 히스토리에 민감 정보 저장 금지
- 허용된 채널에서만 응답 (선택적)

## 8. Success Metrics

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 자연어 이해율 | 90% 이상 | 의도 파악 성공/전체 요청 |
| 응답 지연 시간 | 3초 이내 | 요청 ~ 첫 응답 (분석 중) |
| 분석 완료 시간 | 2분 이내 | 요청 ~ 결과 수신 |
| 대화 만족도 | 80% 이상 | 사용자 피드백 |
| 후속 질문 처리율 | 85% 이상 | 맥락 연결 성공률 |

## 9. Open Questions

| # | 질문 | 상태 | 결정 |
|---|------|------|------|
| 1 | Claude 모델 선택 (Sonnet vs Haiku)? | ✅ 해결 | Sonnet 4 사용 (`claude-sonnet-4-20250514`) |
| 2 | 대화 히스토리 저장 방식 (메모리 vs 파일)? | ✅ 해결 | 메모리 (채널/스레드별 `ConversationManager`) |
| 3 | 메시지 길이 Slack 제한(4000자) 초과 시? | ✅ 해결 | 3000자 초과 시 잘라서 표시 + 파일 첨부 |
| 4 | 동시 요청 처리 방식? | ✅ 해결 | 채널별 큐잉 (`MAX_QUEUE_SIZE=10`) |
| 5 | PC 꺼지면 서비스 중단 수용? | ✅ 해결 | 1차는 수용 (Phase 2에서 클라우드 배포 검토) |

## 10. Implementation Phases

### Phase 1: Claude 연동 Slack Bot (이번 PRD 범위)
1. Slack Bot 서버 개발 (Socket Mode)
2. Claude API 연동 (Tool Use)
3. CHARD 도구 정의 및 구현
4. 대화 히스토리 관리
5. 메시지 포맷터 및 파일 첨부
6. 설정 파일 구조

### Phase 2: 스케줄러 연동 (다음 PRD)
- 매일 아침 9시 자동 분석
- Windows Task Scheduler 연동
- 실행 결과 자동 전송
- 클라우드 서버 배포 옵션

---

*생성일: 2025-12-26*
*수정일: 2025-12-29*
*버전: 3.0*

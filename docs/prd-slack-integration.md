# PRD: CHARD Slack 연동

> 분석 결과를 Slack 메신저로 자동 전송하는 기능

## 1. Introduction/Overview

CHARD 파이프라인 실행 완료 후 분석 결과를 Slack 채널로 자동 전송하는 기능입니다. 사용자가 `main.py`를 실행할 때마다 분석 리포트가 Slack으로 전달되어, 팀원들이 실시간으로 시장 인사이트를 확인할 수 있습니다.

### 해결하려는 문제
- 분석 완료 후 수동으로 결과를 확인하고 공유해야 하는 번거로움
- 팀원들이 output 폴더에 직접 접근해야 하는 불편함
- 분석 실패 시 즉각적인 알림 부재

## 2. Goals

| ID | 목표 | 측정 기준 |
|----|------|----------|
| G1 | 분석 완료 시 자동 Slack 알림 | main.py 실행 완료 후 30초 이내 Slack 메시지 수신 |
| G2 | 리포트 전문 + 파일 첨부 전송 | 마크다운 요약 + JSON/MD 파일 첨부 |
| G3 | 실패 시 에러 알림 | 에러 메시지 + 로그 파일 첨부 |
| G4 | 설정 기반 유연한 구성 | 별도 설정 파일로 on/off 및 채널 지정 가능 |

## 3. User Stories

### US-1: 분석 결과 자동 수신
> "트레이더로서, main.py 실행 후 Slack에서 바로 시장 분석 결과를 받아보고 싶다. 그래야 별도로 서버에 접속하지 않아도 된다."

### US-2: 파일 다운로드
> "데이터 분석가로서, Slack에서 JSON 분석 파일을 다운로드하여 추가 분석에 활용하고 싶다."

### US-3: 실패 알림 수신
> "시스템 관리자로서, 파이프라인 실패 시 즉시 알림을 받아 문제를 빠르게 파악하고 싶다."

### US-4: 알림 설정 관리
> "운영자로서, Slack 알림을 켜고 끄거나 채널을 변경할 수 있어야 한다."

## 4. Functional Requirements

### 4.1 Slack 클라이언트 모듈

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-1.1 | `src/notifications/slack_notifier.py` 모듈 생성 | P0 |
| FR-1.2 | Slack Bot Token을 사용한 인증 구현 | P0 |
| FR-1.3 | 텍스트 메시지 전송 기능 (`chat.postMessage`) | P0 |
| FR-1.4 | 파일 업로드 기능 (`files.upload`) | P0 |
| FR-1.5 | 비동기(async) API 호출 지원 | P1 |

### 4.2 메시지 포맷

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-2.1 | 전체 마크다운 리포트를 Slack 메시지로 변환 | P0 |
| FR-2.2 | Slack Block Kit 형식으로 구조화된 메시지 생성 | P1 |
| FR-2.3 | 상위 키워드 테이블 포함 | P0 |
| FR-2.4 | 시장 심리 (방향성, 변동성) 표시 | P0 |
| FR-2.5 | 거래 인사이트 (기회/위험) 포함 | P0 |

### 4.3 파일 첨부

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-3.1 | `*_summary.json` 파일 첨부 | P0 |
| FR-3.2 | `*_summary.md` 파일 첨부 | P0 |
| FR-3.3 | 파일 업로드 실패 시 재시도 (최대 3회) | P1 |

### 4.4 에러 처리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-4.1 | 파이프라인 실패 시 에러 메시지 전송 | P0 |
| FR-4.2 | 에러 발생 시 로그 파일 (`execution_*.log`) 첨부 | P0 |
| FR-4.3 | 에러 유형별 아이콘/색상 구분 | P2 |

### 4.5 설정 관리

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-5.1 | `config/slack.yml` 설정 파일 생성 | P0 |
| FR-5.2 | Slack 알림 활성화/비활성화 옵션 (`enabled: true/false`) | P0 |
| FR-5.3 | 대상 채널 설정 (`channel_id`) | P0 |
| FR-5.4 | Bot Token은 `.env`에서 로드 (`SLACK_BOT_TOKEN`) | P0 |
| FR-5.5 | 성공/실패 알림 개별 on/off 설정 | P1 |

### 4.6 main.py 통합

| ID | 요구사항 | 우선순위 |
|----|----------|----------|
| FR-6.1 | 파이프라인 완료 후 Slack 알림 자동 호출 | P0 |
| FR-6.2 | `--no-slack` CLI 옵션으로 알림 비활성화 | P1 |
| FR-6.3 | Slack 전송 실패가 전체 파이프라인을 중단시키지 않음 | P0 |

## 5. Non-Goals (Out of Scope)

| 항목 | 이유 |
|------|------|
| Slack 명령어(슬래시 커맨드) 지원 | 2차 개발 범위 (배치 스케줄러와 함께) |
| 양방향 대화 (Slack → CHARD) | 복잡도 증가, 향후 고려 |
| 다중 채널 동시 전송 | 1차에서는 단일 채널만 지원 |
| Webhook 방식 지원 | Bot Token으로 통일 (파일 업로드 필요) |
| 메시지 스레드/리액션 관리 | 1차에서는 단순 전송만 |

## 6. Design Considerations

### 6.1 Slack 메시지 구조 (예시)

```
📊 CHARD 시장 분석 리포트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 분석 시간: 2025-12-26 09:00 KST
📈 데이터: RSS 255건, Telegram 120건

🔑 상위 키워드
┌────┬─────────────┬────────┬────────┐
│ # │ 키워드      │ 점수   │ 출현   │
├────┼─────────────┼────────┼────────┤
│ 1  │ 비트코인   │ 1122.5 │ 29회   │
│ 2  │ S&P500     │ 129.4  │ 2회    │
│ 3  │ GDP        │ 116.9  │ 2회    │
└────┴─────────────┴────────┴────────┘

📊 시장 심리
• 방향성: 중립 (신뢰도 65%)
• 변동성: 증가 (신뢰도 78%)

💡 거래 인사이트
[기회] 스테이블코인 시장 성장...
[위험] 비트코인 ETF 순유출...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 품질 점수: 85.7% (Very Good)
```

### 6.2 설정 파일 구조 (`config/slack.yml`)

```yaml
slack:
  enabled: true
  channel_id: "C0123456789"  # Slack 채널 ID

  notifications:
    on_success: true         # 성공 시 알림
    on_failure: true         # 실패 시 알림

  attachments:
    include_json: true       # JSON 파일 첨부
    include_markdown: true   # MD 파일 첨부
    include_log_on_error: true  # 에러 시 로그 첨부

  message:
    include_full_report: true   # 전체 리포트 포함
    max_keywords: 5             # 표시할 최대 키워드 수
```

### 6.3 환경변수 (`.env`)

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
```

## 7. Technical Considerations

### 7.1 의존성
- `slack-sdk>=3.0.0` - Slack API 클라이언트
- `aiohttp` - 비동기 HTTP (이미 설치됨)

### 7.2 디렉토리 구조
```
src/
└── notifications/
    ├── __init__.py
    ├── slack_notifier.py    # Slack 알림 클래스
    └── message_formatter.py # 메시지 포맷터
config/
└── slack.yml               # Slack 설정
```

### 7.3 에러 처리 전략
- Slack API 호출 실패 시 로깅 후 계속 진행 (파이프라인 중단 X)
- 재시도 로직: 지수 백오프 (1초, 2초, 4초)
- Rate Limit 처리: `retry_after` 헤더 존중

### 7.4 보안 고려사항
- Bot Token은 `.env`에만 저장 (git에 포함 X)
- 채널 ID는 설정 파일에 저장 (민감하지 않음)

## 8. Success Metrics

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 알림 성공률 | 99% 이상 | Slack 전송 성공/시도 비율 |
| 전송 지연 시간 | 30초 이내 | 파이프라인 완료 ~ Slack 수신 |
| 파일 첨부 성공률 | 95% 이상 | 파일 업로드 성공/시도 비율 |

## 9. Open Questions

| # | 질문 | 상태 |
|---|------|------|
| 1 | Slack 워크스페이스/채널은 이미 생성되어 있는가? | 확인 필요 |
| 2 | Bot Token 생성 권한이 있는가? | 확인 필요 |
| 3 | 메시지 길이가 Slack 제한(4000자)을 초과할 경우 분할 전송할 것인가? | 결정 필요 |

## 10. Implementation Phases

### Phase 1: 기본 구현 (이번 PRD 범위)
- Slack 클라이언트 모듈 개발
- 메시지 포맷터 구현
- main.py 통합
- 설정 파일 구조

### Phase 2: 스케줄러 연동 (다음 PRD)
- 매일 아침 9시 배치 실행
- cron 또는 Windows Task Scheduler 연동
- 실행 결과 모니터링

---

*생성일: 2025-12-26*
*버전: 1.0*

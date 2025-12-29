# Tasks: CHARD Slack + Claude MCP 연동

> PRD 기반: `docs/prd-slack-integration.md` (v3.0)

## Relevant Files

### 신규 생성
- `src/slack/__init__.py` - Slack 모듈 패키지 초기화
- `src/slack/bot_server.py` - Slack Bot 서버 메인 (Socket Mode)
- `src/slack/claude_agent.py` - Claude API 연동 및 Tool Use 처리
- `src/slack/tools.py` - CHARD 도구 정의 (Claude용 Tool Schema)
- `src/slack/message_formatter.py` - Slack 메시지 포맷터 (Block Kit 지원)
- `src/slack/file_uploader.py` - Slack 파일 업로더 (재시도 로직 포함)
- `src/slack/conversation.py` - 대화 히스토리 관리
- `src/slack/config.py` - Slack 설정 로더
- `config/slack.yml` - Slack + Claude 설정 파일
- `run_slack_bot.py` - Slack Bot 실행 스크립트
- `tests/unit/slack/__init__.py` - Slack 테스트 패키지
- `tests/unit/slack/test_claude_agent.py` - Claude Agent 테스트
- `tests/unit/slack/test_tools.py` - 도구 정의 테스트
- `tests/unit/slack/test_conversation.py` - 대화 히스토리 테스트

### 수정 필요
- `requirements.txt` - slack-sdk, slack-bolt, anthropic 추가
- `config/.env.example` - SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY 추가
- `.gitignore` - Slack 관련 임시 파일 제외 (필요시)

### Notes

- 테스트는 `tests/unit/slack/` 디렉토리에 배치
- `pytest tests/unit/slack/` 로 Slack 관련 테스트만 실행 가능
- Socket Mode는 공인 IP 없이 로컬에서 실행 가능
- Claude API 호출은 비동기로 처리하여 Slack 응답 지연 방지

## Instructions for Completing Tasks

**IMPORTANT:** 각 태스크 완료 시 `- [ ]`를 `- [x]`로 변경하여 진행 상황을 추적하세요.

예시:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (완료 후)

서브태스크 완료 시마다 파일을 업데이트하세요.

## Tasks

- [x] 0.0 피처 브랜치 생성
  - [x] 0.1 새 브랜치 생성 및 체크아웃 (`git checkout -b feature/slack-mcp-integration`)

- [x] 1.0 개발 환경 설정
  - [x] 1.1 `requirements.txt`에 의존성 추가
    - `slack-sdk>=3.0.0`
    - `slack-bolt>=1.18.0`
    - `anthropic>=0.18.0`
  - [x] 1.2 `config/.env.example` 업데이트
    - `SLACK_BOT_TOKEN=xoxb-your-bot-token`
    - `SLACK_APP_TOKEN=xapp-your-app-token`
    - `ANTHROPIC_API_KEY=sk-ant-your-api-key`
  - [x] 1.3 로컬 `.env` 파일에 실제 토큰 설정
  - [x] 1.4 `pip install -r requirements.txt` 실행하여 의존성 설치

- [x] 2.0 Slack 모듈 기본 구조 생성
  - [x] 2.1 `src/slack/__init__.py` 생성
  - [x] 2.2 `src/slack/bot_server.py` 기본 구조 작성
    - Slack Bolt App 초기화
    - Socket Mode 설정
    - 기본 이벤트 핸들러 (app_mention, message)
  - [x] 2.3 `run_slack_bot.py` 실행 스크립트 생성
  - [x] 2.4 기본 연결 테스트 (Bot이 Slack에 연결되는지 확인)

- [x] 3.0 설정 파일 구조 구현
  - [x] 3.1 `config/slack.yml` 생성
    - slack 설정 (enabled, socket_mode, allowed_channels)
    - claude 설정 (model, max_tokens, temperature, conversation)
    - analysis 설정 (timeout_seconds, max_queue_size)
    - response 설정 (include_files, include_json, include_markdown)
  - [x] 3.2 `src/slack/config.py` 설정 로더 구현 (선택적)
  - [x] 3.3 환경변수 로딩 검증

- [x] 4.0 Claude Agent 구현
  - [x] 4.1 `src/slack/claude_agent.py` 생성
    - Anthropic 클라이언트 초기화
    - 시스템 프롬프트 정의 (CHARD 역할)
    - `process_message()` 메서드 구현
  - [x] 4.2 Tool Use 처리 로직 구현
    - 도구 호출 감지
    - 도구 실행 결과 반환
    - 멀티턴 도구 호출 지원
  - [x] 4.3 에러 처리 및 폴백 응답 구현
    - RateLimitError, APIConnectionError, APIError 처리
    - 최대 Tool Use 반복 횟수 제한 (5회)
    - 에러 메시지 한국어화
  - [x] 4.4 `tests/unit/slack/test_claude_agent.py` 작성 (17개 테스트)

- [x] 5.0 CHARD 도구 정의 및 구현
  - [x] 5.1 `src/slack/tools.py` 생성
    - Tool Schema 정의 (Claude Tool Use 형식)
    - `run_analysis` - 전체 분석 실행
    - `run_analysis_filtered` - 필터 분석 (소스/키워드/기간)
    - `get_latest_report` - 최근 리포트 조회
    - `get_latest_keywords` - 최근 키워드 조회
    - `list_available_sources` - 소스 목록 조회
  - [x] 5.2 각 도구의 실행 함수 구현
    - 기존 CHARD 파이프라인 호출
    - 결과 JSON 파싱 및 반환
  - [x] 5.3 도구 실행 타임아웃 처리
    - 도구별 타임아웃 설정 (run_analysis: 5분, get_latest_*: 30초)
    - `with_timeout()` 헬퍼 함수 구현
  - [x] 5.4 `tests/unit/slack/test_tools.py` 작성 (18개 테스트)

- [x] 6.0 대화 히스토리 관리
  - [x] 6.1 `src/slack/conversation.py` 생성
    - 채널/스레드별 히스토리 저장
    - 최대 히스토리 길이 관리
    - 세션 타임아웃 처리
  - [x] 6.2 히스토리 추가/조회/삭제 메서드 구현
  - [x] 6.3 Claude API 호출 시 히스토리 포함
    - `bot_server.py`에서 `get_history()` → Claude → `update_history()` 플로우 구현
  - [x] 6.4 `tests/unit/slack/test_conversation.py` 작성 (20개 테스트)

- [x] 7.0 메시지 포맷터 구현
  - [x] 7.1 `src/slack/message_formatter.py` 생성
  - [x] 7.2 분석 결과 → Slack 메시지 변환
    - 키워드 테이블 포맷팅
    - 시장 심리 표시
    - 인사이트 섹션
  - [x] 7.3 에러 메시지 포맷팅
  - [x] 7.4 "분석 중..." 로딩 메시지
  - [x] 7.5 Slack Block Kit 형식 적용 (선택적)

- [x] 8.0 파일 첨부 기능
  - [x] 8.1 분석 완료 후 JSON 파일 업로드 구현
  - [x] 8.2 MD 파일 업로드 구현
  - [x] 8.3 업로드 실패 시 재시도 로직 (최대 3회)
  - [x] 8.4 에러 시 로그 파일 첨부 (선택적)

- [x] 9.0 Bot Server 통합
  - [x] 9.1 `bot_server.py`에 Claude Agent 통합
  - [x] 9.2 `app_mention` 이벤트 핸들러 구현
    - 메시지 수신 → Claude Agent → 응답 전송
  - [x] 9.3 DM 메시지 핸들러 구현 (선택적)
  - [x] 9.4 "분석 중..." 즉시 응답 후 결과 후속 전송
  - [x] 9.5 동시 요청 큐잉 처리

- [ ] 10.0 통합 테스트 (수동 테스트 - Slack 연결 필요)
  - [ ] 10.1 Slack에서 `@CHARD 시황 알려줘` 테스트
  - [ ] 10.2 소스 필터 테스트 (`RSS만 분석해줘`)
  - [ ] 10.3 키워드 필터 테스트 (`비트코인 분석해줘`)
  - [ ] 10.4 후속 질문 테스트 (`왜 이게 1위야?`)
  - [ ] 10.5 파일 첨부 확인
  - [ ] 10.6 에러 케이스 테스트 (잘못된 요청, 타임아웃)

- [x] 11.0 문서화 및 마무리
  - [x] 11.1 `docs/prd-slack-integration.md` Open Questions 업데이트
  - [x] 11.2 README에 Slack Bot 실행 방법 추가
  - [x] 11.3 `config/slack.yml` 주석 보강
  - [x] 11.4 Git 커밋 완료 (PR은 사용자가 원격 저장소로 push 후 생성)

---

*생성일: 2025-12-29*
*PRD 버전: 3.0*

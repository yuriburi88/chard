# Tasks: CHARD 프로젝트 코드 체계 정리

> 이 태스크 목록은 [prd-code-restructuring.md](./prd-code-restructuring.md)를 기반으로 생성되었습니다.

## Relevant Files

### 설정 파일
- `pyproject.toml` - 프로젝트 설정, linter/formatter 설정 (새로 생성)
- `config/config.yml` - 설정 파일 (이동)
- `config/.env.example` - 환경변수 예제 (새로 생성)
- `requirements.txt` - 프로덕션 의존성
- `requirements-dev.txt` - 개발 의존성 (새로 생성)
- `requirements-test.txt` - 테스트 의존성 (새로 생성)

### 문서 파일
- `docs/architecture.md` - 프로젝트 아키텍처 문서 (새로 생성)
- `docs/coding-conventions.md` - 코딩 컨벤션 가이드 (새로 생성)
- `docs/config-reference.md` - 설정 파일 레퍼런스 (새로 생성)
- `docs/api-reference.md` - API 문서 (새로 생성)
- `CONTRIBUTING.md` - 기여 가이드 (새로 생성)
- `src/collectors/README.md` - collectors 모듈 문서 (새로 생성)
- `src/workflows/README.md` - workflows 모듈 문서 (새로 생성)
- `src/report/README.md` - report 모듈 문서 (새로 생성)

### 소스 코드
- `src/collectors/base.py` - collector 기본 인터페이스 (새로 생성)
- `src/collectors/rss_collector.py` - RSS 수집기
- `src/collectors/telegram_collector.py` - Telegram 수집기
- `src/collectors/economic_calendar_collector.py` - 경제 캘린더 수집기
- `src/mcp/` - MCP 서버 모듈 (`chard_mcp/`에서 이동)
- `src/utils/` - 공통 유틸리티 (새로 생성)
- `scripts/verification/` - 검증 스크립트 (재정리)
- `scripts/setup/` - 설정 스크립트 (재정리)

### 테스트 파일
- `tests/conftest.py` - pytest 설정 및 공통 fixture
- `tests/fixtures/` - 테스트 데이터 (새로 생성)
- `tests/unit/collectors/test_rss_collector.py` - RSS 수집기 테스트
- `tests/unit/collectors/test_telegram_collector.py` - Telegram 수집기 테스트
- `tests/unit/collectors/test_economic_calendar_collector.py` - 경제 캘린더 테스트
- `tests/unit/workflows/test_nodes.py` - workflow 노드 테스트
- `tests/integration/test_pipeline.py` - 통합 테스트 (새로 생성)

### Notes

- 테스트 실행: `pytest` 또는 `pytest tests/unit/` (단위 테스트만)
- 코드 포맷팅: `black .` 또는 `ruff format .`
- 린팅: `ruff check .`
- 타입 체크: `mypy src/`

---

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

---

## Tasks

### Phase 0: 준비

- [x] **0.0 Create feature branch**
  - [x] 0.1 Create and checkout a new branch: `git checkout -b feature/code-restructuring`
  - [x] 0.2 현재 프로젝트 상태 백업 확인 (모든 변경사항 커밋 또는 스태시)

---

### Phase 1: 개발 환경 및 도구 설정

- [x] **1.0 개발 환경 및 도구 설정**
  - [x] 1.1 `pyproject.toml` 파일 생성 (프로젝트 메타데이터 정의)
  - [x] 1.2 Black 설정 추가 (`pyproject.toml` - line-length: 88)
  - [x] 1.3 Ruff 설정 추가 (`pyproject.toml` - linting rules)
  - [x] 1.4 isort 설정 추가 (`pyproject.toml` - import 정렬)
  - [x] 1.5 pytest 설정 추가 (`pyproject.toml` - test configuration)
  - [x] 1.6 `requirements-dev.txt` 생성 (black, ruff, isort, mypy, pre-commit)
  - [x] 1.7 `requirements-test.txt` 생성 (pytest, pytest-cov, pytest-asyncio)
  - [x] 1.8 `.pre-commit-config.yaml` 생성 (Git hooks 설정)
  - [x] 1.9 개발 도구 설치 테스트 (`pip install -r requirements-dev.txt`)

---

### Phase 2: 가이드라인 문서 작성

- [ ] **2.0 가이드라인 문서 작성**
  - [ ] 2.1 `docs/coding-conventions.md` 작성 (PEP 8 기반 코딩 스타일 가이드)
    - [ ] 2.1.1 네이밍 컨벤션 정의 (변수, 함수, 클래스, 파일명)
    - [ ] 2.1.2 Import 순서 및 구조 표준화 규칙
    - [ ] 2.1.3 Type Hints 사용 가이드
    - [ ] 2.1.4 Docstring 작성 가이드 (Google 스타일)
  - [ ] 2.2 `CONTRIBUTING.md` 작성 (기여 가이드)
    - [ ] 2.2.1 개발 환경 설정 방법
    - [ ] 2.2.2 Git 브랜치 전략 (feature, bugfix, release)
    - [ ] 2.2.3 Pull Request 작성 가이드
    - [ ] 2.2.4 코드 리뷰 체크리스트
  - [ ] 2.3 `docs/config-reference.md` 작성 (config.yml 각 항목 설명)

---

### Phase 3: 테스트 인프라 구축

- [ ] **3.0 테스트 인프라 구축 및 기존 기능 테스트 작성**
  - [ ] 3.1 `tests/` 디렉토리 구조 재정리
    - [ ] 3.1.1 `tests/unit/` 디렉토리 생성
    - [ ] 3.1.2 `tests/unit/collectors/` 디렉토리 생성
    - [ ] 3.1.3 `tests/unit/workflows/` 디렉토리 생성
    - [ ] 3.1.4 `tests/unit/report/` 디렉토리 생성
    - [ ] 3.1.5 `tests/integration/` 디렉토리 생성
    - [ ] 3.1.6 `tests/fixtures/` 디렉토리 생성
  - [ ] 3.2 기존 테스트 파일 이동
    - [ ] 3.2.1 `tests/test_*.py` → `tests/unit/` 적절한 위치로 이동
    - [ ] 3.2.2 `tests/collectors/` → `tests/unit/collectors/`로 이동
    - [ ] 3.2.3 `tests/workflows/` → `tests/unit/workflows/`로 이동
  - [ ] 3.3 루트의 테스트 파일 이동
    - [ ] 3.3.1 `test_economic_calendar.py` → `tests/unit/collectors/`로 이동
    - [ ] 3.3.2 `test_mcp.py` → `tests/unit/mcp/`로 이동
  - [ ] 3.4 테스트 fixture 및 mock 데이터 정리
    - [ ] 3.4.1 `tests/fixtures/sample_rss_data.json` 생성
    - [ ] 3.4.2 `tests/fixtures/sample_telegram_data.json` 생성
    - [ ] 3.4.3 `tests/conftest.py` 업데이트 (공통 fixture 추가)
  - [ ] 3.5 Collector 단위 테스트 보완
    - [ ] 3.5.1 `test_rss_collector.py` 검토 및 보완
    - [ ] 3.5.2 `test_telegram_collector.py` 작성 (없는 경우)
    - [ ] 3.5.3 `test_economic_calendar_collector.py` 검토 및 보완
  - [ ] 3.6 Workflow 노드 단위 테스트 작성
    - [ ] 3.6.1 `test_collector_node.py` 작성
    - [ ] 3.6.2 `test_aggregator_node.py` 작성
    - [ ] 3.6.3 `test_insight_node.py` 작성
    - [ ] 3.6.4 `test_keyword_extractor_node.py` 작성
  - [ ] 3.7 통합 테스트 작성
    - [ ] 3.7.1 `tests/integration/test_pipeline.py` 작성 (전체 파이프라인)
  - [ ] 3.8 테스트 실행 및 기준선 확립
    - [ ] 3.8.1 `pytest` 실행하여 모든 테스트 통과 확인
    - [ ] 3.8.2 `pytest --cov=src` 실행하여 현재 커버리지 확인

---

### Phase 4: 디렉토리 구조 재정리

- [ ] **4.0 디렉토리 구조 재정리**
  - [ ] 4.1 `config/` 디렉토리 생성 및 설정 파일 이동
    - [ ] 4.1.1 `config/` 디렉토리 생성
    - [ ] 4.1.2 `config.yml` → `config/config.yml` 이동
    - [ ] 4.1.3 `config/.env.example` 생성 (`.env` 기반 예제)
    - [ ] 4.1.4 `main.py` 및 관련 파일에서 config 경로 업데이트
  - [ ] 4.2 `chard_mcp/` → `src/mcp/` 이동
    - [ ] 4.2.1 `src/mcp/` 디렉토리 생성
    - [ ] 4.2.2 `chard_mcp/*` 파일들을 `src/mcp/`로 이동
    - [ ] 4.2.3 import 경로 업데이트 (`chard_mcp` → `src.mcp`)
    - [ ] 4.2.4 `run_mcp_server.py` 업데이트
  - [ ] 4.3 루트 디렉토리 정리
    - [ ] 4.3.1 `nul` 파일 삭제 (불필요한 파일)
    - [ ] 4.3.2 `search_kaia.py` → `scripts/` 이동 또는 삭제 결정
    - [ ] 4.3.3 `tele_setup.py` → `scripts/setup/` 이동
    - [ ] 4.3.4 `mcp_server_example.py` → `docs/examples/` 또는 삭제 결정
  - [ ] 4.4 `scripts/` 디렉토리 재정리
    - [ ] 4.4.1 `scripts/verification/` 디렉토리 생성
    - [ ] 4.4.2 `scripts/generation/` 디렉토리 생성
    - [ ] 4.4.3 `scripts/setup/` 디렉토리 생성
    - [ ] 4.4.4 `verify_*.py` 스크립트 → `scripts/verification/` 이동
    - [ ] 4.4.5 `generate_*.py` 스크립트 → `scripts/generation/` 이동
    - [ ] 4.4.6 `run_*.py` 스크립트 → `scripts/` 루트 또는 적절한 위치로 이동
  - [ ] 4.5 `src/utils/` 공통 유틸리티 디렉토리 생성
    - [ ] 4.5.1 `src/utils/` 디렉토리 생성
    - [ ] 4.5.2 `src/utils/__init__.py` 생성
    - [ ] 4.5.3 `src/async_utils.py` → `src/utils/async_utils.py` 이동
  - [ ] 4.6 모든 import 경로 업데이트 및 테스트
    - [ ] 4.6.1 모든 파일에서 변경된 경로 업데이트
    - [ ] 4.6.2 `pytest` 실행하여 모든 테스트 통과 확인
    - [ ] 4.6.3 `python main.py --help` 실행하여 메인 기능 확인

---

### Phase 5: 코드 스타일 통일 및 문서화

- [ ] **5.0 코드 스타일 통일 및 문서화**
  - [ ] 5.1 코드 포맷팅 적용
    - [ ] 5.1.1 `black .` 실행하여 전체 코드 포맷팅
    - [ ] 5.1.2 `isort .` 실행하여 import 정렬
    - [ ] 5.1.3 `ruff check . --fix` 실행하여 자동 수정 가능한 린트 오류 수정
    - [ ] 5.1.4 남은 린트 오류 수동 수정
  - [ ] 5.2 Collectors 모듈 문서화
    - [ ] 5.2.1 `src/collectors/README.md` 작성
    - [ ] 5.2.2 `rss_collector.py` docstring 추가
    - [ ] 5.2.3 `telegram_collector.py` docstring 추가
    - [ ] 5.2.4 `economic_calendar_collector.py` docstring 추가
    - [ ] 5.2.5 `models.py` docstring 추가
  - [ ] 5.3 Workflows 모듈 문서화
    - [ ] 5.3.1 `src/workflows/README.md` 작성
    - [ ] 5.3.2 `langgraph_pipeline.py` docstring 추가
    - [ ] 5.3.3 `nodes/*.py` 각 파일 docstring 추가
    - [ ] 5.3.4 `llm_client.py` docstring 추가
    - [ ] 5.3.5 `prompts.py` docstring 추가
  - [ ] 5.4 Report 모듈 문서화
    - [ ] 5.4.1 `src/report/README.md` 작성
    - [ ] 5.4.2 `report_builder.py` docstring 추가
  - [ ] 5.5 프로젝트 아키텍처 문서 작성
    - [ ] 5.5.1 `docs/architecture.md` 작성 (전체 시스템 구조)
    - [ ] 5.5.2 데이터 흐름 다이어그램 포함
    - [ ] 5.5.3 모듈 간 의존성 그래프 포함
  - [ ] 5.6 API 문서 작성
    - [ ] 5.6.1 `docs/api-reference.md` 작성
    - [ ] 5.6.2 MCP 서버 API 문서화

---

### Phase 6: 모듈화 개선 및 의존성 정리

- [ ] **6.0 모듈화 개선 및 의존성 정리**
  - [ ] 6.1 Collector 인터페이스 정의
    - [ ] 6.1.1 `src/collectors/base.py` 생성 (BaseCollector ABC 정의)
    - [ ] 6.1.2 `rss_collector.py`가 BaseCollector를 상속하도록 수정
    - [ ] 6.1.3 `telegram_collector.py`가 BaseCollector를 상속하도록 수정
    - [ ] 6.1.4 `economic_calendar_collector.py`가 BaseCollector를 상속하도록 수정
  - [ ] 6.2 순환 의존성 분석 및 제거
    - [ ] 6.2.1 현재 의존성 그래프 생성 (pydeps 또는 수동 분석)
    - [ ] 6.2.2 순환 의존성 식별
    - [ ] 6.2.3 순환 의존성 제거를 위한 리팩토링
  - [ ] 6.3 의존성 파일 정리
    - [ ] 6.3.1 `requirements.txt` 정리 (프로덕션 의존성만)
    - [ ] 6.3.2 각 의존성에 버전 고정 (pinning)
    - [ ] 6.3.3 불필요한 의존성 제거
  - [ ] 6.4 테스트 실행 및 확인
    - [ ] 6.4.1 `pytest` 실행하여 모든 테스트 통과 확인
    - [ ] 6.4.2 `python main.py --help` 실행하여 메인 기능 확인

---

### Phase 7: 최종 검증 및 정리

- [ ] **7.0 최종 검증 및 정리**
  - [ ] 7.1 전체 테스트 실행
    - [ ] 7.1.1 `pytest` 실행 - 모든 테스트 통과 확인
    - [ ] 7.1.2 `pytest --cov=src --cov-report=html` - 커버리지 리포트 생성
    - [ ] 7.1.3 커버리지 목표(70%) 달성 확인
  - [ ] 7.2 린트 및 포맷 검증
    - [ ] 7.2.1 `ruff check .` - 린트 오류 0건 확인
    - [ ] 7.2.2 `black --check .` - 포맷 검증
  - [ ] 7.3 기능 테스트
    - [ ] 7.3.1 `python main.py` 실행하여 전체 파이프라인 동작 확인
    - [ ] 7.3.2 MCP 서버 실행 테스트
  - [ ] 7.4 문서 검토
    - [ ] 7.4.1 모든 README 파일 검토
    - [ ] 7.4.2 링크 및 경로 유효성 확인
  - [ ] 7.5 Git 정리 및 커밋
    - [ ] 7.5.1 `.gitignore` 업데이트 (필요시)
    - [ ] 7.5.2 변경사항 커밋
    - [ ] 7.5.3 feature branch를 main에 머지 (또는 PR 생성)
  - [ ] 7.6 README.md 업데이트
    - [ ] 7.6.1 새로운 프로젝트 구조 반영
    - [ ] 7.6.2 개발 환경 설정 방법 업데이트
    - [ ] 7.6.3 테스트 실행 방법 추가

---

## Summary

| Phase | 설명 | 예상 태스크 수 |
|-------|------|---------------|
| 0 | 준비 (브랜치 생성) | 2 |
| 1 | 개발 환경 및 도구 설정 | 9 |
| 2 | 가이드라인 문서 작성 | 10 |
| 3 | 테스트 인프라 구축 | 25 |
| 4 | 디렉토리 구조 재정리 | 22 |
| 5 | 코드 스타일 통일 및 문서화 | 18 |
| 6 | 모듈화 개선 및 의존성 정리 | 12 |
| 7 | 최종 검증 및 정리 | 14 |
| **Total** | | **112** |

---

*생성일: 2024-12-23*

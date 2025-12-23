# PRD: CHARD 프로젝트 코드 체계 정리 및 관리 체계 수립

## 1. Introduction/Overview

CHARD 프로젝트는 암호화폐 및 금융 시장 데이터를 수집하고 분석하여 인사이트를 제공하는 시스템입니다. 프로젝트가 성장하면서 수많은 기능 추가와 수정이 이루어졌으나, 체계적인 코드 관리가 부족하여 다음과 같은 문제가 발생하고 있습니다:

- **문서화 부족**: 코드 이해가 어려워 유지보수 시간이 증가
- **테스트 부재**: 수정 시 사이드 이펙트 우려로 안정적인 개발이 어려움
- **복잡한 의존성**: 모듈 간 결합도가 높아 개별 기능 수정이 어려움

이 PRD는 전체 프로젝트의 코드 체계를 정리하고, 지속 가능한 코드 관리 체계를 수립하기 위한 요구사항을 정의합니다.

---

## 2. Goals

1. **문서화 체계 수립**: 모든 주요 모듈에 대한 docstring 및 README 작성
2. **테스트 커버리지 확보**: 핵심 기능에 대한 단위 테스트 및 통합 테스트 작성
3. **모듈화 개선**: 모듈 간 의존성을 명확히 하고 결합도를 낮춤
4. **코딩 컨벤션 통일**: 일관된 코드 스타일 적용
5. **디렉토리 구조 정리**: 명확하고 직관적인 파일/폴더 구조 확립
6. **개발 가이드라인 문서화**: 향후 개발자를 위한 기여 가이드 작성

---

## 3. User Stories

### 개인 투자자/트레이더
- 사용자로서, 안정적으로 동작하는 시스템을 원합니다. 코드 수정 후에도 기존 기능이 정상 작동해야 합니다.

### 개발자 (API/통합 용도)
- 개발자로서, 코드를 쉽게 이해하고 수정할 수 있어야 합니다.
- 개발자로서, 새로운 기능을 추가할 때 기존 코드에 미치는 영향을 파악할 수 있어야 합니다.
- 개발자로서, 명확한 API 문서를 통해 시스템과 통합할 수 있어야 합니다.

---

## 4. Functional Requirements

### 4.1 디렉토리/파일 구조 재정리

| 번호 | 요구사항 |
|------|----------|
| FR-1.1 | 루트 디렉토리의 불필요한 파일 정리 (예: `nul`, `search_kaia.py`, `tele_setup.py` 등 적절한 위치로 이동) |
| FR-1.2 | `chard_mcp/` 모듈을 `src/` 하위로 이동하거나 독립 패키지로 분리 |
| FR-1.3 | 테스트 파일 (`test_*.py`)을 루트에서 `tests/` 디렉토리로 이동 |
| FR-1.4 | `scripts/` 디렉토리 내 스크립트 목적별 분류 (검증, 생성, 실행 등) |
| FR-1.5 | 설정 파일 (`config.yml`, `.env`, `ref.env`)을 `config/` 디렉토리로 통합 |

### 4.2 코드 스타일/컨벤션 통일

| 번호 | 요구사항 |
|------|----------|
| FR-2.1 | Python 코드 스타일 가이드 문서 작성 (PEP 8 기반) |
| FR-2.2 | `pyproject.toml` 또는 설정 파일에 linter/formatter 설정 추가 (black, ruff, isort 등) |
| FR-2.3 | 네이밍 컨벤션 정의 (변수, 함수, 클래스, 파일명) |
| FR-2.4 | Import 순서 및 구조 표준화 |

### 4.3 문서화

| 번호 | 요구사항 |
|------|----------|
| FR-3.1 | 모든 공개 함수/클래스에 Google 스타일 docstring 작성 |
| FR-3.2 | 각 모듈(`src/collectors`, `src/workflows`, `src/report`)에 README.md 작성 |
| FR-3.3 | 프로젝트 전체 아키텍처 다이어그램 작성 |
| FR-3.4 | API 엔드포인트 문서화 (MCP 서버 포함) |
| FR-3.5 | 설정 파일(`config.yml`) 각 항목에 대한 설명 문서 작성 |

### 4.4 테스트 코드 체계화

| 번호 | 요구사항 |
|------|----------|
| FR-4.1 | `tests/` 디렉토리 구조를 `src/` 구조와 동일하게 미러링 |
| FR-4.2 | 각 collector에 대한 단위 테스트 작성 (`rss`, `telegram`, `economic_calendar`) |
| FR-4.3 | workflow 노드에 대한 단위 테스트 작성 |
| FR-4.4 | 통합 테스트 작성 (전체 파이프라인 테스트) |
| FR-4.5 | pytest 설정 파일(`pytest.ini` 또는 `pyproject.toml`) 구성 |
| FR-4.6 | 테스트 fixture 및 mock 데이터 정리 (`tests/fixtures/`) |

### 4.5 모듈화/의존성 관리

| 번호 | 요구사항 |
|------|----------|
| FR-5.1 | 모듈 간 의존성 그래프 문서화 |
| FR-5.2 | 순환 의존성 제거 |
| FR-5.3 | 인터페이스(Protocol/ABC) 정의를 통한 느슨한 결합 구현 |
| FR-5.4 | `requirements.txt`를 용도별로 분리 (`requirements.txt`, `requirements-dev.txt`, `requirements-test.txt`) |
| FR-5.5 | 의존성 버전 고정 및 보안 취약점 검사 도구 도입 |

### 4.6 개발 가이드라인

| 번호 | 요구사항 |
|------|----------|
| FR-6.1 | `CONTRIBUTING.md` 파일 작성 (기여 가이드) |
| FR-6.2 | Git 브랜치 전략 문서화 |
| FR-6.3 | 코드 리뷰 체크리스트 작성 |
| FR-6.4 | 릴리스/버전 관리 가이드 작성 |

---

## 5. Non-Goals (Out of Scope)

- 새로운 기능 개발 (이 PRD는 기존 코드 정리에 집중)
- 성능 최적화 (별도 PRD로 진행)
- UI/UX 개선 (해당 없음)
- 클라우드 배포 설정 (별도 PRD로 진행)
- CI/CD 파이프라인 구축 (이 PRD에서는 가이드라인만 제공)

---

## 6. Design Considerations

### 6.1 제안하는 디렉토리 구조

```
chard/
├── config/                    # 설정 파일
│   ├── config.yml
│   └── .env.example
├── docs/                      # 문서
│   ├── architecture.md
│   ├── api-reference.md
│   └── ...
├── scripts/                   # 유틸리티 스크립트
│   ├── verification/          # 검증 스크립트
│   ├── generation/            # 생성 스크립트
│   └── setup/                 # 설정 스크립트
├── src/                       # 소스 코드
│   ├── __init__.py
│   ├── collectors/            # 데이터 수집
│   │   ├── __init__.py
│   │   ├── base.py            # 기본 클래스/인터페이스
│   │   ├── rss_collector.py
│   │   ├── telegram_collector.py
│   │   └── economic_calendar_collector.py
│   ├── workflows/             # 워크플로우/파이프라인
│   │   ├── __init__.py
│   │   ├── nodes/
│   │   └── normalization/
│   ├── report/                # 리포트 생성
│   ├── mcp/                   # MCP 서버 (chard_mcp에서 이동)
│   └── utils/                 # 공통 유틸리티
├── tests/                     # 테스트
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/              # 테스트 데이터
│   ├── unit/                  # 단위 테스트
│   │   ├── collectors/
│   │   ├── workflows/
│   │   └── report/
│   └── integration/           # 통합 테스트
├── main.py                    # 진입점
├── pyproject.toml             # 프로젝트 설정
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### 6.2 코딩 컨벤션 요약

- **Formatter**: Black (line-length: 88)
- **Linter**: Ruff
- **Import 정렬**: isort
- **Type Hints**: 모든 공개 함수에 타입 힌트 필수
- **Docstring**: Google 스타일

---

## 7. Technical Considerations

### 7.1 의존성
- 기존 기능에 영향을 주지 않도록 점진적 리팩토링 수행
- 각 단계별로 테스트를 통해 기능 유지 확인

### 7.2 마이그레이션 전략
1. **Phase 1**: 가이드라인 문서 작성 (구조 설계, 컨벤션 정의)
2. **Phase 2**: 테스트 코드 작성 (기존 기능 동작 보장)
3. **Phase 3**: 디렉토리 구조 재정리
4. **Phase 4**: 코드 스타일 통일 및 문서화
5. **Phase 5**: 모듈화 개선 및 의존성 정리

### 7.3 도구
- **Black**: 코드 포맷팅
- **Ruff**: 린팅
- **pytest**: 테스트
- **pytest-cov**: 테스트 커버리지
- **pre-commit**: Git 훅을 통한 자동 검사

---

## 8. Success Metrics

| 지표 | 목표 |
|------|------|
| 테스트 커버리지 | 핵심 모듈 70% 이상 |
| 문서화 완성도 | 모든 공개 함수/클래스에 docstring 100% |
| Lint 오류 | 0건 (Ruff 기준) |
| 순환 의존성 | 0건 |
| 코드 리뷰 시간 단축 | 기존 대비 50% 감소 (체감) |

---

## 9. Open Questions

1. **MCP 모듈 분리**: `chard_mcp`를 독립 패키지로 분리할 것인가, `src/mcp`로 통합할 것인가?
2. **버전 관리**: 시맨틱 버저닝을 도입할 것인가? 현재 버전은 무엇으로 설정할 것인가?
3. **CI/CD**: GitHub Actions 등 CI/CD 파이프라인을 이 PRD 범위에 포함할 것인가?
4. **레거시 코드**: `search_kaia.py`, `tele_setup.py` 등 루트 레벨 스크립트를 유지할 것인가, 제거/통합할 것인가?

---

## Appendix: 현재 프로젝트 구조 분석

### 현재 디렉토리 구조
```
chard/
├── chard_mcp/           # MCP 서버 (루트에 위치)
├── docs/                # 문서
├── logs/                # 로그 파일
├── output/              # 출력 파일
├── scripts/             # 유틸리티 스크립트
├── secrets/             # 비밀 정보
├── src/                 # 소스 코드
│   ├── collectors/      # 데이터 수집기
│   ├── report/          # 리포트 생성
│   └── workflows/       # 워크플로우
├── tests/               # 테스트
├── main.py              # 메인 진입점
├── config.yml           # 설정 파일 (루트)
├── search_kaia.py       # 검색 스크립트 (루트)
├── tele_setup.py        # 텔레그램 설정 (루트)
├── test_*.py            # 테스트 파일 (루트에 일부 존재)
└── ...
```

### 식별된 문제점
1. 루트 디렉토리에 혼재된 파일들 (`test_*.py`, `search_kaia.py`, `tele_setup.py`)
2. `chard_mcp`가 `src` 외부에 위치
3. 설정 파일이 루트에 산재
4. 테스트 디렉토리 구조가 소스 구조와 불일치
5. 공통 유틸리티를 위한 명확한 위치 부재

---

*문서 작성일: 2024-12-23*
*버전: 1.0*

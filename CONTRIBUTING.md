# CHARD 기여 가이드

CHARD 프로젝트에 기여해 주셔서 감사합니다! 이 문서는 프로젝트에 기여하는 방법을 안내합니다.

## 1. 개발 환경 설정

### 1.1 저장소 클론
```bash
git clone https://github.com/yuriburi88/chard.git
cd chard
```

### 1.2 Python 환경 설정
Python 3.10 이상이 필요합니다.

```bash
# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 1.3 의존성 설치
```bash
# 프로덕션 의존성
pip install -r requirements.txt

# 개발 의존성
pip install -r requirements-dev.txt

# 테스트 의존성
pip install -r requirements-test.txt
```

### 1.4 Pre-commit 훅 설치
```bash
pre-commit install
```

이제 커밋할 때마다 자동으로 코드 포맷팅과 린팅이 실행됩니다.

### 1.5 환경 변수 설정
```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env

# .env 파일을 열어 필요한 값 입력
# - GOOGLE_API_KEY: Google Gemini API 키
# - TELEGRAM_API_ID, TELEGRAM_API_HASH: Telegram API 자격 증명
```

---

## 2. Git 브랜치 전략

### 2.1 브랜치 종류

| 브랜치 | 설명 | 예시 |
|--------|------|------|
| `main` | 안정된 프로덕션 코드 | - |
| `feature/*` | 새 기능 개발 | `feature/add-twitter-collector` |
| `bugfix/*` | 버그 수정 | `bugfix/fix-rss-parsing` |
| `hotfix/*` | 긴급 수정 | `hotfix/critical-security-fix` |
| `refactor/*` | 코드 리팩토링 | `refactor/improve-collector-interface` |
| `docs/*` | 문서 작업 | `docs/update-readme` |

### 2.2 브랜치 생성
```bash
# 최신 main에서 시작
git checkout main
git pull origin main

# 새 브랜치 생성
git checkout -b feature/your-feature-name
```

### 2.3 브랜치 네이밍 규칙
- 소문자와 하이픈(`-`) 사용
- 간결하고 설명적인 이름
- 예시:
  - `feature/add-economic-calendar`
  - `bugfix/fix-telegram-timeout`
  - `docs/update-api-reference`

---

## 3. Pull Request 작성 가이드

### 3.1 PR 생성 전 체크리스트
```bash
# 1. 코드 포맷팅 확인
python -m black --check .
python -m isort --check .

# 2. 린트 확인
python -m ruff check .

# 3. 테스트 실행
python -m pytest

# 4. 타입 체크 (선택사항)
python -m mypy src/
```

### 3.2 PR 제목 형식
```
<type>: <간단한 설명>

예시:
feat: Add Twitter collector
fix: Fix RSS feed parsing error
docs: Update installation guide
refactor: Improve collector base class
test: Add unit tests for telegram collector
chore: Update dependencies
```

**Type 종류:**
- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `refactor`: 코드 리팩토링 (기능 변경 없음)
- `test`: 테스트 추가/수정
- `chore`: 빌드, 설정 등 기타 변경

### 3.3 PR 본문 템플릿
```markdown
## 요약
이 PR이 무엇을 변경하는지 간략히 설명합니다.

## 변경 사항
- 변경 1
- 변경 2
- 변경 3

## 테스트 방법
1. 테스트 단계 1
2. 테스트 단계 2

## 체크리스트
- [ ] 코드 포맷팅 완료 (`black`, `isort`)
- [ ] 린트 통과 (`ruff`)
- [ ] 테스트 통과 (`pytest`)
- [ ] 문서 업데이트 (필요시)

## 관련 이슈
Closes #123
```

---

## 4. 코드 리뷰 체크리스트

### 4.1 코드 품질
- [ ] 코드가 명확하고 읽기 쉬운가?
- [ ] 적절한 변수/함수 이름을 사용했는가?
- [ ] 불필요한 코드 중복이 없는가?
- [ ] 에러 처리가 적절한가?

### 4.2 기능
- [ ] 요구사항을 충족하는가?
- [ ] 엣지 케이스를 고려했는가?
- [ ] 기존 기능에 영향을 주지 않는가?

### 4.3 테스트
- [ ] 새 코드에 대한 테스트가 있는가?
- [ ] 기존 테스트가 통과하는가?
- [ ] 테스트 커버리지가 적절한가?

### 4.4 문서
- [ ] 코드에 필요한 주석이 있는가?
- [ ] Docstring이 작성되어 있는가?
- [ ] README나 문서 업데이트가 필요한가?

### 4.5 보안
- [ ] 민감한 정보(API 키, 비밀번호)가 하드코딩되어 있지 않은가?
- [ ] 입력 검증이 적절한가?

---

## 5. 커밋 메시지 규칙

### 5.1 형식
```
<type>: <subject>

<body> (선택사항)

<footer> (선택사항)
```

### 5.2 예시
```
feat: Add economic calendar collector

- Implement InvestPy integration
- Add date range filtering
- Support multiple countries

Closes #45
```

### 5.3 규칙
- 제목은 50자 이내
- 제목은 명령형으로 작성 (Add, Fix, Update 등)
- 본문은 72자에서 줄바꿈
- 본문에는 "무엇을"과 "왜"를 설명

---

## 6. 이슈 보고

버그를 발견하거나 기능을 제안하려면 GitHub Issues를 사용해 주세요.

### 버그 보고 템플릿
```markdown
## 버그 설명
버그에 대한 명확한 설명

## 재현 방법
1. 단계 1
2. 단계 2
3. 단계 3

## 예상 동작
예상되는 정상 동작

## 실제 동작
실제로 발생한 동작

## 환경
- OS: Windows 11
- Python: 3.11
- CHARD 버전: 0.1.0
```

---

## 7. 도움이 필요하신가요?

- 질문이나 토론: GitHub Discussions 사용
- 버그 보고: GitHub Issues 사용
- 코드 기여: Pull Request 생성

감사합니다!

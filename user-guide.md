# 사용자 안내서

디지털 자산 내러티브 추출 플랫폼을 처음 사용하는 분을 위한 단계별 가이드입니다.

## 목차

1. [시작하기 전 준비사항](#시작하기-전-준비사항)
2. [API 키 발급 및 설정](#api-키-발급-및-설정)
3. [텔레그램 설정 (선택사항)](#텔레그램-설정-선택사항)
4. [프로그램 실행하기](#프로그램-실행하기)
5. [결과 확인하기](#결과-확인하기)
6. [문제 해결](#문제-해결)

---

## 시작하기 전 준비사항

### 1. Python 설치 확인

프로그램을 실행하기 전에 Python이 설치되어 있는지 확인하세요.

**Windows:**
1. 명령 프롬프트(CMD) 또는 PowerShell을 엽니다
2. 다음 명령을 입력합니다:
   ```cmd
   python --version
   ```
3. `Python 3.10` 이상 버전이 표시되면 정상입니다
4. 설치되어 있지 않다면 [Python 공식 웹사이트](https://www.python.org/downloads/)에서 다운로드하여 설치하세요

### 2. 프로젝트 폴더로 이동

프로그램이 있는 폴더로 이동합니다:

```cmd
cd myDrive:\dev\chard
```

(실제 프로젝트 폴더 경로로 변경하세요)

### 3. 가상 환경 활성화

**Windows:**
```cmd
venv\Scripts\activate
```

가상 환경이 활성화되면 명령 프롬프트 앞에 `(venv)`가 표시됩니다.

---

## API 키 발급 및 설정

프로그램을 실행하려면 AI 서비스의 API 키가 필요합니다. Gemini 또는 OpenAI 중 하나를 선택하여 설정하세요.

### 방법 1: Gemini API 키 사용 (권장)

#### 1단계: Gemini API 키 발급

1. [Google AI Studio](https://aistudio.google.com/app/apikey)에 접속합니다
2. Google 계정으로 로그인합니다
3. "Create API Key" 버튼을 클릭합니다
4. API 키가 생성되면 복사합니다 (예: `AIzaSyAbc123...`)

> ⚠️ **주의**: API 키는 비밀번호처럼 중요합니다. 다른 사람과 공유하지 마세요.

#### 2단계: .env 파일 생성

프로젝트 폴더에 `.env` 파일을 생성합니다:

1. 프로젝트 폴더(`chard`)에서 메모장이나 텍스트 편집기를 엽니다
2. 다음 내용을 입력합니다:
   ```
   GEMINI_API_KEY=여기에_발급받은_API_키_붙여넣기
   ```
3. 파일 이름을 `.env`로 저장합니다 (확장자 없음)
4. 파일 형식을 "모든 파일"로 선택하여 저장합니다

**예시:**
```
GEMINI_API_KEY=AIzaSyAbc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

### 방법 2: OpenAI API 키 사용 (선택사항)

OpenAI 임베딩 기능을 사용하려면 OpenAI API 키도 필요합니다.

#### 1단계: OpenAI API 키 발급

1. [OpenAI Platform](https://platform.openai.com/api-keys)에 접속합니다
2. 계정으로 로그인합니다
3. "Create new secret key" 버튼을 클릭합니다
4. 키 이름을 입력하고 "Create secret key"를 클릭합니다
5. 생성된 키를 복사합니다 (한 번만 표시되므로 반드시 복사하세요)

#### 2단계: .env 파일에 추가

`.env` 파일에 다음 줄을 추가합니다:

```
OPENAI_API_KEY=여기에_발급받은_OpenAI_API_키_붙여넣기
```

**완성된 .env 파일 예시:**
```
GEMINI_API_KEY=AIzaSyAbc123def456ghi789jkl012mno345pqr678stu901vwx234yz
OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

---

## 텔레그램 설정 (선택사항)

텔레그램 채널에서 데이터를 수집하려면 텔레그램 설정이 필요합니다. 텔레그램을 사용하지 않으면 이 단계를 건너뛰어도 됩니다.

### 방법 : MTProto 사용

비공개 채널이나 그룹의 메시지를 수집할 때 사용합니다.

#### 1단계: Telegram API 자격증명 발급

1. [my.telegram.org/apps](https://my.telegram.org/apps)에 접속합니다
2. 전화번호로 로그인합니다
3. "API development tools" 섹션에서:
   - App title: 원하는 이름 입력 (예: "News Collector")
   - Short name: 짧은 이름 입력 (예: "news")
   - Platform: "Desktop" 선택
   - Description: 설명 입력 (선택사항)
4. "Create application"을 클릭합니다
5. **api_id**와 **api_hash**를 복사합니다

#### 2단계: 세션 파일 생성

프로젝트 폴더에서 다음 명령을 실행합니다(텔레그램 접속 프로필(credential, session 정보) 만들기):

```cmd
python tele_setup.py --config config.yml --profile "내_프로필_이름"
```

실행 중 다음 정보를 입력합니다:
- 텔레그램 자격증명 ID: 원하는 ID 입력 (예: `main`, `1`)
- api_id: 위에서 복사한 api_id
- api_hash: 위에서 복사한 api_hash
- 전화번호: 국가코드 포함 (예: `+821012345678`)
- SMS 인증 코드: 텔레그램에서 받은 코드

세션이 생성되면 `secrets/telegram_sessions/` 폴더에 `.session` 파일이 저장됩니다.

#### 3단계: config.yml 파일 수정

`config.yml` 파일의 `telegram_sources` 섹션을 다음과 같이 수정합니다:

```yaml
telegram_sources:
  - name: 내_채널_이름
    auth_method: mtproto
    channel_id: 채널_이름_또는_ID  # 예: "CryptoNews" 또는 숫자 ID
    tg_cred_id: main  # 위에서 입력한 자격증명 ID
    session_file: secrets\telegram_sessions\tg_cred_main.session
```

### 전처리 옵션 (장문 메시지 분할)

텔레그램에서 수집한 장문 메시지가 LLM 입력 제한을 초과하는 경우 자동으로 세그먼트로 분할할 수 있습니다. `config.yml`의 `preprocessing` 섹션을 다음과 같이 설정하세요:

```yaml
preprocessing:
  split_long_messages: true                # 장문 분할 기능 활성화 여부 (기본: true)
  max_tokens_per_segment: 4000             # 세그먼트당 최대 토큰 수
  segment_overlap_tokens: 200              # 세그먼트 간 컨텍스트 오버랩 토큰 수
```

- **split_long_messages**: `true`로 설정하면 토큰 제한을 초과한 메시지를 여러 조각으로 나누어 Stage 4 분석에 전달합니다.
- **max_tokens_per_segment**: 분할된 각 세그먼트의 최대 토큰 수입니다. 사용 중인 LLM 컨텍스트 길이에 맞춰 조정하세요.
- **segment_overlap_tokens**: 세그먼트 간 문맥 손실을 줄이기 위해 겹쳐서 포함할 토큰 수입니다. 0으로 설정하면 오버랩 없이 분할합니다.

분할된 세그먼트에는 다음 메타데이터가 자동으로 추가됩니다.

- `original_message_id` / `message_id`: 원본 텔레그램 메시지 ID
- `segment_index`: 현재 세그먼트의 순번 (0부터 시작)
- `segment_count`: 전체 세그먼트 개수
- `segment_range_tokens.start`, `segment_range_tokens.end`: 원본 메시지에서 차지하는 토큰 범위

이 정보를 사용하면 Stage 4 이후 단계에서 각 세그먼트가 어떤 원본 메시지에 속했는지 추적하고, 필요 시 원문을 재조합할 수 있습니다.

---

## 프로그램 실행하기

### 프로그램 실행

가장 간단한 방법으로 프로그램을 실행합니다:

```cmd
python main.py --config config.yml
```

이 명령 하나로 다음 작업이 모두 자동으로 실행됩니다:
1. **데이터 수집**: RSS 기사 및 텔레그램 메시지 수집
2. **전처리**: 데이터 정제 및 필터링
3. **정규화**: 공통 형식으로 변환
4. **원본 데이터 저장**: `*_raw.json` 파일 생성
5. **LLM 분석**: 키워드 추출 및 인사이트 생성
6. **리포트 생성**: `*_summary.json` 및 `*_summary.md` 파일 생성

**실행 중 표시되는 내용:**
- 수집 중인 데이터 소스 정보
- 수집된 기사/메시지 수
- 키워드 추출 진행 상황
- 분석 완료 메시지
- 리포트 생성 완료 메시지

**실행 시간:** 보통 2-15분 정도 소요됩니다 (데이터 양에 따라 다름).

> 💡 **참고**: 기존에 수집된 데이터로 분석만 다시 실행하려면 `scripts/run_stage4.py`를 별도로 실행할 수 있습니다.

---

## 결과 확인하기

### 결과 파일 위치

프로그램 실행이 완료되면 다음 위치에 결과 파일이 생성됩니다:

```
output/
└── 2025-11-13/          (실행한 날짜)
    ├── 143022_raw.json          (원본 데이터)
    ├── 143022_summary.json      (JSON 리포트)
    └── 143022_summary.md        (Markdown 리포트) ⭐
```

> ✅ **중요**: `main.py`를 실행하면 자동으로 Markdown 리포트(`*_summary.md`)가 생성됩니다.
> 
> 프로그램 실행이 완료되면 콘솔에 다음과 같은 메시지가 표시됩니다:
> ```
> ✅ Markdown 리포트: 143022_summary.md
> ✅ JSON 리포트: 143022_summary.json
> ```

### Markdown 리포트 확인

**가장 간단한 방법:**

1. `output` 폴더를 엽니다
2. 오늘 날짜 폴더(예: `2025-11-13`)를 엽니다
3. `*_summary.md` 파일을 더블클릭하여 열기
4. 메모장이나 마크다운 뷰어로 열립니다

**Markdown 뷰어 사용 (권장):**

- [Typora](https://typora.io/) (유료, 무료 평가판 있음)
- [Mark Text](https://marktext.app/) (무료)
- [VS Code](https://code.visualstudio.com/) (무료, 확장 프로그램 설치)

### 리포트 내용

생성된 Markdown 리포트에는 다음 정보가 포함됩니다:

1. **헤더 정보**
   - 생성 시간
   - 분석 기간
   - 데이터 소스 통계

2. **상위 키워드**
   - 키워드 순위표
   - 원본 변형 정보
   - 중요도 점수
   - 출처 수

3. **시장 내러티브 요약**
   - 3-5개 문단으로 구성된 시장 분석

4. **거래 인사이트**
   - 기회 항목
   - 위험 요소
   - 시장 심리

5. **주요 출처**
   - 관련 기사 링크
   - 텔레그램 메시지 정보

### JSON 리포트 확인

JSON 리포트는 프로그램에서 자동으로 처리할 때 사용됩니다. 일반 사용자는 Markdown 리포트만 확인하면 됩니다.

---

## 문제 해결

### 문제 1: "GEMINI_API_KEY 환경 변수가 설정되지 않았습니다" 오류

**원인:** `.env` 파일이 없거나 API 키가 잘못 입력되었습니다.

**해결 방법:**
1. 프로젝트 폴더에 `.env` 파일이 있는지 확인합니다
2. `.env` 파일을 열어서 다음 형식이 맞는지 확인합니다:
   ```
   GEMINI_API_KEY=AIzaSy...
   ```
3. 등호(`=`) 앞뒤에 공백이 없어야 합니다
4. API 키 앞뒤에 따옴표(`"` 또는 `'`)가 없어야 합니다

### 문제 2: "설정 파일을 찾을 수 없습니다" 오류

**원인:** `config.yml` 파일이 프로젝트 폴더에 없습니다.

**해결 방법:**
1. 프로젝트 폴더에 `config.yml` 파일이 있는지 확인합니다
2. 없다면 프로젝트 관리자에게 문의하세요

### 문제 3: "입력 파일을 찾을 수 없습니다" 오류 (Stage 4 실행 시)

**원인:** 1단계(데이터 수집)가 완료되지 않았거나 파일 경로가 잘못되었습니다.

**해결 방법:**
1. 먼저 `python main.py --config config.yml`을 실행했는지 확인합니다
2. `output` 폴더에서 가장 최근에 생성된 `*_raw.json` 파일의 정확한 경로를 확인합니다
3. 경로에 백슬래시(`\`)를 사용했는지 확인합니다 (Windows)

**올바른 예시:**
```cmd
python scripts/run_stage4.py --input output\2025-11-13\143022_raw.json --config config.yml
```

### 문제 4: 텔레그램 데이터가 수집되지 않음

**원인:** 텔레그램 설정이 잘못되었거나 권한이 없습니다.

**해결 방법:**

**Bot API 사용 시:**
1. 봇이 해당 채널에 추가되어 있는지 확인합니다
2. 채널이 공개 채널인지 확인합니다
3. `channel_id`가 올바른지 확인합니다 (`@` 기호 포함)

**MTProto 사용 시:**
1. 세션 파일이 올바른 위치에 있는지 확인합니다
2. 해당 채널/그룹에 접근 권한이 있는지 확인합니다
3. `tele_setup.py`를 다시 실행하여 세션을 재생성합니다

### 문제 5: "ModuleNotFoundError" 오류

**원인:** 필요한 패키지가 설치되지 않았습니다.

**해결 방법:**
1. 가상 환경이 활성화되어 있는지 확인합니다 (`(venv)` 표시 확인)
2. 다음 명령을 실행합니다:
   ```cmd
   pip install -r requirements.txt
   ```

### 문제 6: 리포트가 생성되지 않음

**원인:** Stage 4 실행 중 오류가 발생했을 수 있습니다.

**해결 방법:**
1. `logs` 폴더에서 가장 최근 로그 파일을 확인합니다
2. 오류 메시지를 확인하고 위의 문제 해결 방법을 참고합니다
3. 문제가 계속되면 프로젝트 관리자에게 문의하세요

---

## 자주 묻는 질문 (FAQ)

### Q1: 프로그램을 매일 실행해야 하나요?

**A:** 네, 새로운 데이터를 분석하려면 매일 실행해야 합니다. 자동화를 원하면 프로젝트 관리자에게 문의하세요.

### Q2: API 키 사용량은 어떻게 확인하나요?

**A:** 
- **Gemini**: [Google AI Studio](https://aistudio.google.com/app/apikey)에서 확인
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/usage)에서 확인

### Q3: 리포트는 어디에 저장되나요?

**A:** `output` 폴더의 날짜별 폴더에 저장됩니다. 예: `output\2025-11-13\143022_summary.md`

### Q4: 이전 리포트는 삭제해도 되나요?

**A:** 네, 삭제해도 됩니다. 하지만 나중에 참고할 수 있도록 백업을 권장합니다.

### Q5: 여러 날짜의 리포트를 한 번에 생성할 수 있나요?

**A:** 현재는 한 번에 하루치 데이터만 처리합니다. 여러 날짜를 처리하려면 각 날짜별로 실행해야 합니다.

---

## 추가 도움말

- **기술 문서**: `dev-doc/` 폴더의 문서들을 참고하세요
- **설정 파일**: `config.yml` 파일의 주석을 참고하세요
- **문제 발생 시**: `logs/` 폴더의 로그 파일을 확인하세요

---

**마지막 업데이트**: 2025-11-13


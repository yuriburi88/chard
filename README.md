# 디지털 자산 내러티브 추출 플랫폼

RSS 피드와 텔레그램 채팅 데이터를 수집하여 Gemini LLM을 활용해 키워드 추출 및 내러티브 요약 리포트를 생성하는 플랫폼입니다.

## 프로젝트 구조

```
rex/
├── src/
│   ├── collectors/          # 데이터 수집 모듈 (RSS, 텔레그램)
│   ├── workflows/           # LangGraph 워크플로
│   │   ├── nodes/          # 워크플로 노드들
│   │   └── normalization/  # 키워드 정규화
│   └── report/             # 리포트 생성
├── tests/                  # 테스트 모듈
├── dev-doc/                # 개발 문서
├── output/                 # 실행 결과 저장 디렉터리
├── main.py                 # CLI 엔트리 포인트
├── config.yml              # 설정 파일 (샘플)
├── .env                    # 환경 변수 (Gemini API 키 등)
└── requirements.txt        # Python 의존성 패키지
```

## 설치 및 설정

### 1. 가상 환경 생성 및 활성화

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 2. 의존성 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 Gemini API 키를 설정합니다:

```env
GEMINI_API_KEY=your_api_key_here
```

### 4. 설정 파일 준비

`config.yml` 파일을 생성하고 수집 기간, 데이터 소스, LLM 옵션 등을 설정합니다.

#### 텔레그램 설정 (선택사항)

텔레그램 데이터 수집을 위해 두 가지 방식을 지원합니다:

**방식 1: Bot API (권장)**
- BotFather에서 봇을 생성하고 토큰을 발급받습니다
- `config.yml`에서 `auth_method: "bot_api"`와 `bot_token`을 설정합니다
- 공개 채널 메시지 수집에 적합합니다

**방식 2: MTProto (고급)**
- https://my.telegram.org/apps에서 API ID와 API Hash를 발급받습니다
- `tele_setup.py`를 실행하여 자격증명을 `.env`에 저장하고 세션 파일을 생성합니다
- `config.yml`에서 `auth_method: "mtproto"`, `tg_cred_id`를 설정합니다 (자격증명은 환경변수에서 자동 로드)
- 비공개 채널/그룹 메시지 수집이 가능합니다

자세한 설정 방법은 `config.yml`의 주석을 참조하세요.

### MTProto 세션 생성 예시

MTProto 수집을 사용하려면 먼저 Telethon 세션 파일을 만들어야 합니다.  
프로젝트 루트에서 다음 명령을 실행하고 안내에 따라 `api_id`, `api_hash`, 전화번호, SMS 인증 코드를 입력하면 세션이 생성됩니다.

```bash
python tele_setup.py --config config.yml --profile "Crypto News Channel"
```

실행 중 텔레그램 자격증명 ID(예: `1`, `ONE`, `MAIN`), `api_id`, `api_hash`, 전화번호, 채널 식별자, SMS 인증 코드를 입력하면, 스크립트가 Telethon 세션을 생성하고 자격증명 기반으로 `.env`와 `config.yml`을 자동으로 갱신합니다.  

**자격증명 기반 관리의 장점:**
- 하나의 텔레그램 자격증명(api_id, api_hash, phone)으로 여러 채널에 접근 가능
- 동일한 자격 정보를 중복 저장하지 않아 효율적
- 자격증명별로 세션 파일을 하나만 관리

`.env`에는 `TG_CRED_<ID>_API_ID`, `TG_CRED_<ID>_API_HASH`, `TG_CRED_<ID>_PHONE` 등이 기록되며, `config.yml`에는 `tg_cred_id`와 `session_file`만 기록됩니다. 동일한 `tg_cred_id`를 사용하는 채널들은 같은 세션 파일을 공유합니다.  
생성된 `.session` 파일은 기본적으로 `secrets/telegram_sessions/tg_cred_<id>.session` 형태로 저장되며, 이후 MTProto 수집 실행 시 추가 인증이 필요 없습니다.  
세부 절차는 `dev-doc/mtproto-setup-plan.md`를 참고하세요.

## 사용법

### 빠른 시작 (비개발자용)

자세한 사용 방법은 [사용자 안내서](./dev-doc/user-guide.md)를 참조하세요.

**기본 실행 (한 번에 끝까지 실행):**
```bash
python main.py --config config.yml
```

이 명령 하나로 데이터 수집부터 Markdown 리포트 생성까지 모두 자동 실행됩니다.

**결과 확인:**
- Markdown 리포트: `output/<날짜>/<시간>_summary.md` ⭐
- JSON 리포트: `output/<날짜>/<시간>_summary.json`
- 원본 데이터: `output/<날짜>/<시간>_raw.json`

> 💡 **참고**: 기존 데이터로 분석만 다시 실행하려면 `scripts/run_stage4.py`를 별도로 사용할 수 있습니다.

### 개발자용

```bash
python main.py --config config.yml
```

## 개발 가이드

자세한 내용은 다음 문서를 참조하세요:

- [PRD](./dev-doc/prd-digital-asset-narrative-extractor.md): 전체 프로젝트 요구사항
- [LLM 키워드 분석 파이프라인](./dev-doc/llm-keyword-analysis-pipeline.md): LangGraph 워크플로 설계
- [Tasks](./tasks/tasks-prd-digital-asset-narrative-extractor.md): 개발 태스크 목록


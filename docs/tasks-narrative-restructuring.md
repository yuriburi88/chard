## Relevant Files

- `src/workflows/prompts.py` - 프롬프트 공통 부분 추출, Key Points 프롬프트 추가, 기존 Narrative 프롬프트 파라미터 확장
- `src/workflows/nodes/insight_node.py` - 2단계 LLM 호출 로직 구현, 소스 필터링 로직 추가
- `src/workflows/state.py` - insights 타입 정의에 key_points 필드 추가
- `src/report/report_builder.py` - Key Points 표시 로직 추가, Markdown/JSON 출력 수정
- `config.yml` - enable_segmentation 설정 제거 또는 deprecated 표시

### Notes

- 이 기능은 LLM 호출을 기존 3회에서 6회로 증가시킵니다
- Key Points 개수는 5~20개 범위에서 LLM이 자동 결정합니다
- 테스트 시 `pytest` 또는 `python -m pytest` 명령어를 사용합니다
- **핵심 원칙**: 기존 프롬프트를 최대한 재활용하고, 출력 형식만 변경하는 방식으로 구현

### 프롬프트 리팩토링 전략

```
[공통 부분 추출]
_build_macro_prompt_base() → (system_prompt, user_prompt_base)
  - system_prompt: 역할 정의
  - user_prompt_base: 데이터 섹션 + 작성 가이드

[Key Points 프롬프트]
build_macro_keypoints_prompt()
  = _build_macro_prompt_base() + Key Points 출력 형식

[Narrative 프롬프트]
build_macro_narrative_prompt(key_points=None)
  = _build_macro_prompt_base() + (Key Points 데이터) + Narrative 출력 형식
```

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [ ] 0.0 Create feature branch
  - [ ] 0.1 Create and checkout a new branch for this feature (`git checkout -b feature/narrative-restructure`)

- [ ] 1.0 State 타입 정의 업데이트
  - [ ] 1.1 `src/workflows/state.py` 파일 읽기 및 현재 insights 구조 분석
  - [ ] 1.2 `key_points` 필드를 포함한 새로운 narrative 타입 정의 추가
  - [ ] 1.3 `source_mapping` 필드 타입 정의 추가
  - [ ] 1.4 기존 `narrative_summary` 필드를 deprecated로 표시

- [ ] 2.0 프롬프트 공통 부분 추출 (리팩토링)
  - [ ] 2.1 `src/workflows/prompts.py` 파일 읽기 및 현재 프롬프트 구조 분석
  - [ ] 2.2 `build_macro_narrative_prompt()`에서 공통 부분 식별
    - system_prompt (역할 정의)
    - 데이터 섹션 (키워드, 소스, 경제일정)
    - 작성 가이드 (문단 구성, 인과관계 원칙 등)
    - 출력 형식 (JSON 구조)
  - [ ] 2.3 `_build_macro_prompt_base()` 내부 헬퍼 함수 생성
    - 입력: keywords, source_highlights, economic_events
    - 출력: (system_prompt, user_prompt_base) 튜플
  - [ ] 2.4 `_build_crypto_prompt_base()` 내부 헬퍼 함수 생성
  - [ ] 2.5 `_build_integrated_prompt_base()` 내부 헬퍼 함수 생성
  - [ ] 2.6 기존 `build_*_narrative_prompt()` 함수들이 `_build_*_prompt_base()` 사용하도록 리팩토링
  - [ ] 2.7 리팩토링 후 기존 동작 테스트 (regression 확인)

- [ ] 3.0 Key Points 생성 프롬프트 구현
  - [ ] 3.1 `build_macro_keypoints_prompt()` 함수 구현
    - `_build_macro_prompt_base()` 재사용
    - 출력 형식만 Key Points용으로 변경 (key_points + source_mapping)
    - 5~20개 범위, 정량적 데이터 포함, 중요도순 정렬 지침 추가
  - [ ] 3.2 `build_crypto_keypoints_prompt()` 함수 구현
    - `_build_crypto_prompt_base()` 재사용
  - [ ] 3.3 `build_integrated_keypoints_prompt()` 함수 구현
    - `_build_integrated_prompt_base()` 재사용
    - Macro/Crypto Key Points를 입력으로 받아 통합 Key Points 생성
  - [ ] 3.4 `parse_keypoints_response()` 함수 구현
    - JSON 응답 파싱 (key_points, source_mapping)
    - 유효성 검증 (5~20개 범위, 필수 필드 존재 확인)

- [ ] 4.0 기존 Narrative 프롬프트 파라미터 확장
  - [ ] 4.1 `build_macro_narrative_prompt()`에 `key_points` 파라미터 추가
    - 기본값: None (하위 호환성 유지)
    - key_points가 있으면 데이터 섹션에 "### Key Points" 추가
  - [ ] 4.2 `build_crypto_narrative_prompt()`에 `key_points` 파라미터 추가
  - [ ] 4.3 `build_integrated_narrative_prompt()`에 `key_points` 파라미터 추가
  - [ ] 4.4 프롬프트에 "Key Points를 반드시 모두 반영하세요" 지침 추가

- [ ] 5.0 Insight Node 2단계 LLM 호출 로직 구현
  - [ ] 5.1 `src/workflows/nodes/insight_node.py` 파일 읽기 및 현재 LLM 호출 흐름 분석
  - [ ] 5.2 `_generate_keypoints()` 함수 구현
    - 입력: category, keywords, sources, economic_events
    - 출력: {"key_points": [...], "source_mapping": {...}}
    - 1단계 LLM 호출 (Key Points 생성)
  - [ ] 5.3 `_filter_sources_by_keypoints()` 함수 구현
    - source_mapping 기반으로 관련 소스만 필터링
    - 매핑 실패 시 전체 소스 반환 (fallback)
  - [ ] 5.4 `_generate_narrative_from_keypoints()` 함수 구현
    - 입력: category, key_points, filtered_sources, economic_events
    - 2단계 LLM 호출 (Narrative 생성)
  - [ ] 5.5 `_generate_segmented_narratives()` 함수 수정
    - Macro: Key Points 생성 → Narrative 생성 (2회 호출)
    - Crypto: Key Points 생성 → Narrative 생성 (2회 호출)
    - 통합: Key Points 생성 → Narrative 생성 (2회 호출)
  - [ ] 5.6 반환값에 key_points 포함하도록 수정
    - narratives["macro"] = {"key_points": [...], "paragraphs": [...]}
  - [ ] 5.7 에러 처리 및 fallback 로직 추가
    - Key Points 생성 실패 시 기존 방식으로 fallback

- [ ] 6.0 Report Builder 출력 형식 수정
  - [ ] 6.1 `src/report/report_builder.py` 파일 읽기 및 현재 출력 구조 분석
  - [ ] 6.2 Markdown 출력에 Key Points bullet list 추가
    - `#### Key Points` 섹션 추가
    - 각 포인트를 `•` bullet으로 나열
  - [ ] 6.3 Key Points 아래 `#### 분석` 섹션으로 narrative 출력
  - [ ] 6.4 JSON 출력 구조 변경
    - 기존: `narratives.macro: [문단1, 문단2]`
    - 변경: `narratives.macro: {key_points: [...], paragraphs: [...]}`
  - [ ] 6.5 Macro/Crypto/통합 모든 섹션에 동일한 형식 적용

- [ ] 7.0 설정 파일 정리 및 하위 호환성 처리
  - [ ] 7.1 `config.yml` 읽기 및 `enable_segmentation` 설정 확인
  - [ ] 7.2 `enable_segmentation` 설정을 deprecated로 표시 또는 제거
  - [ ] 7.3 deprecated 설정 사용 시 warning 로그 출력 로직 추가
  - [ ] 7.4 기존 단일 내러티브 모드 코드 정리/제거

- [ ] 8.0 테스트 및 검증
  - [ ] 8.1 프롬프트 리팩토링 단위 테스트 (공통 부분 추출 검증)
  - [ ] 8.2 Key Points 생성 프롬프트 단위 테스트
  - [ ] 8.3 소스 필터링 로직 단위 테스트
  - [ ] 8.4 2단계 LLM 호출 통합 테스트
  - [ ] 8.5 리포트 출력 형식 검증 테스트
  - [ ] 8.6 실제 데이터로 end-to-end 테스트 실행
  - [ ] 8.7 Key Points 개수가 5~20개 범위 내인지 검증
  - [ ] 8.8 LLM 호출 6회 모두 성공하는지 확인

- [ ] 9.0 문서화 및 마무리
  - [ ] 9.1 코드 변경사항에 대한 docstring 추가
  - [ ] 9.2 config.yml 주석 업데이트 (deprecated 설정 안내)
  - [ ] 9.3 PR 생성 및 코드 리뷰 요청

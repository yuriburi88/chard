## Relevant Files

- `src/workflows/prompts.py` - Key Points 생성 프롬프트 함수 추가 및 기존 narrative 프롬프트 수정
- `src/workflows/nodes/insight_node.py` - 2단계 LLM 호출 로직 구현, 소스 필터링 로직 추가
- `src/workflows/state.py` - insights 타입 정의에 key_points 필드 추가
- `src/report/report_builder.py` - Key Points 표시 로직 추가, Markdown/JSON 출력 수정
- `config.yml` - enable_segmentation 설정 제거 또는 deprecated 표시

### Notes

- 이 기능은 LLM 호출을 기존 3회에서 6회로 증가시킵니다
- Key Points 개수는 5~20개 범위에서 LLM이 자동 결정합니다
- 테스트 시 `pytest` 또는 `python -m pytest` 명령어를 사용합니다

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

- [ ] 2.0 Key Points 생성 프롬프트 구현
  - [ ] 2.1 `src/workflows/prompts.py` 파일 읽기 및 현재 프롬프트 구조 분석
  - [ ] 2.2 `build_macro_keypoints_prompt()` 함수 구현 (5~20개 Key Points, source_mapping 포함)
  - [ ] 2.3 `build_crypto_keypoints_prompt()` 함수 구현
  - [ ] 2.4 `build_integrated_keypoints_prompt()` 함수 구현 (Macro/Crypto Key Points 통합)
  - [ ] 2.5 `parse_keypoints_response()` 함수 구현 (JSON 응답 파싱 및 유효성 검증)

- [ ] 3.0 2단계 Narrative 프롬프트 수정
  - [ ] 3.1 기존 narrative 프롬프트 함수 분석
  - [ ] 3.2 Key Points를 입력으로 받는 새로운 narrative 프롬프트 구조 설계
  - [ ] 3.3 Macro/Crypto/통합 각각의 narrative 프롬프트 수정
  - [ ] 3.4 필터링된 소스만 전달하도록 프롬프트 템플릿 업데이트

- [ ] 4.0 Insight Node 2단계 LLM 호출 로직 구현
  - [ ] 4.1 `src/workflows/nodes/insight_node.py` 파일 읽기 및 현재 LLM 호출 흐름 분석
  - [ ] 4.2 `_generate_keypoints()` 함수 구현 (1단계 LLM 호출)
  - [ ] 4.3 `_filter_sources_by_keypoints()` 함수 구현 (소스 매핑 기반 필터링)
  - [ ] 4.4 `_generate_narrative_from_keypoints()` 함수 구현 (2단계 LLM 호출)
  - [ ] 4.5 기존 단일 LLM 호출 로직을 2단계 호출로 교체
  - [ ] 4.6 Macro → Crypto → 통합 순서로 각각 2단계 호출 적용
  - [ ] 4.7 에러 처리 및 fallback 로직 추가 (소스 매핑 실패 시 처리)

- [ ] 5.0 Report Builder 출력 형식 수정
  - [ ] 5.1 `src/report/report_builder.py` 파일 읽기 및 현재 출력 구조 분석
  - [ ] 5.2 Markdown 출력에 Key Points bullet list 추가 (`#### Key Points` 섹션)
  - [ ] 5.3 Key Points 아래 `#### 분석` 섹션으로 narrative 출력
  - [ ] 5.4 JSON 출력에 `key_points` 배열 필드 추가
  - [ ] 5.5 Macro/Crypto/통합 모든 섹션에 동일한 형식 적용

- [ ] 6.0 설정 파일 정리 및 하위 호환성 처리
  - [ ] 6.1 `config.yml` 읽기 및 `enable_segmentation` 설정 확인
  - [ ] 6.2 `enable_segmentation` 설정을 deprecated로 표시 또는 제거
  - [ ] 6.3 deprecated 설정 사용 시 warning 로그 출력 로직 추가
  - [ ] 6.4 기존 단일 내러티브 모드 코드 정리/제거

- [ ] 7.0 테스트 및 검증
  - [ ] 7.1 Key Points 생성 프롬프트 단위 테스트 작성
  - [ ] 7.2 소스 필터링 로직 단위 테스트 작성
  - [ ] 7.3 2단계 LLM 호출 통합 테스트 작성
  - [ ] 7.4 리포트 출력 형식 검증 테스트 작성
  - [ ] 7.5 실제 데이터로 end-to-end 테스트 실행
  - [ ] 7.6 Key Points 개수가 5~20개 범위 내인지 검증
  - [ ] 7.7 LLM 호출 6회 모두 성공하는지 확인

- [ ] 8.0 문서화 및 마무리
  - [ ] 8.1 코드 변경사항에 대한 docstring 추가
  - [ ] 8.2 config.yml 주석 업데이트 (deprecated 설정 안내)
  - [ ] 8.3 PR 생성 및 코드 리뷰 요청

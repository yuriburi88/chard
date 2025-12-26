# CHARD Workflows 모듈

LangGraph 기반 분석 파이프라인을 담당하는 모듈입니다.

## 구조

```
workflows/
├── __init__.py
├── langgraph_pipeline.py     # 메인 파이프라인 정의
├── state.py                  # 파이프라인 상태 관리
├── llm_client.py             # LLM 클라이언트 (Gemini)
├── prompts.py                # 프롬프트 템플릿
├── quality_metrics.py        # 품질 메트릭
├── keyword_categories.py     # 키워드 카테고리 정의
├── keyword_learner.py        # 동적 키워드 학습
├── dynamic_keywords.py       # 동적 키워드 관리
├── id_generator.py           # ID 생성기
├── nodes/                    # 파이프라인 노드
│   ├── collector_node.py
│   ├── keyword_extractor_node.py
│   ├── aggregator_node.py
│   └── insight_node.py
└── normalization/            # 정규화 모듈
    ├── embedding_cluster.py
    └── llm_verifier.py
```

## 파이프라인 흐름

```
                 ┌─────────────────┐
                 │  collector_node │
                 │ (데이터 청킹)    │
                 └────────┬────────┘
                          │
          ┌───────────────┴───────────────┐
          │ (각 청크에 대해 병렬 실행)        │
          ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│ keyword_extractor│             │ keyword_extractor│
│ (키워드 추출)     │     ...     │ (키워드 추출)     │
└────────┬────────┘             └────────┬────────┘
          │                               │
          └───────────────┬───────────────┘
                          ▼
                 ┌─────────────────┐
                 │ aggregator_node │
                 │ (키워드 통합)    │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  insight_node   │
                 │ (인사이트 생성)  │
                 └─────────────────┘
```

## 주요 컴포넌트

### AnalysisState (`state.py`)

파이프라인 전체에서 공유되는 상태 객체

```python
class AnalysisState(TypedDict):
    raw_records: list[dict]           # 원본 레코드
    chunks: list[list[dict]]          # 청크된 레코드
    chunk_keywords: list[list[dict]]  # 청크별 키워드
    aggregated_keywords: list[dict]   # 통합 키워드
    narratives: dict                  # 생성된 내러티브
    config: dict                      # 설정
    errors: list[str]                 # 에러 목록
```

### GeminiClient (`llm_client.py`)

Google Gemini API 클라이언트

**지원 모델:**
- `gemini-2.5-flash` (기본값)
- `gemini-2.5-pro`
- `gemini-2.0-flash`
- `gemini-2.0-pro`

```python
from src.workflows.llm_client import GeminiClient

client = GeminiClient(model="flash")
response = await client.generate_content_async(
    prompt="분석해주세요",
    response_format="json"
)
```

### 파이프라인 노드

#### collector_node
- 입력 데이터를 토큰 제한에 맞게 청킹
- 소스별 그룹화 및 시간순 정렬

#### keyword_extractor_node
- 각 청크에서 키워드 추출
- LLM을 사용하여 중요 키워드 식별

#### aggregator_node
- 여러 청크의 키워드를 통합
- 동의어 그룹화 및 중복 제거
- 임베딩 기반 클러스터링 (선택적)
- LLM 검증 (선택적)

#### insight_node
- 통합된 키워드를 기반으로 내러티브 생성
- 트레이딩 인사이트 제공

## 설정

```yaml
llm:
  model: "gemini-2.5-flash"
  provider: "google"
  max_tokens: 8000
  chunk_size: 50000

normalization:
  embedding_threshold: 0.9
  dbscan_min_samples: 2

narrative:
  enable_segmentation: true
  crypto_paragraphs: 2
  integrated_paragraphs: 3

output:
  top_keywords_count: 10
  summary_paragraphs: 4
```

## 사용 예시

```python
from src.workflows.langgraph_pipeline import create_analysis_pipeline, run_pipeline

# 파이프라인 생성
pipeline = create_analysis_pipeline()

# 초기 상태 설정
initial_state = {
    "raw_records": collected_data,
    "config": config_dict,
    "errors": []
}

# 파이프라인 실행
final_state = await run_pipeline(pipeline, initial_state)

# 결과 확인
keywords = final_state["aggregated_keywords"]
narratives = final_state["narratives"]
```

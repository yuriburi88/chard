# 키워드 추출 및 필터링 로직 전체 분석

## 개요

CHARD 시스템은 RSS 뉴스와 텔레그램 메시지에서 키워드를 추출하고, 중복을 제거하며, 최종적으로 상위 키워드를 선정하는 4단계 파이프라인을 사용합니다.

---

## 전체 파이프라인 (4단계)

```
[1단계: 수집] → [2단계: 추출] → [3단계: 병합] → [4단계: 분류]
CollectorNode → KeywordExtractorNode → AggregatorNode → Categorization
```

---

## 1단계: 데이터 수집 (CollectorNode)

### 파일 위치
- `src/workflows/nodes/collector_node.py`
- `src/collectors/rss_collector.py`
- `src/collectors/telegram_collector.py`
- `src/collectors/economic_calendar_collector.py`

### 처리 과정
1. **RSS 뉴스 수집**
   - 설정된 RSS 피드에서 기사 수집
   - 필터링: `hours_back` 시간 이내의 기사만
   - 각 기사에 `source`, `timestamp`, `text`, `meta` 필드 포함

2. **텔레그램 메시지 수집**
   - 설정된 텔레그램 채널에서 메시지 수집
   - 필터링: `hours_back` 시간 이내의 메시지만
   - 긴 메시지는 `split_long_messages` 설정에 따라 분할

3. **Economic Calendar 수집**
   - 경제 지표 발표 일정 수집
   - 중요도 필터링: `importance` 설정 (high/medium/low)
   - Macro 키워드 추출에 활용

### 출력
- `raw_records`: 수집된 모든 레코드 리스트
- `chunks`: 레코드를 청크로 분할 (청크당 50,000 토큰)

---

## 2단계: 키워드 추출 (KeywordExtractorNode)

### 파일 위치
- `src/workflows/nodes/keyword_extractor_node.py`
- `src/workflows/prompts.py` (프롬프트 생성)

### 처리 과정

#### 2.1 청크 병렬 처리
```yaml
parallel_concurrency: 3  # 최대 3개 청크를 동시 처리
```
- **무제한 모드** (`parallel_concurrency=0`): 모든 청크를 동시 처리
- **제한 모드** (`parallel_concurrency=N`): 최대 N개 청크만 동시 처리 (Semaphore 사용)

#### 2.2 LLM 기반 키워드 추출
각 청크마다 Gemini API를 호출하여 키워드 추출:

**프롬프트 요구사항** (`build_keyword_extraction_prompt`):
1. **3개 카테고리로 분류**:
   - `macro_keywords`: 금리, 연준, GDP, 인플레이션, 실업률 등
   - `crypto_native_keywords`: 비트코인, 이더리움, DeFi, NFT 등
   - `crypto_macro_keywords`: 비트코인 ETF, 기관투자, 규제(SEC) 등

2. **각 카테고리당 최소 3개, 권장 5~10개 키워드 추출**

3. **각 키워드 정보**:
   - `term`: 키워드 용어
   - `score`: 중요도 점수 (0-100, 50점 이상만)
   - `evidence_ids`: 해당 키워드를 지지하는 레코드 ID 리스트
   - `sources`: RSS 기사 제목 또는 텔레그램 채널명

#### 2.3 Economic Calendar 활용
- Macro 키워드 추출 시 Economic Calendar 이벤트를 참고
- 최대 20개 이벤트를 프롬프트에 포함

### 출력
- `extracted_keywords`: 모든 청크에서 추출된 키워드 리스트
  - 예: 5개 청크 × 18개 키워드 = 85개 키워드

---

## 3단계: 키워드 병합 및 필터링 (AggregatorNode)

### 파일 위치
- `src/workflows/nodes/aggregator_node.py`
- `src/workflows/normalization/embedding_cluster.py`
- `src/workflows/normalization/llm_verifier.py`

### 처리 단계

#### 3.1 임베딩 기반 DBSCAN 클러스터링

**목적**: 의미적으로 유사한 키워드를 클러스터로 묶기

**알고리즘**: DBSCAN (Density-Based Spatial Clustering)
```python
eps = 1.0 - embedding_threshold  # 거리 임계값
min_samples = dbscan_min_samples  # 최소 샘플 수
metric = "cosine"  # 코사인 거리 사용
```

**현재 설정** ([config.yml](config.yml#L226-227)):
```yaml
embedding_threshold: 0.90  # 유사도 0.90 이상만 같은 클러스터
dbscan_min_samples: 2      # 최소 2개 샘플이 있어야 클러스터 형성
```

**예시**:
- "비트코인", "BTC", "Bitcoin" → 같은 클러스터 (유사도 0.95)
- "비트코인", "금리" → 다른 클러스터 (유사도 0.60)

**클러스터링 결과**:
- 85개 키워드 → 약 30~50개 클러스터로 축소

#### 3.2 클러스터별 스코어 재계산 (`aggregate_clustered_keywords`)

각 클러스터에 대해:
1. **대표 키워드 선정**: 클러스터 내 최고 점수 키워드
2. **메타데이터 통합**:
   - `original_variants`: 클러스터 내 모든 변형 용어
   - `score`: 클러스터 내 평균 점수
   - `evidence_ids`: 모든 증거 ID 병합 (최대 3개)
   - `sources`: 모든 출처 병합
   - `occurrence_count`: 클러스터 내 키워드 개수

**스코어 재계산 공식** (`recalculate_cluster_scores`):
```python
final_score = base_mean × source_factor × occurrence_factor × evidence_factor

source_factor = 1.0 + (source_count × 0.1)
occurrence_factor = 1.0 + (max(occurrence_count - 1, 0) × 0.05)
evidence_factor = 1.0 + (evidence_count × 0.02)
```

**예시**:
- base_mean = 80
- source_count = 5 → source_factor = 1.5
- occurrence_count = 3 → occurrence_factor = 1.1
- evidence_count = 3 → evidence_factor = 1.06
- **final_score = 80 × 1.5 × 1.1 × 1.06 = 140.04**

#### 3.3 상위 후보 키워드 선정 (`_select_top_keywords`)

**단계 1**: 후보 키워드 선정
```yaml
candidate_limit = max(30, top_keywords_count)  # 최소 30개
```
- 점수 기준 상위 30개 선정
- `include_ties=True`: 동점자 모두 포함

**단계 2**: 1차 최상위 키워드 선정
```yaml
top_keywords_count: 10  # 최종 10개
```
- 점수 기준 상위 10개 선정
- `include_ties=False`: 정확히 10개만

#### 3.4 LLM 동의어 검증 (선택적)

**설정** ([config.yml](config.yml#L228-229)):
```yaml
llm_verification_enabled: true
llm_verification_top_n: 30
```

**프롬프트** (`build_synonym_verification_prompt`):
- 상위 30개 후보를 LLM에 전달
- **목적**: 의미적으로 동일한 용어를 추가로 병합
- **예**: "연준", "Fed", "연방준비제도" → "연준(Fed)"로 병합

**병합 로직** (`merge_llm_groups_with_keywords`):
1. LLM이 그룹 정보 반환: `groups` (병합 대상), `standalone` (독립 용어)
2. 각 그룹의 키워드 메타데이터 병합
3. 점수 기준 상위 `top_n=10`개 선정

### 출력
- `aggregated_keywords`: 최종 상위 10개 키워드

---

## 4단계: 카테고리 분류 및 동적 학습

### 파일 위치
- `src/workflows/keyword_categories.py`
- `src/workflows/keyword_learner.py`
- `src/workflows/dynamic_keywords.py`

### 4.1 카테고리 분류 (`KeywordCategorizer`)

**목적**: 최종 키워드를 Macro/Crypto Native/Crypto-Macro로 분류

**분류 로직**:
1. **고정 키워드 매칭**: 미리 정의된 키워드 리스트와 비교
2. **동적 키워드 매칭**: 캐시에 저장된 동적 학습 키워드와 비교
3. **LLM 분류**: 위 두 방법으로 분류되지 않은 키워드는 LLM에게 질의

**차등 임계값** ([config.yml](config.yml#L243-246)):
```yaml
category_thresholds:
  macro: 0.4           # 거시경제: 중간 수준
  crypto_native: 0.3   # 암호화폐 고유: 관대
  crypto_macro: 0.5    # 교차 이슈: 엄격
```

**멀티 레이블 분류**: 하나의 키워드가 여러 카테고리에 속할 수 있음
- 예: "비트코인 ETF" → `crypto_native` + `crypto_macro`

### 4.2 동적 키워드 학습 (`KeywordLearner`)

**목적**: 자주 나오는 키워드를 자동으로 학습하여 고정 키워드 리스트에 추가

**설정** ([config.yml](config.yml#L249-254)):
```yaml
dynamic_keywords:
  enabled: true
  learning_top_n: 30      # 상위 30개 키워드 학습
  min_frequency: 4        # 최소 4회 출현
  ttl_hours: 24           # 24시간 유효
  cache_file: "dynamic_keywords_cache.json"
```

**학습 로직**:
1. 상위 30개 키워드 중 `min_frequency ≥ 4`인 키워드만 선택
2. LLM에게 각 키워드의 카테고리 분류 요청
3. 결과를 캐시 파일에 저장 (24시간 유효)

**캐시 예시** (`dynamic_keywords_cache.json`):
```json
{
  "비트코인 ETF": {
    "categories": ["crypto_native", "crypto_macro"],
    "confidence": 0.95,
    "last_seen": "2025-12-17T12:00:00Z"
  }
}
```

### 출력
- 각 키워드에 `categories` 필드 추가
- 카테고리별 키워드 개수:
  - `macro`: N개
  - `crypto_native`: M개
  - `crypto_macro`: K개

---

## 현재 설정값 요약

### 수집 단계
```yaml
collection_period:
  mode: days_back
  days_back: 1
```

### 키워드 추출
```yaml
llm:
  model: gemini-2.5-flash
  temperature: 0.1
  max_tokens: 8000
  parallel_concurrency: 3  # 최대 3개 청크 동시 처리
```

### 클러스터링 및 병합
```yaml
normalization:
  embedding_threshold: 0.90  # 유사도 0.90 이상만 병합
  dbscan_min_samples: 2
  llm_verification_enabled: true
  llm_verification_top_n: 30
```

### 카테고리 분류
```yaml
narrative:
  category_thresholds:
    macro: 0.4
    crypto_native: 0.3
    crypto_macro: 0.5
  dynamic_keywords:
    enabled: true
    learning_top_n: 30
    min_frequency: 4
    ttl_hours: 24
```

### 최종 출력
```yaml
output:
  top_keywords_count: 10  # 최종 10개 키워드
```

---

## 주요 필터링 포인트 정리

### 1. 시간 필터링 (수집 단계)
- RSS: `hours_back: 24` (24시간 이내 기사만)
- Telegram: `hours_back: 24`
- Economic Calendar: `days_back: 7`, `days_forward: 14`

### 2. 점수 필터링 (추출 단계)
- **최소 점수**: 50점 이상만 추출
- LLM이 각 키워드에 0-100점 부여

### 3. 클러스터링 필터링 (병합 단계)
- **유사도 임계값**: 0.90 이상만 같은 클러스터로 병합
- **최소 샘플**: 2개 이상 있어야 클러스터 형성

### 4. 순위 필터링 (최종 선정)
- **후보**: 상위 30개
- **LLM 검증**: 30개 → 병합 → 상위 10개
- **최종 출력**: 10개

### 5. 카테고리 필터링
- **차등 임계값**:
  - Macro: 0.4 (관대)
  - Crypto Native: 0.3 (매우 관대)
  - Crypto-Macro: 0.5 (엄격)
- **동적 학습 필터**: 최소 4회 출현

---

## 최근 수정 사항 (2025-12-17)

### 문제: Macro 내러티브 누락
- **원인**: `embedding_threshold: 0.75`가 너무 낮아 85개 키워드가 모두 1개 클러스터로 병합됨
- **해결**: `embedding_threshold: 0.75 → 0.90` (엄격하게 변경)
- **효과**: 서로 다른 카테고리 키워드가 분리되어 Macro/Crypto Native/Crypto-Macro 각각 유지됨

### 파라미터 변경
```yaml
# 변경 전
embedding_threshold: 0.75
dbscan_min_samples: 3

# 변경 후
embedding_threshold: 0.90  # 더 엄격하게
dbscan_min_samples: 2      # 더 관대하게
```

---

## 참고 파일 경로

### 주요 노드
- [collector_node.py](src/workflows/nodes/collector_node.py)
- [keyword_extractor_node.py](src/workflows/nodes/keyword_extractor_node.py)
- [aggregator_node.py](src/workflows/nodes/aggregator_node.py)

### 정규화 모듈
- [embedding_cluster.py](src/workflows/normalization/embedding_cluster.py)
- [llm_verifier.py](src/workflows/normalization/llm_verifier.py)

### 카테고리 분류
- [keyword_categories.py](src/workflows/keyword_categories.py)
- [keyword_learner.py](src/workflows/keyword_learner.py)
- [dynamic_keywords.py](src/workflows/dynamic_keywords.py)

### 프롬프트
- [prompts.py](src/workflows/prompts.py)

### 설정
- [config.yml](config.yml)

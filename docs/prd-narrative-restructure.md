# PRD: 내러티브 리포트 2중 구조 전환

## 1. Introduction/Overview

CHARD 프로젝트의 내러티브 리포트 생성 방식을 변경합니다. 현재는 LLM이 키워드와 뉴스 소스를 받아 바로 산문 형식의 내러티브를 생성하지만, 이를 2단계 구조로 전환합니다:

1. **1단계 (Key Points)**: 주요 이벤트와 분석 포인트를 bullet point 형식으로 나열
2. **2단계 (Narrative)**: Key Points와 관련 원본 소스를 기반으로 통합 내러티브 작성

이 변경을 통해 리포트의 가독성을 높이고, 핵심 정보를 빠르게 파악한 후 상세 분석을 읽을 수 있는 구조를 제공합니다.

---

## 2. Goals

1. **가독성 향상**: 핵심 포인트를 먼저 bullet point로 제시하여 빠른 정보 파악 가능
2. **분석 품질 향상**: Key Points를 먼저 정리함으로써 더 구조화된 내러티브 생성
3. **유연한 Key Points 개수**: 뉴스 양에 비례하여 5~20개 범위에서 LLM이 자동 판단
4. **일관된 구조**: 모든 내러티브(Macro/Crypto/통합)에 동일한 2중 구조 적용

---

## 3. User Stories

### 트레이더/투자자
- 사용자로서, 리포트를 열었을 때 핵심 이벤트를 bullet point로 빠르게 스캔하고 싶습니다.
- 사용자로서, 관심 있는 포인트에 대한 상세 분석을 내러티브에서 확인하고 싶습니다.

### 개발자
- 개발자로서, 내러티브 생성 로직이 명확하게 2단계로 분리되어 디버깅과 품질 개선이 용이해야 합니다.
- 개발자로서, Key Points와 Narrative의 연관성을 추적할 수 있어야 합니다.

---

## 4. Functional Requirements

### 4.1 Key Points 생성 (1단계)

| 번호 | 요구사항 |
|------|----------|
| FR-1.1 | Macro, Crypto, 통합 내러티브 각각에 대해 별도의 Key Points를 생성한다 |
| FR-1.2 | Key Points 개수는 5~20개 범위에서 LLM이 뉴스 양과 중요도에 따라 자동 결정한다 |
| FR-1.3 | 각 Key Point는 한 문장으로 핵심 이벤트/분석을 명확히 표현한다 |
| FR-1.4 | Key Point에는 가능한 경우 정량적 데이터를 포함한다 (%, 금액, 지수 등) |
| FR-1.5 | Key Points는 중요도/시간순으로 정렬되어야 한다 |

### 4.2 Narrative 생성 (2단계)

| 번호 | 요구사항 |
|------|----------|
| FR-2.1 | 2단계 LLM 호출 시 1단계에서 생성한 Key Points를 입력으로 전달한다 |
| FR-2.2 | Key Points와 관련된 원본 뉴스 소스만 필터링하여 함께 전달한다 |
| FR-2.3 | Narrative는 Key Points의 내용을 통합하여 자연스러운 산문으로 작성한다 |
| FR-2.4 | Narrative는 기존과 동일하게 과거 분석 / 미래 전망 구조를 유지한다 |

### 4.3 LLM 호출 구조

| 번호 | 요구사항 |
|------|----------|
| FR-3.1 | Macro 내러티브: Key Points 생성 (1회) → Narrative 생성 (1회) = 총 2회 |
| FR-3.2 | Crypto 내러티브: Key Points 생성 (1회) → Narrative 생성 (1회) = 총 2회 |
| FR-3.3 | 통합 내러티브: Key Points 생성 (1회) → Narrative 생성 (1회) = 총 2회 |
| FR-3.4 | 전체 LLM 호출: 기존 3회 → 6회로 증가 |

### 4.4 리포트 출력 형식

| 번호 | 요구사항 |
|------|----------|
| FR-4.1 | 각 섹션(Macro/Crypto/통합)에서 Key Points를 bullet point로 먼저 표시한다 |
| FR-4.2 | Key Points 아래에 Narrative 문단을 표시한다 |
| FR-4.3 | JSON 리포트에도 key_points 필드를 추가한다 |

### 4.5 기존 구조 전환

| 번호 | 요구사항 |
|------|----------|
| FR-5.1 | 기존 단일 내러티브 모드(`enable_segmentation=false`)를 제거한다 |
| FR-5.2 | 모든 내러티브 생성은 2중 구조(Key Points → Narrative)로 통일한다 |
| FR-5.3 | `enable_segmentation` 설정을 deprecated 처리하거나 제거한다 |

---

## 5. Non-Goals (Out of Scope)

- Key Points에 대한 사용자 편집/수정 기능
- Key Points별 중요도 점수 표시
- 실시간 스트리밍 출력 (기존과 동일하게 배치 처리)
- 다국어 지원 변경 (기존 한국어 유지)
- UI/대시보드 변경 (CLI 리포트 형식만 변경)

---

## 6. Design Considerations

### 6.1 리포트 출력 형식 예시

```markdown
## 시장 내러티브 요약

### Macro 내러티브

#### Key Points
• Fed 금리 동결 기조 유지, 2025년 상반기 인하 기대 후퇴
• 미국 11월 CPI 2.7%로 예상(2.6%) 상회, 인플레이션 우려 지속
• 10년물 국채 수익률 4.2%로 10bp 상승
• 달러지수 106.5로 강세 유지, 신흥국 통화 압박
• 다음 주 FOMC 회의 주목, 점도표 상향 조정 가능성

#### 분석
Fed의 금리 동결 기조가 유지되는 가운데, 11월 CPI가 2.7%로 시장 예상치를
상회하며 인플레이션 우려가 재부각되었습니다. 이에 따라 10년물 국채 수익률은
4.2%로 10bp 상승했으며...

### Crypto 내러티브

#### Key Points
• 비트코인 $95,000 저항선 테스트, 24시간 거래량 $400억
• 비트코인 현물 ETF 순유입 $3억, 기관 수요 지속
• 이더리움 Pectra 업그레이드 Q1 예정, 스테이킹 개선 기대
• Arbitrum TVL 15% 증가, L2 경쟁 심화
• SEC 스테이킹 ETF 심사 진행 중, 1월 결정 예상

#### 분석
비트코인이 $95,000 저항선을 테스트하는 가운데, 현물 ETF로의 기관 자금
유입이 $3억을 기록하며 상승 모멘텀을 지지하고 있습니다...
```

### 6.2 JSON 출력 구조

```json
{
  "insights": {
    "narratives": {
      "macro": {
        "key_points": [
          "Fed 금리 동결 기조 유지, 2025년 상반기 인하 기대 후퇴",
          "미국 11월 CPI 2.7%로 예상(2.6%) 상회"
        ],
        "paragraphs": [
          "문단1: 과거 분석...",
          "문단2: 미래 전망..."
        ]
      },
      "crypto": {
        "key_points": ["..."],
        "paragraphs": ["..."]
      },
      "integrated": {
        "key_points": ["..."],
        "paragraphs": ["..."]
      }
    },
    "trading_insights": { ... }
  }
}
```

### 6.3 LLM 프롬프트 구조

**1단계: Key Points 생성 프롬프트**
```
입력: 키워드 + 원본 뉴스 소스
출력: {
  "key_points": ["포인트1", "포인트2", ...],
  "source_mapping": {
    "포인트1": ["source_id_1", "source_id_2"],
    ...
  }
}
```

**2단계: Narrative 생성 프롬프트**
```
입력: Key Points + 관련 원본 소스 (필터링됨)
출력: {
  "narrative": ["문단1", "문단2"]
}
```

---

## 7. Technical Considerations

### 7.1 수정 대상 파일

| 파일 | 수정 내용 |
|------|----------|
| `src/workflows/prompts.py` | Key Points 생성 프롬프트 함수 추가, 기존 narrative 프롬프트 수정 |
| `src/workflows/nodes/insight_node.py` | 2단계 LLM 호출 로직 구현, 소스 필터링 로직 추가 |
| `src/workflows/state.py` | `insights` 타입 정의에 `key_points` 필드 추가 |
| `src/report/report_builder.py` | Key Points 표시 로직 추가, Markdown/JSON 출력 수정 |
| `config.yml` | `enable_segmentation` 설정 제거 또는 deprecated 표시 |

### 7.2 새로운 함수

```python
# prompts.py에 추가
def build_macro_keypoints_prompt(keywords, source_highlights, economic_events) -> str
def build_crypto_keypoints_prompt(keywords, source_highlights, economic_events) -> str
def build_integrated_keypoints_prompt(macro_keypoints, crypto_keypoints, all_keywords) -> str
def parse_keypoints_response(response_text, category) -> dict

# insight_node.py에 추가
def _filter_sources_by_keypoints(sources, keypoint_source_mapping) -> list
def _generate_keypoints(category, keywords, sources, economic_events) -> dict
def _generate_narrative_from_keypoints(category, keypoints, filtered_sources) -> list
```

### 7.3 LLM 호출 흐름

```
[기존]
Macro 키워드 → LLM → Macro Narrative (1회)
Crypto 키워드 → LLM → Crypto Narrative (1회)
전체 → LLM → 통합 Narrative (1회)
총 3회

[변경 후]
Macro 키워드 → LLM → Key Points (1회) → LLM → Narrative (1회) = 2회
Crypto 키워드 → LLM → Key Points (1회) → LLM → Narrative (1회) = 2회
전체 → LLM → Key Points (1회) → LLM → Narrative (1회) = 2회
총 6회
```

### 7.4 소스 필터링 로직

Key Points 생성 시 각 포인트가 어떤 소스에서 유래했는지 매핑을 함께 반환:
```json
{
  "key_points": ["Fed 금리 동결 발표", "CPI 예상 상회"],
  "source_mapping": {
    "Fed 금리 동결 발표": ["source_001", "source_003"],
    "CPI 예상 상회": ["source_002"]
  }
}
```

2단계 Narrative 생성 시 해당 source_id에 해당하는 원본 소스만 필터링하여 전달.

### 7.5 하위 호환성

- `enable_segmentation=false` 설정 사용 시 warning 로그 출력 후 새 구조로 동작
- 기존 `insights.narrative_summary` 필드는 deprecated, `insights.narratives` 사용 권장
- 기존 리포트 파싱 코드가 있다면 `key_points` 필드 추가에 대응 필요

---

## 8. Success Metrics

| 지표 | 목표 |
|------|------|
| Key Points 생성 성공률 | 95% 이상 (5~20개 범위 내) |
| 소스 매핑 정확도 | 90% 이상 (Key Point와 관련 소스 연결) |
| 리포트 가독성 | 사용자 피드백 기반 개선 확인 |
| LLM 호출 안정성 | 6회 호출 모두 성공률 95% 이상 |

---

## 9. Open Questions

1. **Key Points 정렬 기준**: 중요도순 vs 시간순 vs 카테고리순 중 어떤 것을 우선할지?
2. **소스 매핑 실패 시 처리**: Key Point에 매핑된 소스가 없을 경우 전체 소스를 전달할지, 해당 Key Point를 제외할지?
3. **통합 내러티브 Key Points**: Macro/Crypto Key Points를 합치는 방식 vs 새로 생성하는 방식 중 선택
4. **비용 증가 대응**: LLM 호출이 2배 증가하는데, 토큰 사용량 최적화 방안이 필요한지?

---

## Appendix: 현재 vs 변경 후 비교

### 현재 구조
```
키워드 + 소스 → [LLM] → 내러티브 문단
                         ↓
                    리포트 출력:
                    ## Macro 내러티브
                    문단1...
                    문단2...
```

### 변경 후 구조
```
키워드 + 소스 → [LLM 1차] → Key Points + 소스 매핑
                              ↓
Key Points + 필터링된 소스 → [LLM 2차] → 내러티브 문단
                                          ↓
                                     리포트 출력:
                                     ## Macro 내러티브
                                     #### Key Points
                                     • 포인트1
                                     • 포인트2
                                     #### 분석
                                     문단1...
                                     문단2...
```

---

*문서 작성일: 2024-12-29*
*버전: 1.0*

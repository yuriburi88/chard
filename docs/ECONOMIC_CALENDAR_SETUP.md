# Economic Calendar 통합 가이드

CHARD에 Investing.com Economic Calendar 데이터를 통합하는 방법입니다.

## 1. 라이브러리 설치

```bash
pip install investpy
```

또는 `requirements.txt`에 추가:
```
investpy>=1.0.8
```

## 2. 설정 (config.yml)

`config.yml`에 Economic Calendar 설정이 이미 추가되어 있습니다:

```yaml
economic_calendar:
  enabled: true                  # 활성화 여부
  countries:                     # 수집할 국가
    - united states
    - china
    - japan
    - eurozone
  importance: high               # 중요도: high, medium, low, all
  days_back: 7                   # 과거 며칠 데이터
```

## 3. 파이프라인 통합

Economic Calendar 데이터를 기존 RSS/Telegram 데이터와 함께 수집하려면,
CollectorNode를 수정해야 합니다.

### 예시 코드 (main.py 또는 파이프라인 진입점)

```python
from src.collectors.economic_calendar_collector import collect_economic_calendar

# Economic Calendar 데이터 수집
if config.get("economic_calendar", {}).get("enabled", False):
    ec_config = config["economic_calendar"]

    economic_records = await collect_economic_calendar(
        countries=ec_config.get("countries"),
        importance=ec_config.get("importance", "high"),
        days_back=ec_config.get("days_back", 7)
    )

    logger.info(f"Economic Calendar: {len(economic_records)}개 이벤트 수집")

    # 기존 raw_records에 추가
    raw_records.extend(economic_records)
```

## 4. 수집되는 데이터 형식

Economic Calendar 데이터는 다음과 같은 형식으로 정규화됩니다:

```python
{
    "source": "economic_calendar",
    "timestamp": "2025-12-16T14:30:00+00:00",
    "text": "[United States] Consumer Price Index (CPI) 발표: 0.2% (예상 0.3% 하회) 이전: 0.4% [중요]",
    "meta": {
        "event_name": "Consumer Price Index (CPI)",
        "country": "United States",
        "importance": "High",
        "actual": "0.2%",
        "forecast": "0.3%",
        "previous": "0.4%",
        "impact": "positive",  # positive, negative, neutral
        "currency": "USD",
        "event_time": "2025-12-16T14:30:00+00:00"
    }
}
```

## 5. 주요 기능

### 자동 영향 분석
- **actual vs forecast 비교**: 실제 발표값과 예상치를 비교하여 시장 영향 판단
- **경제 지표별 방향성**: CPI(인플레이션)는 예상보다 높으면 부정적, GDP/고용은 예상보다 높으면 긍정적

### Macro 키워드 추출 강화
- 경제 지표 이름이 자연어로 포함되어 LLM이 쉽게 키워드 추출 가능
- 예: "Consumer Price Index", "GDP", "Non-Farm Payrolls" 등

### 내러티브 분석 개선
- 거시경제 이벤트의 타임라인과 영향도를 명확히 파악 가능
- 예상치 대비 실제값 차이로 시장 반응 예측 가능

## 6. 대안 데이터 소스

`investpy`가 불안정하거나 사용이 어려운 경우, 다음 대안을 고려하세요:

### Trading Economics API (유료, 안정적)
- https://tradingeconomics.com/api
- 월 $50~$500 (플랜에 따라)
- 매우 안정적이고 포괄적인 데이터

### Alpha Vantage (무료, 제한적)
- https://www.alphavantage.co/
- 무료 API 키 제공
- Economic Indicators API 사용 가능

### FRED API (무료, 미국 중심)
- https://fred.stlouisfed.org/
- Federal Reserve 공식 데이터
- 미국 경제 지표에 최적화

## 7. 문제 해결

### investpy 설치 오류
```bash
# pandas 버전 문제가 있을 수 있음
pip install pandas==1.5.3
pip install investpy
```

### 데이터 수집 실패
- `economic_calendar.enabled: false`로 비활성화하면 기존 기능은 정상 작동
- 로그 확인: `[EconomicCalendarCollector]` 태그 검색

### 키워드 추출 시 무시됨
- Macro 카테고리 키워드로 자동 분류되어야 함
- 프롬프트에 경제 지표 예시가 포함되어 있음 (CPI, GDP, 고용 등)

## 8. 향후 개선 사항

- [ ] 경제 지표별 가중치 설정 (CPI > PMI > 소비자신뢰지수 등)
- [ ] 과거 데이터와 비교하여 트렌드 분석
- [ ] 시장 반응 데이터(주가, 금리 변화) 연계
- [ ] 실시간 알림 기능 (중요 지표 발표 전)

## 9. 참고 자료

- [investpy Documentation](https://investpy.readthedocs.io/)
- [Investing.com Economic Calendar](https://www.investing.com/economic-calendar/)
- [Trading Economics API](https://tradingeconomics.com/api)

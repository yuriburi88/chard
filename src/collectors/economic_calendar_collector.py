"""
Economic Calendar Collector

Investing.com 등에서 경제 지표 발표 일정과 결과를 수집하는 모듈입니다.
- 주요 경제 지표 (CPI, GDP, 고용지표 등) 수집
- 실제 발표값, 예상값, 이전값 비교
- 시장 영향도(importance) 분류
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class EconomicEvent:
    """경제 지표 이벤트"""

    event_name: str
    country: str
    timestamp: datetime
    importance: str  # High, Medium, Low
    actual: str | None
    forecast: str | None
    previous: str | None
    currency: str
    source: str = "economic_calendar"


class EconomicCalendarCollector:
    """
    Economic Calendar 수집기

    경제 지표 발표 일정과 결과를 수집합니다.
    """

    def __init__(self):
        """Economic Calendar 수집기 초기화"""
        self._check_dependencies()

    def _check_dependencies(self):
        """필요한 라이브러리 확인"""
        try:
            import investpy

            self.investpy = investpy
        except ImportError:
            logger.warning(
                "[EconomicCalendarCollector] investpy 라이브러리가 설치되지 않았습니다. "
                "설치하려면: pip install investpy"
            )
            self.investpy = None

    async def collect(
        self,
        countries: list[str] = None,
        importance: str = "high",
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        경제 지표 데이터를 수집합니다.

        Args:
            countries: 수집할 국가 리스트 (기본값: ["united states", "china", "japan", "eurozone"])
            importance: 중요도 필터 (high, medium, low, all)
            from_date: 시작 날짜 (기본값: 7일 전)
            to_date: 종료 날짜 (기본값: 오늘)

        Returns:
            정규화된 레코드 리스트 (raw_records 형식과 호환)
        """
        if self.investpy is None:
            logger.error(
                "[EconomicCalendarCollector] investpy가 설치되지 않아 수집을 건너뜁니다."
            )
            return []

        # 기본값 설정
        if countries is None:
            countries = [
                "united states",
                "china",
                "japan",
                "eurozone",
                "canada",
                "australia",
                "united kingdom",
                "germany",
                "france",
                "south korea",
            ]

        if from_date is None:
            from_date = datetime.now(timezone.utc) - timedelta(days=7)

        if to_date is None:
            to_date = datetime.now(timezone.utc)

        logger.info(
            f"[Economic Calendar 수집 시작] "
            f"국가: {countries}, 중요도: {importance}, "
            f"기간: {from_date.date()} ~ {to_date.date()}"
        )

        # asyncio.to_thread로 블로킹 호출을 비동기로 처리
        events = await asyncio.to_thread(
            self._fetch_calendar,
            countries=countries,
            importance=importance,
            from_date=from_date,
            to_date=to_date,
        )

        # raw_records 형식으로 변환
        records = self._normalize_to_records(events)

        logger.info(
            f"[Economic Calendar 수집 완료] " f"총 {len(records)}개 이벤트 수집"
        )

        return records

    def _fetch_calendar(
        self,
        countries: list[str],
        importance: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[EconomicEvent]:
        """
        investpy를 사용하여 경제 지표 데이터를 가져옵니다.

        (블로킹 함수 - asyncio.to_thread로 호출)
        """
        events = []

        # 날짜 형식 변환 (investpy는 'dd/mm/yyyy' 형식 사용)
        from_str = from_date.strftime("%d/%m/%Y")
        to_str = to_date.strftime("%d/%m/%Y")

        for country in countries:
            try:
                logger.info(f"[Economic Calendar] {country} 데이터 수집 중...")

                # investpy.economic_calendar 호출
                calendar_df = self.investpy.economic_calendar(
                    countries=[country],
                    from_date=from_str,
                    to_date=to_str,
                    importances=[importance] if importance != "all" else None,
                )

                if calendar_df.empty:
                    logger.warning(f"[Economic Calendar] {country}: 데이터 없음")
                    continue

                # DataFrame을 EconomicEvent로 변환
                for _, row in calendar_df.iterrows():
                    event = self._parse_event(row, country)
                    if event:
                        events.append(event)

                logger.info(
                    f"[Economic Calendar] {country}: {len(calendar_df)}개 이벤트 수집"
                )

            except Exception as exc:
                logger.error(
                    f"[Economic Calendar] {country} 수집 실패: {exc}", exc_info=True
                )

        return events

    def _parse_event(self, row, country: str) -> EconomicEvent | None:
        """DataFrame row를 EconomicEvent로 변환"""
        try:
            # 필수 필드 확인
            event_name = row.get("event", "Unknown Event")
            date_str = row.get("date", "")
            time_str = row.get("time", "")

            # 타임스탬프 생성
            if date_str and time_str:
                datetime_str = f"{date_str} {time_str}"
                timestamp = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                # 시간 정보가 없으면 현재 시간 사용
                timestamp = datetime.now(timezone.utc)

            return EconomicEvent(
                event_name=event_name,
                country=country.title(),
                timestamp=timestamp,
                importance=row.get("importance", "Medium"),
                actual=(
                    str(row.get("actual", ""))
                    if row.get("actual") is not None
                    else None
                ),
                forecast=(
                    str(row.get("forecast", ""))
                    if row.get("forecast") is not None
                    else None
                ),
                previous=(
                    str(row.get("previous", ""))
                    if row.get("previous") is not None
                    else None
                ),
                currency=row.get("currency", "USD"),
            )

        except Exception as exc:
            logger.warning(f"[Economic Calendar] 이벤트 파싱 실패: {exc}")
            return None

    def _normalize_to_records(
        self, events: list[EconomicEvent]
    ) -> list[dict[str, Any]]:
        """
        EconomicEvent를 raw_records 형식으로 변환

        기존 RSS/Telegram과 동일한 형식:
        {
            "source": "economic_calendar",
            "timestamp": "ISO 8601",
            "text": "설명 문장",
            "meta": {...}
        }
        """
        records = []

        for event in events:
            # 텍스트 생성 (LLM이 이해하기 쉬운 자연어 형식)
            text = self._generate_event_text(event)

            # 시장 영향 판단 (actual vs forecast)
            impact = self._calculate_impact(event)

            record = {
                "source": "economic_calendar",
                "timestamp": event.timestamp.isoformat(),
                "text": text,
                "meta": {
                    "event_name": event.event_name,
                    "country": event.country,
                    "importance": event.importance,
                    "actual": event.actual,
                    "forecast": event.forecast,
                    "previous": event.previous,
                    "impact": impact,
                    "currency": event.currency,
                    "event_time": event.timestamp.isoformat(),
                },
            }

            records.append(record)

        return records

    def _generate_event_text(self, event: EconomicEvent) -> str:
        """
        경제 지표 이벤트를 자연어 텍스트로 변환

        LLM이 키워드를 추출하고 분석하기 쉽도록 명확한 문장 생성
        """
        # 과거/미래 구분
        now = datetime.now(timezone.utc)
        is_future = event.timestamp > now

        parts = [f"[{event.country}] {event.event_name}"]

        # 미래 이벤트 (예정된 발표)
        if is_future:
            parts.append("[예정]")
            if event.forecast:
                parts.append(f"예상: {event.forecast}")
            if event.previous:
                parts.append(f"이전: {event.previous}")
        else:
            # 과거 이벤트 (이미 발표된 지표)
            # 실제값이 있으면 포함
            if event.actual:
                parts.append(f"발표: {event.actual}")

            # 예상치와 비교
            if event.forecast and event.actual:
                try:
                    actual_val = float(event.actual.replace("%", ""))
                    forecast_val = float(event.forecast.replace("%", ""))

                    if actual_val > forecast_val:
                        parts.append(f"(예상 {event.forecast} 상회)")
                    elif actual_val < forecast_val:
                        parts.append(f"(예상 {event.forecast} 하회)")
                    else:
                        parts.append("(예상치 일치)")
                except (ValueError, AttributeError):
                    # 숫자 변환 실패 시 그냥 표시
                    parts.append(f"(예상: {event.forecast})")
            elif event.forecast:
                parts.append(f"예상: {event.forecast}")

            # 이전값 포함
            if event.previous:
                parts.append(f"이전: {event.previous}")

        # 중요도 강조
        if event.importance and event.importance.lower() == "high":
            parts.append("[중요]")

        return " ".join(parts)

    def _calculate_impact(self, event: EconomicEvent) -> str:
        """
        실제값과 예상값을 비교하여 시장 영향 판단

        Returns:
            "positive" | "negative" | "neutral"
        """
        if not event.actual or not event.forecast:
            return "neutral"

        try:
            actual_val = float(event.actual.replace("%", "").replace(",", ""))
            forecast_val = float(event.forecast.replace("%", "").replace(",", ""))

            diff_pct = (
                abs((actual_val - forecast_val) / forecast_val) * 100
                if forecast_val != 0
                else 0
            )

            # 5% 이상 차이나면 영향 있음으로 판단
            if diff_pct > 5:
                # 경제 지표별 방향성 판단 (간단한 휴리스틱)
                if (
                    "cpi" in event.event_name.lower()
                    or "inflation" in event.event_name.lower()
                ):
                    # 인플레이션: 예상보다 높으면 부정적 (금리 인상 압력)
                    return "negative" if actual_val > forecast_val else "positive"
                elif (
                    "gdp" in event.event_name.lower()
                    or "employment" in event.event_name.lower()
                ):
                    # GDP, 고용: 예상보다 높으면 긍정적
                    return "positive" if actual_val > forecast_val else "negative"

            return "neutral"

        except (ValueError, AttributeError):
            return "neutral"


# 비동기 헬퍼 함수 (파이프라인에서 사용)
async def collect_economic_calendar(
    countries: list[str] = None,
    importance: str = "high",
    days_back: int = 7,
    days_forward: int = 0,
) -> list[dict[str, Any]]:
    """
    Economic Calendar 데이터를 비동기로 수집하는 헬퍼 함수

    Args:
        countries: 수집할 국가 리스트
        importance: 중요도 필터 (high, medium, low, all)
        days_back: 과거 며칠 데이터 수집
        days_forward: 미래 며칠 예정 일정 수집 (0이면 현재까지만)

    Returns:
        정규화된 레코드 리스트
    """
    collector = EconomicCalendarCollector()

    from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    to_date = datetime.now(timezone.utc) + timedelta(days=days_forward)

    return await collector.collect(
        countries=countries, importance=importance, from_date=from_date, to_date=to_date
    )

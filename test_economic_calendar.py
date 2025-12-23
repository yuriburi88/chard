"""
Economic Calendar 테스트 스크립트

investpy 라이브러리가 제대로 작동하는지, 데이터가 어떻게 나오는지 확인합니다.
"""

import asyncio
from datetime import datetime, timezone, timedelta


async def test_economic_calendar():
    """Economic Calendar 데이터 수집 테스트"""

    print("=" * 60)
    print("Economic Calendar 테스트 시작")
    print("=" * 60)

    # 1. investpy 설치 확인
    try:
        import investpy
        print("\n✅ investpy 라이브러리 설치 확인 완료")
        print(f"   버전: {investpy.__version__ if hasattr(investpy, '__version__') else 'Unknown'}")
    except ImportError as e:
        print("\n❌ investpy 라이브러리가 설치되지 않았습니다.")
        print("   설치 방법: python -m pip install investpy")
        return

    # 2. 날짜 설정
    from_date = datetime.now(timezone.utc) - timedelta(days=7)
    to_date = datetime.now(timezone.utc)

    from_str = from_date.strftime("%d/%m/%Y")
    to_str = to_date.strftime("%d/%m/%Y")

    print(f"\n📅 수집 기간: {from_str} ~ {to_str}")

    # 3. 미국 데이터 수집 테스트
    print("\n" + "=" * 60)
    print("미국(United States) 경제 지표 수집 테스트")
    print("=" * 60)

    try:
        calendar_df = investpy.economic_calendar(
            countries=["united states"],
            from_date=from_str,
            to_date=to_str,
            importances=["high"]  # 중요도: high만
        )

        if calendar_df.empty:
            print("\n⚠️ 데이터가 없습니다. (기간 내 이벤트 없음)")
        else:
            print(f"\n✅ 수집 완료: {len(calendar_df)}개 이벤트")

            # DataFrame 컬럼 확인
            print("\n📊 DataFrame 컬럼:")
            print(f"   {list(calendar_df.columns)}")

            # 처음 3개 데이터 출력
            print("\n📄 샘플 데이터 (처음 3개):")
            print("-" * 60)

            for idx, row in calendar_df.head(3).iterrows():
                print(f"\n이벤트 #{idx + 1}:")
                print(f"  - 날짜/시간: {row.get('date', 'N/A')} {row.get('time', 'N/A')}")
                print(f"  - 이벤트명: {row.get('event', 'N/A')}")
                print(f"  - 중요도: {row.get('importance', 'N/A')}")
                print(f"  - 실제값: {row.get('actual', 'N/A')}")
                print(f"  - 예상값: {row.get('forecast', 'N/A')}")
                print(f"  - 이전값: {row.get('previous', 'N/A')}")
                print(f"  - 통화: {row.get('currency', 'N/A')}")

            # 전체 데이터 요약
            print("\n" + "=" * 60)
            print("📈 데이터 요약")
            print("=" * 60)

            # 이벤트 타입별 개수
            if 'event' in calendar_df.columns:
                print("\n이벤트 타입별 개수:")
                event_counts = calendar_df['event'].value_counts()
                for event, count in event_counts.head(5).items():
                    print(f"  - {event}: {count}개")

            # 중요도별 개수
            if 'importance' in calendar_df.columns:
                print("\n중요도별 개수:")
                importance_counts = calendar_df['importance'].value_counts()
                for importance, count in importance_counts.items():
                    print(f"  - {importance}: {count}개")

    except Exception as exc:
        print(f"\n❌ 데이터 수집 실패: {exc}")
        print(f"   에러 타입: {type(exc).__name__}")
        import traceback
        traceback.print_exc()

    # 4. Collector 클래스 테스트
    print("\n" + "=" * 60)
    print("EconomicCalendarCollector 클래스 테스트")
    print("=" * 60)

    try:
        from src.collectors.economic_calendar_collector import collect_economic_calendar

        print("\n✅ Collector import 성공")

        # 데이터 수집
        print("\n데이터 수집 중...")
        records = await collect_economic_calendar(
            countries=["united states"],
            importance="high",
            days_back=7
        )

        print(f"\n✅ 수집 완료: {len(records)}개 레코드")

        if records:
            # 첫 번째 레코드 출력
            print("\n📄 샘플 레코드 (첫 번째):")
            print("-" * 60)

            import json
            first_record = records[0]
            print(json.dumps(first_record, indent=2, ensure_ascii=False))

            # text 필드 확인
            print("\n📝 생성된 텍스트 예시:")
            for i, record in enumerate(records[:3], 1):
                print(f"\n{i}. {record['text']}")

    except ImportError as exc:
        print(f"\n❌ Collector import 실패: {exc}")
    except Exception as exc:
        print(f"\n❌ Collector 테스트 실패: {exc}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(test_economic_calendar())

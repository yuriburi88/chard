"""
디지털 자산 내러티브 추출 플랫폼 CLI 엔트리 포인트

사용법:
    python main.py --config config.yml
    python main.py --config path/to/config.yml
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone, timedelta, date

from src.config_manager import ConfigManager, AppConfig, OutputConfig
from src.async_utils import run_async_main
from src.collectors.rss_collector import RSSCollector
from src.collectors.telegram_collector import TelegramCollector
from src.collectors.economic_calendar_collector import collect_economic_calendar
from src.collectors.models import Article, TelegramMessage, CollectedItem
from src.preprocessor import Preprocessor, PreprocessingConfig
from src.normalizer import DataNormalizer
from src.storage import StorageManager, ExecutionLogger
from src.workflows.state import AnalysisState


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None
) -> None:
    """
    로깅 설정을 초기화합니다.
    
    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (None이면 파일 로깅 안 함)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # 기존 핸들러 제거 (중복 방지)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (log_file이 제공된 경우)
    if log_file:
        log_file = Path(log_file)
        # 디렉토리 생성
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        logger = logging.getLogger(__name__)
        logger.info(f"로그 파일 저장 위치: {log_file}")
    
    root_logger.setLevel(numeric_level)


def resolve_log_file_path(
    logs_dir: Path,
    execution_timestamp: datetime,
    output_config: OutputConfig
) -> Path:
    """로그 파일 경로를 계산합니다.
    
    Args:
        logs_dir: 로그 파일을 저장할 디렉터리
        execution_timestamp: 실행 타임스탬프 (UTC)
        output_config: 출력 설정 객체
    
    Returns:
        계산된 로그 파일 경로
    """
    strategy = output_config.log_filename_strategy
    logger = logging.getLogger(__name__)
    
    if strategy not in {"timestamp", "fixed_window"}:
        logger.warning(
            "지원하지 않는 로그 파일 전략이 지정되었습니다: %s. 기본 전략(timestamp)을 사용합니다.",
            strategy
        )
        strategy = "timestamp"
    
    # UTC를 표현용 타임존으로 변환
    display_tz = timezone(timedelta(hours=output_config.display_timezone))
    if execution_timestamp.tzinfo is None:
        execution_timestamp = execution_timestamp.replace(tzinfo=timezone.utc)
    display_timestamp = execution_timestamp.astimezone(display_tz)
    
    if strategy == "fixed_window":
        window_days = max(1, output_config.log_fixed_window_days)
        base_date = display_timestamp.date()
        epoch = date(1970, 1, 1)
        delta_days = (base_date - epoch).days
        window_index = delta_days // window_days
        window_start_date = epoch + timedelta(days=window_index * window_days)
        window_end_date = window_start_date + timedelta(days=window_days - 1)
        
        log_filename = (
            f"execution_{window_start_date.strftime('%Y%m%d')}"
            f"_{window_end_date.strftime('%Y%m%d')}.log"
        )
        
        return logs_dir / log_filename
    
    date_str = display_timestamp.strftime("%Y%m%d")
    time_str = display_timestamp.strftime("%H%M%S")
    log_filename = f"execution_{date_str}_{time_str}.log"
    
    return logs_dir / log_filename


def parse_arguments() -> argparse.Namespace:
    """
    커맨드라인 인자를 파싱합니다.
    
    Returns:
        파싱된 인자 네임스페이스
    """
    parser = argparse.ArgumentParser(
        description="디지털 자산 내러티브 추출 플랫폼",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py --config config.yml
  python main.py --config path/to/config.yml
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="설정 파일 경로 (기본값: config.yml)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="로그 레벨 (기본값: config.yml의 output.log_level)"
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> AppConfig:
    """
    설정 파일을 로드하고 검증합니다.
    
    Args:
        config_path: 설정 파일 경로
        
    Returns:
        검증된 AppConfig 객체
        
    Raises:
        FileNotFoundError: 설정 파일을 찾을 수 없는 경우
        ValueError: 설정이 유효하지 않은 경우
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {config_path}\n"
            f"현재 작업 디렉터리: {Path.cwd()}"
        )
    
    logger = logging.getLogger(__name__)
    logger.info(f"설정 파일 로드 시작: {config_path}")
    
    try:
        config_manager = ConfigManager(config_path=config_path)
        app_config = config_manager.load()
        logger.info("설정 파일 로드 및 검증 완료")
        return app_config
    except Exception as e:
        logger.error(f"설정 파일 로드 실패: {e}", exc_info=True)
        raise


def calculate_min_timestamp(app_config: AppConfig) -> Optional[datetime]:
    """
    수집 기간 설정에 따라 최소 타임스탬프를 계산합니다.

    두 가지 모드 지원:
    - "recent_hours": 현재 시간에서 N시간 전까지 (기존 방식)
    - "days_back": N일 전 00:00부터 현재까지 (날짜 기준, display_timezone 적용)

    Args:
        app_config: 애플리케이션 설정 객체

    Returns:
        최소 타임스탬프 (UTC) 또는 None (필터링 안 함)
    """
    period = app_config.collection_period
    logger = logging.getLogger(__name__)

    # start_time이 있으면 우선 사용 (직접 지정 모드)
    if period.start_time:
        try:
            from dateutil import parser
            min_timestamp = parser.parse(period.start_time)
            if min_timestamp.tzinfo is None:
                min_timestamp = min_timestamp.replace(tzinfo=timezone.utc)
            logger.info(f"수집 기간: start_time 직접 지정 - {min_timestamp.isoformat()}")
            return min_timestamp
        except Exception as e:
            logger.warning(f"start_time 파싱 실패: {e}, mode 설정 사용")

    mode = getattr(period, 'mode', 'recent_hours')

    # days_back 모드: N일 전 00:00부터 (display_timezone 기준)
    if mode == "days_back" and period.days_back is not None:
        display_tz_offset = app_config.output.display_timezone
        display_tz = timezone(timedelta(hours=display_tz_offset))

        # 현재 시간을 display_timezone으로 변환
        now_local = datetime.now(display_tz)

        # N일 전 날짜의 00:00:00 계산
        target_date = now_local.date() - timedelta(days=period.days_back)
        min_timestamp_local = datetime.combine(target_date, datetime.min.time(), tzinfo=display_tz)

        # UTC로 변환
        min_timestamp = min_timestamp_local.astimezone(timezone.utc)

        logger.info(
            f"수집 기간: days_back={period.days_back} - "
            f"{target_date.strftime('%Y-%m-%d')} 00:00 (UTC{display_tz_offset:+d}) ~ 현재"
        )
        return min_timestamp

    # recent_hours 모드: 현재 시간에서 N시간 전 (기존 방식)
    if period.recent_hours:
        min_timestamp = datetime.now(timezone.utc) - timedelta(hours=period.recent_hours)
        logger.info(f"수집 기간: recent_hours={period.recent_hours} - {min_timestamp.isoformat()} ~ 현재")
        return min_timestamp

    # 둘 다 없으면 None (모든 데이터 수집)
    logger.info("수집 기간: 제한 없음 (모든 데이터 수집)")
    return None


async def collect_rss_data(
    app_config: AppConfig,
    min_timestamp: Optional[datetime],
    execution_logger: ExecutionLogger
) -> List[Article]:
    """
    RSS 데이터를 수집합니다.
    
    Args:
        app_config: 애플리케이션 설정 객체
        min_timestamp: 최소 타임스탬프 (None이면 필터링 안 함)
        execution_logger: 실행 로그 기록기
    
    Returns:
        수집된 RSS 기사 리스트
    """
    logger = logging.getLogger(__name__)
    rss_articles: List[Article] = []
    collect_start = datetime.now(timezone.utc)
    
    if not app_config.rss_sources:
        logger.info("[RSS 수집] RSS 소스가 설정되지 않았습니다.")
        collect_end = datetime.now(timezone.utc)
        execution_logger.log_stage(
            "rss_collect",
            collect_start,
            collect_end,
            success=True,
            details={"sources_count": 0, "articles_count": 0}
        )
        return rss_articles
    
    logger.info(f"[RSS 수집] {len(app_config.rss_sources)}개 소스 수집 시작")
    
    async with RSSCollector() as rss_collector:
        for rss_config in app_config.rss_sources:
            try:
                articles = await rss_collector.collect(rss_config, min_published=min_timestamp)
                rss_articles.extend(articles)
                logger.info(f"[RSS 수집] {rss_config.name}: {len(articles)}개 기사 수집")
            except Exception as e:
                logger.error(f"[RSS 수집] {rss_config.name} 수집 실패: {e}", exc_info=True)
                execution_logger.log_error(
                    "RSSCollectionError",
                    f"{rss_config.name} 수집 실패: {str(e)}",
                    stage="collect",
                    details={"source": rss_config.name, "url": rss_config.url}
                )
    
    collect_end = datetime.now(timezone.utc)
    execution_logger.log_stage(
        "rss_collect",
        collect_start,
        collect_end,
        success=True,
        details={"sources_count": len(app_config.rss_sources), "articles_count": len(rss_articles)}
    )
    logger.info(f"[RSS 수집] 완료: 총 {len(rss_articles)}개 기사 수집")
    
    return rss_articles


async def collect_telegram_data(
    app_config: AppConfig,
    min_timestamp: Optional[datetime],
    execution_logger: ExecutionLogger
) -> List[TelegramMessage]:
    """
    텔레그램 데이터를 수집합니다.
    
    Args:
        app_config: 애플리케이션 설정 객체
        min_timestamp: 최소 타임스탬프 (None이면 필터링 안 함)
        execution_logger: 실행 로그 기록기
    
    Returns:
        수집된 텔레그램 메시지 리스트
    """
    logger = logging.getLogger(__name__)
    telegram_messages: List[TelegramMessage] = []
    collect_start = datetime.now(timezone.utc)
    
    if not app_config.telegram_sources:
        logger.info("[텔레그램 수집] 텔레그램 소스가 설정되지 않았습니다.")
        collect_end = datetime.now(timezone.utc)
        execution_logger.log_stage(
            "telegram_collect",
            collect_start,
            collect_end,
            success=True,
            details={"sources_count": 0, "messages_count": 0}
        )
        return telegram_messages
    
    logger.info(f"[텔레그램 수집] {len(app_config.telegram_sources)}개 소스 수집 시작")
    
    telegram_collector = TelegramCollector()
    for tg_config in app_config.telegram_sources:
        try:
            messages = await telegram_collector.collect(tg_config, min_timestamp=min_timestamp)
            telegram_messages.extend(messages)
            logger.info(f"[텔레그램 수집] {tg_config.name}: {len(messages)}개 메시지 수집")
        except Exception as e:
            logger.error(f"[텔레그램 수집] {tg_config.name} 수집 실패: {e}", exc_info=True)
            execution_logger.log_error(
                "TelegramCollectionError",
                f"{tg_config.name} 수집 실패: {str(e)}",
                stage="collect",
                details={"source": tg_config.name, "channel_id": tg_config.channel_id}
            )
    
    collect_end = datetime.now(timezone.utc)
    execution_logger.log_stage(
        "telegram_collect",
        collect_start,
        collect_end,
        success=True,
        details={"sources_count": len(app_config.telegram_sources), "messages_count": len(telegram_messages)}
    )
    logger.info(f"[텔레그램 수집] 완료: 총 {len(telegram_messages)}개 메시지 수집")

    return telegram_messages


async def collect_economic_calendar_data(
    app_config: AppConfig,
    execution_logger: ExecutionLogger
) -> List[CollectedItem]:
    """
    Economic Calendar 데이터를 수집합니다.

    Args:
        app_config: 애플리케이션 설정 객체
        execution_logger: 실행 로그 기록기

    Returns:
        수집된 경제 지표 이벤트 리스트 (CollectedItem 형식)
    """
    logger = logging.getLogger(__name__)
    collect_start = datetime.now(timezone.utc)

    # Economic Calendar 설정 확인
    ec_config = app_config.economic_calendar

    if not ec_config.enabled:
        logger.info("[Economic Calendar] 비활성화 상태, 수집 건너뜀")
        collect_end = datetime.now(timezone.utc)
        execution_logger.log_stage(
            "economic_calendar_collect",
            collect_start,
            collect_end,
            success=True,
            details={"enabled": False, "events_count": 0}
        )
        return []

    days_back = ec_config.days_back
    days_forward = ec_config.days_forward

    logger.info(
        f"[Economic Calendar] 데이터 수집 시작 "
        f"(과거 {days_back}일 + 미래 {days_forward}일)"
    )

    try:
        # Economic Calendar 데이터 수집
        records = await collect_economic_calendar(
            countries=ec_config.countries,
            importance=ec_config.importance,
            days_back=days_back,
            days_forward=days_forward
        )

        logger.info(
            f"[Economic Calendar] 수집 완료: {len(records)}개 이벤트 "
            f"(과거 {days_back}일 + 미래 {days_forward}일)"
        )

        # CollectedItem 형식으로 변환
        collected_items = []
        for record in records:
            try:
                collected_items.append(
                    CollectedItem(
                        source_type="economic_calendar",
                        source_name="Economic Calendar",
                        timestamp=datetime.fromisoformat(record["timestamp"]),
                        text=record["text"],
                        metadata=record.get("meta", {})
                    )
                )
            except Exception as e:
                logger.warning(f"[Economic Calendar] 레코드 변환 실패: {e}")
                continue

        collect_end = datetime.now(timezone.utc)
        execution_logger.log_stage(
            "economic_calendar_collect",
            collect_start,
            collect_end,
            success=True,
            details={"enabled": True, "events_count": len(collected_items)}
        )

        return collected_items

    except Exception as exc:
        logger.error(f"[Economic Calendar] 수집 실패: {exc}", exc_info=True)
        collect_end = datetime.now(timezone.utc)
        execution_logger.log_stage(
            "economic_calendar_collect",
            collect_start,
            collect_end,
            success=False,
            details={"error": str(exc)}
        )
        execution_logger.log_error(
            "EconomicCalendarCollectionError",
            f"Economic Calendar 수집 실패: {str(exc)}",
            stage="collect",
            details={"countries": ec_config.get("countries", [])}
        )
        return []


async def preprocess_data(
    rss_articles: List[Article],
    telegram_messages: List[TelegramMessage],
    economic_events: List[CollectedItem],
    execution_logger: ExecutionLogger,
    preprocessing_config: Optional[PreprocessingConfig] = None
) -> tuple[List[Article], List[CollectedItem]]:
    """
    데이터를 전처리합니다.

    Args:
        rss_articles: RSS 기사 리스트
        telegram_messages: 텔레그램 메시지 리스트
        economic_events: Economic Calendar 이벤트 리스트
        execution_logger: 실행 로그 기록기
        preprocessing_config: 전처리 설정

    Returns:
        (전처리된 RSS 기사 리스트, 전처리된 CollectedItem 리스트 - telegram + economic)
    """
    logger = logging.getLogger(__name__)
    preprocessed_articles: List[Article] = []
    preprocessed_items: List[CollectedItem] = []

    if not rss_articles and not telegram_messages and not economic_events:
        logger.warning("[전처리] 수집된 데이터가 없어 전처리를 건너뜁니다.")
        return preprocessed_articles, preprocessed_items
    
    logger.info("[전처리] 데이터 전처리 시작")
    preprocess_start = datetime.now(timezone.utc)
    
    preprocessor = Preprocessor(config=preprocessing_config)
    
    # RSS 기사 전처리
    if rss_articles:
        preprocessed_articles = await preprocessor.preprocess_articles(rss_articles)
        logger.info(
            f"[전처리] RSS 기사: {len(rss_articles)}개 → {len(preprocessed_articles)}개 "
            f"(필터링: {len(rss_articles) - len(preprocessed_articles)}개)"
        )
    
    # 텔레그램 메시지와 Economic Calendar 이벤트를 CollectedItem으로 병합 후 전처리
    combined_items = []

    if telegram_messages:
        telegram_items = DataNormalizer.normalize_telegram_messages(telegram_messages)
        combined_items.extend(telegram_items)
        logger.info(f"[전처리] 텔레그램 메시지: {len(telegram_messages)}개 변환")

    if economic_events:
        combined_items.extend(economic_events)
        logger.info(f"[전처리] Economic Calendar: {len(economic_events)}개 추가")

    # 병합된 아이템 전처리
    if combined_items:
        preprocessed_items = await preprocessor.preprocess_collected_items(combined_items)
        logger.info(
            f"[전처리] 통합 아이템: {len(combined_items)}개 → {len(preprocessed_items)}개 "
            f"(필터링: {len(combined_items) - len(preprocessed_items)}개)"
        )

    preprocess_end = datetime.now(timezone.utc)
    execution_logger.log_stage(
        "preprocess",
        preprocess_start,
        preprocess_end,
        success=True,
        details={
            "rss_input": len(rss_articles),
            "rss_output": len(preprocessed_articles),
            "telegram_input": len(telegram_messages),
            "economic_input": len(economic_events),
            "combined_output": len(preprocessed_items)
        }
    )
    logger.info("[전처리] 데이터 전처리 완료")
    
    return preprocessed_articles, preprocessed_items


async def normalize_data(
    preprocessed_articles: List[Article],
    preprocessed_items: List[CollectedItem],
    execution_logger: ExecutionLogger
) -> List[CollectedItem]:
    """
    데이터를 정규화합니다.

    Args:
        preprocessed_articles: 전처리된 RSS 기사 리스트
        preprocessed_items: 전처리된 CollectedItem 리스트 (텔레그램 + Economic Calendar)
        execution_logger: 실행 로그 기록기

    Returns:
        정규화된 CollectedItem 리스트 (시간순 정렬)
    """
    logger = logging.getLogger(__name__)
    normalized_items: List[CollectedItem] = []
    
    if not preprocessed_articles and not preprocessed_items:
        logger.warning("[정규화] 전처리된 데이터가 없어 정규화를 건너뜁니다.")
        return normalized_items
    
    logger.info("[정규화] 데이터 정규화 시작")
    normalize_start = datetime.now(timezone.utc)
    
    # RSS 기사를 CollectedItem으로 변환
    if preprocessed_articles:
        article_items = DataNormalizer.normalize_articles(preprocessed_articles)
        normalized_items.extend(article_items)
    
    # 텔레그램 메시지와 Economic Calendar 이벤트는 이미 CollectedItem이므로 추가
    if preprocessed_items:
        normalized_items.extend(preprocessed_items)
    
    # 시간순 정렬
    normalized_items.sort(key=lambda x: x.timestamp)
    
    normalize_end = datetime.now(timezone.utc)
    execution_logger.log_stage(
        "normalize",
        normalize_start,
        normalize_end,
        success=True,
        details={"normalized_items": len(normalized_items)}
    )
    logger.info(f"[정규화] 데이터 정규화 완료: {len(normalized_items)}개 항목")
    
    return normalized_items


async def save_raw_data_to_file(
    normalized_items: List[CollectedItem],
    storage_manager: StorageManager,
    output_dir: Path,
    execution_timestamp: datetime,
    execution_logger: ExecutionLogger
) -> Optional[Path]:
    """
    원본 데이터를 파일로 저장합니다.
    
    Args:
        normalized_items: 정규화된 CollectedItem 리스트
        storage_manager: 저장 관리자
        output_dir: 출력 디렉토리
        execution_timestamp: 실행 타임스탬프
        execution_logger: 실행 로그 기록기
    
    Returns:
        저장된 파일 경로 (데이터가 없으면 None)
    """
    logger = logging.getLogger(__name__)
    
    if not normalized_items:
        logger.warning("[저장] 저장할 데이터가 없습니다.")
        execution_logger.log_warning(
            "NoDataWarning",
            "수집된 데이터가 없어 원본 데이터를 저장하지 않았습니다.",
            stage="save_raw_data"
        )
        return None
    
    logger.info("[저장] 원본 데이터 저장 시작")
    save_start = datetime.now(timezone.utc)
    
    # CollectedItem을 딕셔너리 형식으로 변환
    raw_data = DataNormalizer.to_dict_format_batch(normalized_items)
    
    # 원본 데이터 저장
    raw_file_path = await storage_manager.save_raw_data(
        raw_data,
        output_dir,
        filename_prefix="collected",
        timestamp=execution_timestamp
    )
    
    save_end = datetime.now(timezone.utc)
    execution_logger.log_stage(
        "save_raw_data",
        save_start,
        save_end,
        success=True,
        details={"file_path": str(raw_file_path), "items_count": len(raw_data)}
    )
    logger.info(f"[저장] 원본 데이터 저장 완료: {raw_file_path}")
    
    # 통계 업데이트
    execution_logger.add_statistic("normalized_items", len(normalized_items))
    execution_logger.add_statistic("raw_data_file", str(raw_file_path))
    
    return raw_file_path


async def _save_analysis_results(
    final_state: AnalysisState,
    output_dir: Path,
    execution_timestamp: datetime,
    app_config: AppConfig,
    storage_manager: StorageManager
) -> None:
    """
    Stage 4 분석 결과를 JSON 및 Markdown 형식으로 저장합니다.
    
    Args:
        final_state: LangGraph 워크플로 최종 상태
        output_dir: 출력 디렉토리
        execution_timestamp: 실행 타임스탬프 (파일명 생성용)
        app_config: 애플리케이션 설정 객체
        storage_manager: 저장 관리자
    """
    logger = logging.getLogger(__name__)
    
    # evidence_ids를 원본 텍스트로 복원
    id_mapping = final_state.get("id_mapping", {})
    if not id_mapping:
        from src.workflows.id_generator import get_id_generator
        id_generator = get_id_generator()
        id_mapping = id_generator.get_all_mappings()
    
    aggregated_keywords = final_state.get("aggregated_keywords", [])
    
    # evidence_ids를 원본 텍스트로 복원
    for keyword in aggregated_keywords:
        evidence_ids = keyword.get("evidence_ids", [])
        evidence_texts = []
        invalid_ids = []
        for evidence_id in evidence_ids:
            if isinstance(evidence_id, int) and evidence_id in id_mapping:
                record = id_mapping[evidence_id]
                text = str(record.get("text", "")).strip()
                if text:
                    evidence_texts.append(text)
            else:
                invalid_ids.append(evidence_id)
        
        # 유효하지 않은 ID가 있으면 로그에 기록
        if invalid_ids:
            logger.warning(
                f"[Stage 4] 키워드 '{keyword.get('term', 'unknown')}'의 evidence_ids 중 "
                f"유효하지 않은 ID: {invalid_ids}"
            )
        
        # evidence 필드에 원본 텍스트 추가
        keyword["evidence"] = evidence_texts
    
    # 리포트 빌더를 사용하여 리포트 생성
    from src.report.report_builder import build_json_report, build_markdown_report
    
    # JSON 리포트 생성
    json_report = build_json_report(final_state)
    
    # Markdown 리포트 생성
    markdown_report = build_markdown_report(
        final_state,
        timezone_offset=app_config.output.display_timezone
    )
    
    # 파일명 생성 (타임스탬프 기반)
    timestamp_str = execution_timestamp.strftime("%H%M%S")
    
    # JSON 리포트 저장
    json_file = output_dir / f"{timestamp_str}_summary.json"
    await storage_manager.save_json(json_report, json_file)
    logger.info(f"JSON 리포트 저장 완료: {json_file}")
    
    # Markdown 리포트 저장
    markdown_file = output_dir / f"{timestamp_str}_summary.md"
    await storage_manager.save_text(markdown_report, markdown_file)
    logger.info(f"Markdown 리포트 저장 완료: {markdown_file}")
    
    # 요약 출력
    logger.info("=" * 80)
    logger.info("Stage 4 실행 결과 요약")
    logger.info("=" * 80)
    logger.info(f"실행 시간: {final_state.get('execution_time', 0.0):.2f}초")
    logger.info(f"처리된 청크 수: {final_state.get('chunk_count', 0)}개")
    logger.info(f"통합된 키워드 수: {len(final_state.get('aggregated_keywords', []))}개")
    
    insights = final_state.get("insights", {})
    if insights:
        narrative_count = len(insights.get("narrative_summary", []))
        trading_insights = insights.get("trading_insights", {})
        opportunities_count = len(trading_insights.get("opportunities", []))
        risks_count = len(trading_insights.get("risks", []))
        market_sentiment = trading_insights.get("market_sentiment", "N/A")
        key_sources_count = len(insights.get("key_sources", []))
        
        logger.info("")
        logger.info("인사이트 통계:")
        logger.info(f"  내러티브 요약 문단 수: {narrative_count}개")
        logger.info(f"  거래 기회 인사이트: {opportunities_count}개")
        logger.info(f"  위험 인사이트: {risks_count}개")
        logger.info(f"  시장 심리: {market_sentiment}")
        logger.info(f"  주요 출처 수: {key_sources_count}개")
    
    # 상위 키워드 요약 (상위 5개)
    if aggregated_keywords:
        logger.info("")
        logger.info("상위 키워드 (Top 5):")
        for idx, keyword in enumerate(aggregated_keywords[:5], start=1):
            term = keyword.get("term", "N/A")
            score = keyword.get("score", 0.0)
            occurrence = keyword.get("occurrence_count", 0)
            logger.info(
                f"  {idx}. {term} (점수: {score:.1f}, 출현: {occurrence}회)"
            )
    
    logger.info("")
    logger.info(f"출력 디렉토리: {output_dir}")
    logger.info(f"✅ Markdown 리포트: {markdown_file.name}")
    logger.info(f"✅ JSON 리포트: {json_file.name}")
    logger.info("=" * 80)


def print_execution_summary(
    execution_logger: ExecutionLogger,
    output_dir: Path
) -> None:
    """
    실행 완료 요약을 출력합니다.
    
    Args:
        execution_logger: 실행 로그 기록기
        output_dir: 출력 디렉토리
    """
    logger = logging.getLogger(__name__)
    summary = execution_logger.get_summary()
    
    logger.info("=" * 80)
    logger.info("실행 완료 요약")
    logger.info("=" * 80)
    logger.info(f"총 소요 시간: {summary['total_duration_seconds']:.2f}초")
    logger.info(f"RSS 기사 수집: {summary['statistics'].get('rss_articles', 0)}개")
    logger.info(f"텔레그램 메시지 수집: {summary['statistics'].get('telegram_messages', 0)}개")
    logger.info(f"정규화된 항목: {summary['statistics'].get('normalized_items', 0)}개")
    logger.info(f"처리 단계 수: {summary['stages_count']}개")
    logger.info(f"에러 수: {summary['errors_count']}개")
    logger.info(f"경고 수: {summary['warnings_count']}개")
    logger.info(f"출력 디렉토리: {output_dir}")
    logger.info("=" * 80)


async def main_async(app_config: AppConfig, log_level: str = "INFO") -> None:
    """
    비동기 메인 함수
    
    전체 파이프라인 실행: 데이터 수집 → 전처리 → 정규화 → 원본 데이터 저장 → LLM 분석 → 리포트 생성
    
    Args:
        app_config: 애플리케이션 설정 객체
        log_level: 로그 레벨
    """
    # 실행 로그 및 저장 관리자 초기화
    storage_manager = StorageManager(
        base_output_dir=app_config.output.output_dir,
        display_timezone=app_config.output.display_timezone
    )
    execution_timestamp = datetime.now(timezone.utc)
    output_dir = await storage_manager.create_output_directory(execution_timestamp)
    
    # 로그 파일 설정 (프로젝트 루트의 logs 폴더에 저장)
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 로그 파일 경로 계산 (전략 설정 기반)
    log_file = resolve_log_file_path(logs_dir, execution_timestamp, app_config.output)
    
    setup_logging(log_level, log_file=log_file)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("디지털 자산 내러티브 추출 플랫폼 - 데이터 수집 및 저장 단계 실행")
    logger.info("=" * 80)
    
    execution_logger = ExecutionLogger(output_dir=output_dir)
    
    execution_logger.start()
    
    try:
        # 수집 기간 계산
        min_timestamp = calculate_min_timestamp(app_config)
        if min_timestamp:
            logger.info(f"[수집 기간] 최소 타임스탬프: {min_timestamp.isoformat()}")
        else:
            logger.info("[수집 기간] 모든 데이터 수집 (필터링 없음)")
        
        # 1. 데이터 수집
        rss_articles = await collect_rss_data(app_config, min_timestamp, execution_logger)
        telegram_messages = await collect_telegram_data(app_config, min_timestamp, execution_logger)
        economic_events = await collect_economic_calendar_data(app_config, execution_logger)

        # 모든 소스가 없는 경우 에러 발생
        ec_enabled = app_config.economic_calendar.enabled
        if not app_config.rss_sources and not app_config.telegram_sources and not ec_enabled:
            error_msg = "수집할 소스가 설정되지 않았습니다. rss_sources, telegram_sources, 또는 economic_calendar 중 최소 하나는 설정되어야 합니다."
            logger.error(f"[오류] {error_msg}")
            execution_logger.log_error(
                "NoSourceError",
                error_msg,
                stage="collect",
                details={
                    "rss_sources_count": len(app_config.rss_sources),
                    "telegram_sources_count": len(app_config.telegram_sources),
                    "economic_calendar_enabled": ec_enabled
                }
            )
            execution_logger.end()
            raise ValueError(error_msg)

        # 수집 통계 로깅
        logger.info(
            f"[데이터 수집 완료] RSS={len(rss_articles)}, "
            f"Telegram={len(telegram_messages)}, "
            f"Economic Calendar={len(economic_events)}"
        )

        # 수집 통계 기록
        execution_logger.set_statistics({
            "rss_articles": len(rss_articles),
            "telegram_messages": len(telegram_messages),
            "economic_events": len(economic_events),
            "total_collected": len(rss_articles) + len(telegram_messages) + len(economic_events)
        })
        
        # 2. 데이터 전처리
        preprocessing_config = PreprocessingConfig(
            split_long_messages=app_config.split_long_messages,
            max_tokens_per_segment=app_config.max_tokens_per_segment,
            segment_overlap_tokens=app_config.segment_overlap_tokens
        )
        
        preprocessed_articles, preprocessed_items = await preprocess_data(
            rss_articles,
            telegram_messages,
            economic_events,
            execution_logger,
            preprocessing_config=preprocessing_config
        )
        
        # 3. 데이터 정규화
        normalized_items = await normalize_data(
            preprocessed_articles,
            preprocessed_items,
            execution_logger
        )
        
        # 4. 원본 데이터 저장
        raw_file_path = await save_raw_data_to_file(
            normalized_items,
            storage_manager,
            output_dir,
            execution_timestamp,
            execution_logger
        )
        
        # 5. Stage 4: LLM 분석 및 리포트 생성 (원본 데이터가 있는 경우에만)
        if raw_file_path and normalized_items:
            logger.info("=" * 80)
            logger.info("Stage 4: LLM 분석 및 리포트 생성 시작")
            logger.info("=" * 80)
            
            try:
                from src.workflows.langgraph_pipeline import run_keyword_analysis_workflow
                from src.workflows.state import AnalysisState
                from dataclasses import asdict
                
                # 원본 데이터를 AnalysisState 형식으로 변환
                raw_records = DataNormalizer.to_dict_format_batch(normalized_items)
                
                # 초기 상태 구성
                initial_state: AnalysisState = {
                    "raw_records": raw_records,
                    "config": asdict(app_config),
                    "errors": [],
                }
                
                # LangGraph 워크플로 실행
                logger.info("LangGraph 워크플로 실행 시작...")
                final_state = await run_keyword_analysis_workflow(initial_state)
                
                # 리포트 저장 및 출력
                await _save_analysis_results(
                    final_state,
                    output_dir,
                    execution_timestamp,
                    app_config,
                    storage_manager
                )
                
            except Exception as e:
                logger.error(f"[Stage 4] 분석 중 오류 발생: {e}", exc_info=True)
                execution_logger.log_error(
                    "Stage4Error",
                    f"Stage 4 실행 중 오류 발생: {str(e)}",
                    stage="analyze",
                    details={"exception_type": type(e).__name__}
                )
                logger.warning("Stage 4는 실패했지만 데이터 수집은 완료되었습니다.")
        
        # 6. 실행 종료 및 최종 요약 출력
        execution_logger.end()
        print_execution_summary(execution_logger, output_dir)
        
    except Exception as e:
        logger.error(f"[오류] 실행 중 예외 발생: {e}", exc_info=True)
        execution_logger.log_error(
            "ExecutionError",
            f"실행 중 예외 발생: {str(e)}",
            stage="main",
            details={"exception_type": type(e).__name__}
        )
        execution_logger.end()
        raise


def main() -> int:
    """
    메인 함수
    
    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    try:
        # 커맨드라인 인자 파싱
        args = parse_arguments()
        
        # 임시 로깅 설정 (설정 파일 로드 전)
        setup_logging("INFO")
        logger = logging.getLogger(__name__)
        
        # 설정 파일 로드
        app_config = load_config(args.config)
        
        # 설정 파일의 로그 레벨로 재설정 (인자로 오버라이드 가능)
        log_level = args.log_level or app_config.output.log_level
        
        # 비동기 메인 함수 실행 (이벤트 루프 초기화 전략 적용)
        # 로그 파일은 main_async 내부에서 설정
        return run_async_main(main_async, app_config, log_level=log_level)
        
    except FileNotFoundError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"설정 오류: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.", file=sys.stderr)
        return 130
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.critical(f"예상치 못한 오류 발생: {e}", exc_info=True)
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


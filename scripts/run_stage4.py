"""
Stage 4 LangGraph 워크플로 실행 스크립트

Stage 3에서 생성된 원본 데이터를 읽어서 LangGraph 기반 LLM 분석 파이프라인을 실행합니다.

사용법:
    python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json
    python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json --config config.yml
    python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json --output-dir output/2025-01-15/120000
"""

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import ConfigManager, AppConfig, OutputConfig
from src.workflows.langgraph_pipeline import run_keyword_analysis_workflow
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
    """
    로그 파일 경로를 계산합니다.
    
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
            f"stage4_{window_start_date.strftime('%Y%m%d')}"
            f"_{window_end_date.strftime('%Y%m%d')}.log"
        )
        
        return logs_dir / log_filename
    
    date_str = display_timestamp.strftime("%Y%m%d")
    time_str = display_timestamp.strftime("%H%M%S")
    log_filename = f"stage4_{date_str}_{time_str}.log"
    
    return logs_dir / log_filename


def load_raw_records(input_path: Path) -> list:
    """
    Stage 3 결과 파일에서 원본 레코드를 로드합니다.
    
    Args:
        input_path: Stage 3 결과 JSON 파일 경로
    
    Returns:
        정규화된 레코드 리스트
    """
    logger = logging.getLogger(__name__)
    
    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")
    
    logger.info(f"Stage 3 결과 파일 로드 중: {input_path}")
    
    with input_path.open("r", encoding="utf-8") as fp:
        raw_payload = json.load(fp)
    
    # 다양한 JSON 구조 지원
    if isinstance(raw_payload, dict):
        # "records" 키가 있으면 사용
        if "records" in raw_payload:
            records = raw_payload["records"]
        # "articles" 키가 있으면 사용
        elif "articles" in raw_payload:
            records = raw_payload["articles"]
        # 그 외에는 전체를 리스트로 간주
        else:
            records = [raw_payload]
    elif isinstance(raw_payload, list):
        records = raw_payload
    else:
        raise ValueError(f"예상치 못한 JSON 구조입니다: {type(raw_payload)}")
    
    logger.info(f"로드된 레코드 수: {len(records)}개")
    
    return records


async def save_results(
    final_state: AnalysisState,
    output_dir: Path,
    execution_timestamp: datetime
) -> None:
    """
    분석 결과를 리포트 빌더를 사용하여 JSON 및 Markdown 형식으로 저장합니다.
    
    Args:
        final_state: 최종 워크플로 상태
        output_dir: 출력 디렉토리
        execution_timestamp: 실행 타임스탬프 (파일명 생성용)
    """
    logger = logging.getLogger(__name__)
    
    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # evidence_ids를 원본 텍스트로 복원
    # state에서 id_mapping을 가져오되, 없으면 ID 생성기에서 직접 가져오기
    id_mapping = final_state.get("id_mapping", {})
    if not id_mapping:
        # state에 id_mapping이 없으면 ID 생성기에서 직접 가져오기
        from src.workflows.id_generator import get_id_generator
        id_generator = get_id_generator()
        id_mapping = id_generator.get_all_mappings()
        logger.debug(
            f"[run_stage4] state에서 id_mapping을 찾지 못해 ID 생성기에서 직접 가져옴: "
            f"총 레코드 수={len(id_mapping)}"
        )
    
    aggregated_keywords = final_state.get("aggregated_keywords", [])
    
    # evidence_ids를 원본 텍스트로 복원
    for keyword in aggregated_keywords:
        evidence_ids = keyword.get("evidence_ids", [])
        
        # evidence_ids를 원본 텍스트로 복원
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
                f"[run_stage4] 키워드 '{keyword.get('term', 'unknown')}'의 evidence_ids 중 "
                f"유효하지 않은 ID: {invalid_ids}\n"
                f"ID 매핑 통계: 총 레코드 수={len(id_mapping)}, "
                f"유효한 ID 범위={f'{min(id_mapping.keys())}-{max(id_mapping.keys())}' if id_mapping else 'N/A'}"
            )
        
        # evidence 필드에 원본 텍스트 추가 (리포트 빌더에서 사용)
        keyword["evidence"] = evidence_texts
    
    # 리포트 빌더를 사용하여 리포트 생성
    from src.report.report_builder import build_json_report, build_markdown_report
    from src.config_manager import AppConfig
    
    # 설정에서 timezone_offset 가져오기
    config_dict = final_state.get("config", {})
    output_config = config_dict.get("output", {})
    timezone_offset = int(output_config.get("display_timezone", 9))
    
    # JSON 리포트 생성
    json_report = build_json_report(final_state)
    
    # Markdown 리포트 생성
    markdown_report = build_markdown_report(
        final_state,
        timezone_offset=timezone_offset
    )
    
    # 파일명 생성 (타임스탬프 기반)
    timestamp_str = execution_timestamp.strftime("%H%M%S")
    
    # aiofiles 사용 가능 여부 확인
    try:
        import aiofiles
        AIOFILES_AVAILABLE = True
    except ImportError:
        AIOFILES_AVAILABLE = False
    
    # JSON 리포트 저장 (비동기)
    json_file = output_dir / f"{timestamp_str}_summary.json"
    if AIOFILES_AVAILABLE:
        async with aiofiles.open(json_file, "w", encoding="utf-8") as fp:
            await fp.write(json.dumps(json_report, ensure_ascii=False, indent=2))
        logger.info(f"JSON 리포트 저장 완료: {json_file}")
    else:
        # aiofiles가 없으면 동기 방식으로 저장
        with json_file.open("w", encoding="utf-8") as fp:
            json.dump(json_report, fp, ensure_ascii=False, indent=2)
        logger.info(f"JSON 리포트 저장 완료: {json_file}")
    
    # Markdown 리포트 저장 (비동기)
    markdown_file = output_dir / f"{timestamp_str}_summary.md"
    if AIOFILES_AVAILABLE:
        async with aiofiles.open(markdown_file, "w", encoding="utf-8") as fp:
            await fp.write(markdown_report)
        logger.info(f"Markdown 리포트 저장 완료: {markdown_file}")
    else:
        # aiofiles가 없으면 동기 방식으로 저장
        with markdown_file.open("w", encoding="utf-8") as fp:
            fp.write(markdown_report)
        logger.info(f"Markdown 리포트 저장 완료: {markdown_file}")
    
    logger.info(f"리포트 저장 완료: JSON={json_file.name}, Markdown={markdown_file.name}")


def print_summary(final_state: AnalysisState, output_dir: Path) -> None:
    """
    실행 결과 요약을 출력합니다.
    
    Args:
        final_state: 최종 워크플로 상태
        output_dir: 출력 디렉토리 (파일 경로 표시용)
    """
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("Stage 4 실행 결과 요약")
    logger.info("=" * 80)
    
    # 실행 시간
    execution_time = final_state.get("execution_time", 0.0)
    start_time = final_state.get("start_time")
    end_time = final_state.get("end_time")
    
    logger.info(f"실행 시간: {execution_time:.2f}초")
    if start_time and end_time:
        logger.info(f"시작 시간: {start_time.isoformat()}")
        logger.info(f"종료 시간: {end_time.isoformat()}")
    
    # 청크 처리 통계
    chunk_count = final_state.get("chunk_count", 0)
    total_records = len(final_state.get("raw_records", []))
    logger.info(f"처리된 청크 수: {chunk_count}개")
    logger.info(f"총 레코드 수: {total_records}개")
    
    # 키워드 통계
    extracted_count = len(final_state.get("extracted_keywords", []))
    aggregated_count = len(final_state.get("aggregated_keywords", []))
    logger.info(f"추출된 키워드 수: {extracted_count}개")
    logger.info(f"통합된 키워드 수: {aggregated_count}개")
    
    # 상위 키워드 요약 (상위 5개)
    aggregated_keywords = final_state.get("aggregated_keywords", [])
    if aggregated_keywords:
        logger.info("")
        logger.info("상위 키워드 (Top 5):")
        for idx, keyword in enumerate(aggregated_keywords[:5], start=1):
            term = keyword.get("term", "N/A")
            score = keyword.get("score", 0.0)
            variants = keyword.get("original_variants", [])
            occurrence = keyword.get("occurrence_count", 0)
            logger.info(
                f"  {idx}. {term} (점수: {score:.1f}, 출현: {occurrence}회)"
                + (f" [원본 변형: {', '.join(str(v) for v in variants[:3])}]" if variants else "")
            )
    
    # 인사이트 통계
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
    
    # 출력 파일 정보
    logger.info("")
    logger.info(f"출력 디렉토리: {output_dir}")
    
    # 에러 통계
    errors = final_state.get("errors", [])
    if errors:
        logger.warning("")
        logger.warning(f"⚠️  발생한 에러 수: {len(errors)}개")
        for idx, error in enumerate(errors[:5], start=1):
            logger.warning(f"  {idx}. {error}")
        if len(errors) > 5:
            logger.warning(f"  ... 외 {len(errors) - 5}개 에러")
    else:
        logger.info("")
        logger.info("✅ 에러 없이 완료되었습니다.")
    
    logger.info("=" * 80)


async def main_async(
    input_path: Path,
    config_path: Path,
    output_dir: Optional[Path],
    log_level: str
) -> int:
    """
    비동기 메인 함수
    
    Args:
        input_path: Stage 3 결과 파일 경로
        config_path: 설정 파일 경로
        output_dir: 출력 디렉토리 (None이면 input_path와 같은 디렉토리 사용)
        log_level: 로그 레벨
    
    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    execution_timestamp = datetime.now(timezone.utc)
    
    # 설정 로드
    try:
        config_manager = ConfigManager(config_path=str(config_path))
        app_config = config_manager.load()
    except Exception as e:
        print(f"설정 파일 로드 실패: {e}", file=sys.stderr)
        return 1
    
    # 로그 파일 설정
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = resolve_log_file_path(logs_dir, execution_timestamp, app_config.output)
    
    # 로깅 설정
    setup_logging(log_level, log_file=log_file)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("Stage 4 LangGraph 워크플로 실행")
    logger.info("=" * 80)
    logger.info(f"입력 파일: {input_path}")
    logger.info(f"설정 파일: {config_path}")
    logger.info(f"로그 파일: {log_file}")
    
    # 출력 디렉토리 결정
    if output_dir is None:
        output_dir = input_path.parent
    output_dir = Path(output_dir)
    logger.info(f"출력 디렉토리: {output_dir}")
    
    try:
        # Stage 3 결과 로드
        raw_records = load_raw_records(input_path)
        
        if not raw_records:
            logger.error("로드된 레코드가 없습니다.")
            return 1
        
        # 초기 상태 구성
        initial_state: AnalysisState = {
            "raw_records": raw_records,
            "config": asdict(app_config),
            "errors": [],
        }
        
        # LangGraph 워크플로 실행
        logger.info("LangGraph 워크플로 실행 시작...")
        final_state = await run_keyword_analysis_workflow(initial_state)
        
        # 결과 저장 (비동기)
        await save_results(final_state, output_dir, execution_timestamp)
        
        # 요약 출력
        print_summary(final_state, output_dir)
        
        # 에러가 있으면 경고
        if final_state.get("errors"):
            logger.warning("일부 에러가 발생했지만 실행은 완료되었습니다.")
            return 1
        
        logger.info("Stage 4 실행이 성공적으로 완료되었습니다.")
        return 0
        
    except KeyboardInterrupt:
        logger.warning("사용자에 의해 중단되었습니다.")
        return 130
    except Exception as e:
        logger.critical(f"예상치 못한 오류 발생: {e}", exc_info=True)
        return 1


def parse_arguments() -> argparse.Namespace:
    """
    커맨드라인 인자를 파싱합니다.
    
    Returns:
        파싱된 인자 네임스페이스
    """
    parser = argparse.ArgumentParser(
        description="Stage 4 LangGraph 워크플로 실행 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 사용법
  python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json
  
  # 설정 파일 지정
  python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json --config config.yml
  
  # 출력 디렉토리 지정
  python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json --output-dir output/2025-01-15/120000
  
  # 로그 레벨 변경
  python scripts/run_stage4.py --input output/2025-01-15/120000/articles_raw.json --log-level DEBUG
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Stage 3 결과 JSON 파일 경로 (예: output/2025-01-15/120000/articles_raw.json)"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="설정 파일 경로 (기본값: config.yml)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리 (기본값: 입력 파일과 같은 디렉토리)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="로그 레벨 (기본값: INFO)"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    메인 함수
    
    Returns:
        종료 코드 (0: 성공, 1: 실패, 130: 중단)
    """
    try:
        args = parse_arguments()
        
        # 입력 파일 검증
        if not args.input.exists():
            print(f"오류: 입력 파일을 찾을 수 없습니다: {args.input}", file=sys.stderr)
            return 1
        
        # 설정 파일 검증
        if not args.config.exists():
            print(f"오류: 설정 파일을 찾을 수 없습니다: {args.config}", file=sys.stderr)
            return 1
        
        # 비동기 메인 함수 실행
        return asyncio.run(
            main_async(
                input_path=args.input,
                config_path=args.config,
                output_dir=args.output_dir,
                log_level=args.log_level
            )
        )
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


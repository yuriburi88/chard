"""
JSON 리포트에서 Markdown 리포트 생성 스크립트

기존 JSON 리포트 파일(stage4_results.json 또는 *_summary.json)을 읽어서
Markdown 리포트를 생성합니다.

사용법:
    python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json
    python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json --output output/2025-11-12/stage4_results.md
    python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json --timezone 9
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 리포트 빌더 import (AnalysisState는 TypedDict이므로 직접 정의)
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


def setup_logging(verbose: bool = False) -> None:
    """
    로깅 설정을 초기화합니다.
    
    Args:
        verbose: 상세 로그 출력 여부
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # 기존 핸들러 제거
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        "%(levelname)s - %(message)s"
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)


def load_json_report(file_path: Path) -> Dict[str, Any]:
    """
    JSON 리포트 파일을 로드합니다.
    
    Args:
        file_path: JSON 리포트 파일 경로
    
    Returns:
        리포트 데이터 딕셔너리
    
    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
        json.JSONDecodeError: JSON 파싱 실패 시
    """
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    with file_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    
    return data


def convert_json_to_analysis_state(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    JSON 리포트 데이터를 AnalysisState 형식으로 변환합니다.
    
    Args:
        json_data: JSON 리포트 데이터
    
    Returns:
        AnalysisState 딕셔너리
    """
    # execution_metadata에서 정보 추출
    metadata = json_data.get("execution_metadata", {})
    
    # 타임스탬프 파싱
    timestamp_str = metadata.get("timestamp")
    start_time_str = metadata.get("start_time")
    
    start_time = None
    end_time = None
    
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    if timestamp_str:
        try:
            end_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    
    # 실행 시간 계산
    execution_time = metadata.get("duration_seconds", 0.0)
    if start_time and end_time:
        execution_time = (end_time - start_time).total_seconds()
    
    # top_keywords를 aggregated_keywords로 변환
    top_keywords = json_data.get("top_keywords", [])
    
    # insights 추출
    insights = json_data.get("insights", {})
    
    # raw_records는 JSON 리포트에 없을 수 있으므로 빈 리스트로 설정
    # (Markdown 생성에는 필수적이지 않음)
    raw_records = []
    
    # config는 기본값 사용 (timezone 등은 인자로 전달)
    config = {
        "output": {
            "display_timezone": 9,  # 기본값, 인자로 오버라이드 가능
        }
    }
    
    # AnalysisState 구성
    state: AnalysisState = {
        "raw_records": raw_records,
        "config": config,
        "aggregated_keywords": top_keywords,
        "insights": insights,
        "execution_time": execution_time,
        "start_time": start_time,
        "end_time": end_time,
        "chunk_count": metadata.get("chunks_processed", 0),
        "errors": json_data.get("errors", []),
    }
    
    return state


def save_markdown_report(content: str, output_path: Path) -> None:
    """
    Markdown 리포트를 파일로 저장합니다.
    
    Args:
        content: Markdown 리포트 내용
        output_path: 저장할 파일 경로
    """
    # 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 파일 저장
    with output_path.open("w", encoding="utf-8") as fp:
        fp.write(content)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Markdown 리포트 저장 완료: {output_path} (크기: {len(content):,} bytes)")


def main() -> int:
    """
    메인 함수
    
    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    parser = argparse.ArgumentParser(
        description="JSON 리포트에서 Markdown 리포트 생성 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 사용법 (입력 파일과 같은 디렉토리에 .md 파일 생성)
  python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json
  
  # 출력 파일 지정
  python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json --output output/2025-11-12/stage4_results.md
  
  # 타임존 지정
  python scripts/generate_markdown_from_json.py --input output/2025-11-12/stage4_results.json --timezone 0
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON 리포트 파일 경로 (예: output/2025-11-12/stage4_results.json)"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="출력 Markdown 파일 경로 (기본값: 입력 파일과 같은 디렉토리, 확장자만 .md로 변경)"
    )
    
    parser.add_argument(
        "--timezone",
        type=int,
        default=9,
        help="표시 시간대 오프셋 (기본값: 9 = KST)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="상세 정보 출력"
    )
    
    args = parser.parse_args()
    
    # 로깅 설정
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # JSON 리포트 로드
        logger.info(f"JSON 리포트 로드 중: {args.input}")
        json_data = load_json_report(args.input)
        
        # AnalysisState로 변환
        logger.info("AnalysisState 형식으로 변환 중...")
        state = convert_json_to_analysis_state(json_data)
        
        # 타임존 설정 업데이트
        if isinstance(state.get("config"), dict):
            state["config"]["output"]["display_timezone"] = args.timezone
        
        # 리포트 빌더 import (state 변환 후)
        from src.report.report_builder import build_markdown_report
        
        # Markdown 리포트 생성
        logger.info("Markdown 리포트 생성 중...")
        markdown_content = build_markdown_report(
            state,
            timezone_offset=args.timezone
        )
        
        # 출력 파일 경로 결정
        if args.output:
            output_path = args.output
        else:
            # 입력 파일과 같은 디렉토리, 확장자만 .md로 변경
            output_path = args.input.with_suffix(".md")
        
        # Markdown 리포트 저장
        save_markdown_report(markdown_content, output_path)
        
        logger.info("=" * 80)
        logger.info(f"✅ Markdown 리포트 생성 완료: {output_path}")
        logger.info("=" * 80)
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"파일을 찾을 수 없습니다: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        return 1
    except Exception as e:
        logger.critical(f"예상치 못한 오류 발생: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


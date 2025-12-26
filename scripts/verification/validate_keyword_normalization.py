"""
키워드 정규화 결과 검증 스크립트

원본 변형 정보(original_variants)가 올바르게 보존되는지 검증합니다.

사용법:
    python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json
    python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json --markdown output/2025-11-12/143022_summary.md
    python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json --verbose
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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


def load_markdown_report(file_path: Path) -> str:
    """
    Markdown 리포트 파일을 로드합니다.
    
    Args:
        file_path: Markdown 리포트 파일 경로
    
    Returns:
        Markdown 리포트 내용
    
    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    with file_path.open("r", encoding="utf-8") as fp:
        content = fp.read()
    
    return content


def validate_keyword_variants(keyword: Dict[str, Any], keyword_index: int) -> Dict[str, Any]:
    """
    단일 키워드의 원본 변형 정보를 검증합니다.
    
    Args:
        keyword: 키워드 딕셔너리
        keyword_index: 키워드 인덱스 (0부터 시작)
    
    Returns:
        검증 결과 딕셔너리
    """
    result = {
        "keyword_index": keyword_index,
        "term": keyword.get("term", ""),
        "has_original_variants": "original_variants" in keyword,
        "original_variants_count": 0,
        "original_variants": [],
        "is_valid": True,
        "issues": [],
    }
    
    # original_variants 필드 존재 확인
    if not result["has_original_variants"]:
        result["is_valid"] = False
        result["issues"].append("original_variants 필드가 없습니다.")
        return result
    
    original_variants = keyword.get("original_variants", [])
    
    # original_variants가 리스트인지 확인
    if not isinstance(original_variants, list):
        result["is_valid"] = False
        result["issues"].append(f"original_variants가 리스트가 아닙니다: {type(original_variants)}")
        return result
    
    result["original_variants"] = original_variants
    result["original_variants_count"] = len(original_variants)
    
    # original_variants가 비어있지 않은지 확인
    if result["original_variants_count"] == 0:
        result["is_valid"] = False
        result["issues"].append("original_variants가 비어있습니다.")
        return result
    
    # 각 변형이 문자열인지 확인
    for idx, variant in enumerate(original_variants):
        if not isinstance(variant, str):
            result["is_valid"] = False
            result["issues"].append(f"original_variants[{idx}]가 문자열이 아닙니다: {type(variant)}")
    
    # 대표 키워드(term)가 original_variants에 포함되어 있는지 확인 (선택적)
    term = keyword.get("term", "")
    if term and term not in original_variants:
        # 경고 수준 (필수는 아님)
        result["issues"].append(f"대표 키워드 '{term}'가 original_variants에 포함되어 있지 않습니다.")
    
    return result


def validate_all_keywords(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    리포트의 모든 키워드를 검증합니다.
    
    Args:
        report_data: 리포트 데이터 딕셔너리
    
    Returns:
        전체 검증 결과 딕셔너리
    """
    top_keywords = report_data.get("top_keywords", [])
    
    if not top_keywords:
        return {
            "total_keywords": 0,
            "valid_keywords": 0,
            "invalid_keywords": 0,
            "keyword_results": [],
            "is_valid": False,
            "issues": ["top_keywords가 비어있습니다."],
        }
    
    keyword_results = []
    valid_count = 0
    invalid_count = 0
    
    for idx, keyword in enumerate(top_keywords):
        result = validate_keyword_variants(keyword, idx)
        keyword_results.append(result)
        
        if result["is_valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    
    overall_valid = invalid_count == 0
    
    return {
        "total_keywords": len(top_keywords),
        "valid_keywords": valid_count,
        "invalid_keywords": invalid_count,
        "keyword_results": keyword_results,
        "is_valid": overall_valid,
        "issues": [] if overall_valid else [f"{invalid_count}개의 키워드에 문제가 있습니다."],
    }


def validate_markdown_variants(markdown_content: str) -> Dict[str, Any]:
    """
    Markdown 리포트에서 원본 변형 정보가 표시되는지 검증합니다.
    
    Args:
        markdown_content: Markdown 리포트 내용
    
    Returns:
        Markdown 검증 결과 딕셔너리
    """
    result = {
        "has_keywords_section": False,
        "has_variants_column": False,
        "variants_found_count": 0,
        "is_valid": True,
        "issues": [],
    }
    
    # 상위 키워드 섹션 존재 확인
    if "## 상위 키워드" in markdown_content or "## 상위 키워드\n" in markdown_content:
        result["has_keywords_section"] = True
    else:
        result["is_valid"] = False
        result["issues"].append("상위 키워드 섹션이 없습니다.")
        return result
    
    # 원본 변형 컬럼 존재 확인
    if "원본 변형" in markdown_content:
        result["has_variants_column"] = True
        
        # 원본 변형 정보가 실제로 표시되는지 확인 (테이블 행에서 찾기)
        lines = markdown_content.split("\n")
        for line in lines:
            if "|" in line and "원본 변형" not in line:  # 헤더가 아닌 행
                # 원본 변형 컬럼은 보통 3번째 컬럼 (순위, 키워드, 원본 변형, ...)
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:  # 최소 4개 컬럼 (빈 문자열 포함)
                    variants_cell = parts[3] if len(parts) > 3 else ""
                    if variants_cell and variants_cell not in ["원본 변형", "---", ""]:
                        result["variants_found_count"] += 1
    else:
        result["is_valid"] = False
        result["issues"].append("원본 변형 컬럼이 없습니다.")
    
    # 원본 변형 정보가 실제로 표시되었는지 확인
    if result["has_variants_column"] and result["variants_found_count"] == 0:
        result["is_valid"] = False
        result["issues"].append("원본 변형 컬럼은 있지만 실제 데이터가 없습니다.")
    
    return result


def print_validation_report(
    json_result: Dict[str, Any],
    markdown_result: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> None:
    """
    검증 결과를 출력합니다.
    
    Args:
        json_result: JSON 리포트 검증 결과
        markdown_result: Markdown 리포트 검증 결과 (선택적)
        verbose: 상세 정보 출력 여부
    """
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("키워드 정규화 결과 검증 리포트")
    logger.info("=" * 80)
    
    # JSON 리포트 검증 결과
    logger.info("")
    logger.info("📋 JSON 리포트 검증 결과")
    logger.info("-" * 80)
    
    total = json_result["total_keywords"]
    valid = json_result["valid_keywords"]
    invalid = json_result["invalid_keywords"]
    
    logger.info(f"총 키워드 수: {total}개")
    logger.info(f"✅ 유효한 키워드: {valid}개")
    
    if invalid > 0:
        logger.warning(f"❌ 문제가 있는 키워드: {invalid}개")
    else:
        logger.info(f"❌ 문제가 있는 키워드: {invalid}개")
    
    # 전체 검증 상태
    if json_result["is_valid"]:
        logger.info("")
        logger.info("✅ JSON 리포트 검증 통과")
    else:
        logger.warning("")
        logger.warning("❌ JSON 리포트 검증 실패")
        for issue in json_result["issues"]:
            logger.warning(f"  - {issue}")
    
    # 상세 정보 (verbose 모드 또는 문제가 있는 경우)
    if verbose or invalid > 0:
        logger.info("")
        logger.info("상세 검증 결과:")
        logger.info("-" * 80)
        
        for result in json_result["keyword_results"]:
            if not result["is_valid"] or verbose:
                logger.info(f"\n키워드 #{result['keyword_index'] + 1}: {result['term']}")
                logger.info(f"  original_variants 개수: {result['original_variants_count']}개")
                
                if result["original_variants"]:
                    variants_preview = ", ".join(result["original_variants"][:5])
                    if len(result["original_variants"]) > 5:
                        variants_preview += f" ... (총 {len(result['original_variants'])}개)"
                    logger.info(f"  원본 변형: {variants_preview}")
                
                if result["issues"]:
                    logger.warning(f"  문제점:")
                    for issue in result["issues"]:
                        logger.warning(f"    - {issue}")
                elif verbose:
                    logger.info(f"  ✅ 검증 통과")
    
    # Markdown 리포트 검증 결과
    if markdown_result:
        logger.info("")
        logger.info("📄 Markdown 리포트 검증 결과")
        logger.info("-" * 80)
        
        if markdown_result["is_valid"]:
            logger.info("✅ Markdown 리포트 검증 통과")
            logger.info(f"  - 상위 키워드 섹션: ✅")
            logger.info(f"  - 원본 변형 컬럼: ✅")
            logger.info(f"  - 원본 변형 데이터 표시: {markdown_result['variants_found_count']}개")
        else:
            logger.warning("❌ Markdown 리포트 검증 실패")
            for issue in markdown_result["issues"]:
                logger.warning(f"  - {issue}")
    
    # 통합 검증 결과
    logger.info("")
    logger.info("=" * 80)
    
    all_valid = json_result["is_valid"] and (markdown_result is None or markdown_result["is_valid"])
    
    if all_valid:
        logger.info("✅ 전체 검증 통과: 원본 변형 정보가 올바르게 보존되었습니다.")
        logger.info("=" * 80)
    else:
        logger.warning("❌ 검증 실패: 일부 문제가 발견되었습니다.")
        logger.warning("=" * 80)


def main() -> int:
    """
    메인 함수
    
    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    parser = argparse.ArgumentParser(
        description="키워드 정규화 결과 검증 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 기본 검증
  python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json
  
  # Markdown 리포트도 함께 검증
  python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json --markdown output/2025-11-12/143022_summary.md
  
  # 상세 정보 출력
  python scripts/validate_keyword_normalization.py --input output/2025-11-12/143022_summary.json --verbose
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON 리포트 파일 경로 (예: output/2025-11-12/143022_summary.json)"
    )
    
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Markdown 리포트 파일 경로 (선택적, 예: output/2025-11-12/143022_summary.md)"
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
        report_data = load_json_report(args.input)
        
        # 키워드 검증
        logger.info("키워드 정규화 결과 검증 중...")
        json_result = validate_all_keywords(report_data)
        
        # Markdown 리포트 검증 (제공된 경우)
        markdown_result = None
        if args.markdown:
            if args.markdown.exists():
                logger.info(f"Markdown 리포트 로드 중: {args.markdown}")
                markdown_content = load_markdown_report(args.markdown)
                logger.info("Markdown 리포트 검증 중...")
                markdown_result = validate_markdown_variants(markdown_content)
            else:
                logger.warning(f"Markdown 리포트 파일을 찾을 수 없습니다: {args.markdown}")
                logger.warning("Markdown 리포트 검증을 건너뜁니다. JSON 리포트만 검증합니다.")
        
        # 검증 결과 출력
        print_validation_report(json_result, markdown_result, verbose=args.verbose)
        
        # 종료 코드 결정
        all_valid = json_result["is_valid"] and (markdown_result is None or markdown_result["is_valid"])
        return 0 if all_valid else 1
        
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


"""
Slack 파일 업로더

분석 결과 파일(JSON, MD)을 Slack에 업로드합니다.
재시도 로직과 에러 처리를 포함합니다.
"""

import logging
import time
from pathlib import Path
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


logger = logging.getLogger(__name__)

# 업로드 설정
MAX_RETRIES = 3
RETRY_DELAY = 2  # 초
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class FileUploader:
    """Slack 파일 업로더"""

    def __init__(self, client: WebClient):
        """
        파일 업로더를 초기화합니다.

        Args:
            client: Slack WebClient 인스턴스
        """
        self.client = client

    def upload_file(
        self,
        file_path: str | Path,
        channel: str,
        thread_ts: str | None = None,
        title: str | None = None,
        initial_comment: str | None = None,
    ) -> dict[str, Any] | None:
        """
        파일을 Slack에 업로드합니다.

        Args:
            file_path: 업로드할 파일 경로
            channel: 채널 ID
            thread_ts: 스레드 타임스탬프 (선택)
            title: 파일 제목 (선택)
            initial_comment: 첨부 시 코멘트 (선택)

        Returns:
            업로드 결과 또는 실패 시 None
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"파일이 존재하지 않습니다: {file_path}")
            return None

        # 파일 크기 확인
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.error(f"파일 크기 초과: {file_size} bytes (최대 {MAX_FILE_SIZE})")
            return None

        # 파일 제목 설정
        if title is None:
            title = file_path.name

        # 재시도 로직
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"파일 업로드 시도 {attempt}/{MAX_RETRIES}: {file_path}")

                result = self.client.files_upload_v2(
                    channel=channel,
                    file=str(file_path),
                    title=title,
                    initial_comment=initial_comment,
                    thread_ts=thread_ts,
                )

                if result.get("ok"):
                    logger.info(f"파일 업로드 성공: {file_path}")
                    return result

                logger.warning(f"업로드 응답 실패: {result}")

            except SlackApiError as e:
                logger.error(f"Slack API 에러 (시도 {attempt}): {e.response['error']}")

                # Rate limit 처리
                if e.response.get("error") == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 30))
                    logger.info(f"Rate limited, {retry_after}초 후 재시도")
                    time.sleep(retry_after)
                    continue

            except Exception as e:
                logger.error(f"업로드 실패 (시도 {attempt}): {e}")

            # 재시도 대기
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

        logger.error(f"파일 업로드 최종 실패: {file_path}")
        return None

    def upload_analysis_files(
        self,
        output_dir: str | Path,
        channel: str,
        thread_ts: str | None = None,
        include_json: bool = True,
        include_md: bool = True,
    ) -> list[dict[str, Any]]:
        """
        분석 결과 파일들을 업로드합니다.

        Args:
            output_dir: 분석 결과 디렉토리
            channel: 채널 ID
            thread_ts: 스레드 타임스탬프
            include_json: JSON 파일 포함 여부
            include_md: MD 파일 포함 여부

        Returns:
            업로드된 파일 결과 목록
        """
        output_dir = Path(output_dir)
        results = []

        if not output_dir.exists():
            logger.error(f"출력 디렉토리가 존재하지 않습니다: {output_dir}")
            return results

        files_to_upload = []

        # JSON 파일 찾기
        if include_json:
            json_files = list(output_dir.glob("*.json"))
            # 가장 최근 파일 선택
            if json_files:
                latest_json = sorted(json_files, reverse=True)[0]
                files_to_upload.append((latest_json, "📊 분석 데이터 (JSON)"))

        # MD 파일 찾기
        if include_md:
            md_files = (list(output_dir.glob("*_summary.md"))
                        + list(output_dir.glob("report_*.md")))
            if md_files:
                latest_md = sorted(md_files, reverse=True)[0]
                files_to_upload.append((latest_md, "📄 분석 리포트 (Markdown)"))

        # 파일 업로드
        for file_path, comment in files_to_upload:
            result = self.upload_file(
                file_path=file_path,
                channel=channel,
                thread_ts=thread_ts,
                initial_comment=comment,
            )
            if result:
                results.append(result)

        return results

    def upload_content_as_file(
        self,
        content: str,
        filename: str,
        channel: str,
        thread_ts: str | None = None,
        title: str | None = None,
        initial_comment: str | None = None,
        filetype: str | None = None,
    ) -> dict[str, Any] | None:
        """
        문자열 내용을 파일로 업로드합니다.

        Args:
            content: 파일 내용
            filename: 파일 이름
            channel: 채널 ID
            thread_ts: 스레드 타임스탬프
            title: 파일 제목
            initial_comment: 첨부 시 코멘트
            filetype: 파일 타입 (json, markdown 등)

        Returns:
            업로드 결과 또는 실패 시 None
        """
        if title is None:
            title = filename

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"콘텐츠 업로드 시도 {attempt}/{MAX_RETRIES}: {filename}")

                result = self.client.files_upload_v2(
                    channel=channel,
                    content=content,
                    filename=filename,
                    title=title,
                    initial_comment=initial_comment,
                    thread_ts=thread_ts,
                    filetype=filetype,
                )

                if result.get("ok"):
                    logger.info(f"콘텐츠 업로드 성공: {filename}")
                    return result

            except SlackApiError as e:
                logger.error(f"Slack API 에러 (시도 {attempt}): {e.response['error']}")

                if e.response.get("error") == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 30))
                    time.sleep(retry_after)
                    continue

            except Exception as e:
                logger.error(f"콘텐츠 업로드 실패 (시도 {attempt}): {e}")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

        return None


def get_latest_output_dir(base_dir: str | Path) -> Path | None:
    """
    가장 최근 출력 디렉토리를 찾습니다.

    Args:
        base_dir: 기본 출력 디렉토리

    Returns:
        최신 날짜 디렉토리 또는 None
    """
    base_dir = Path(base_dir)

    if not base_dir.exists():
        return None

    # 날짜 형식 디렉토리 찾기
    date_dirs = sorted(
        [d for d in base_dir.iterdir() if d.is_dir()],
        reverse=True,
    )

    return date_dirs[0] if date_dirs else None

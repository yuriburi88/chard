"""
Slack 설정 로더

config/slack.yml 파일에서 설정을 로드하고 관리합니다.
"""

import logging
from pathlib import Path
from typing import Any

import yaml


logger = logging.getLogger(__name__)

# 기본 설정값
DEFAULT_CONFIG = {
    "slack": {
        "enabled": True,
        "socket_mode": True,
        "allowed_channels": [],
    },
    "claude": {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "temperature": 0.7,
        "conversation": {
            "max_history": 10,
            "timeout_minutes": 30,
        },
    },
    "analysis": {
        "timeout_seconds": 300,
        "max_queue_size": 5,
    },
    "response": {
        "include_files": True,
        "include_json": True,
        "include_markdown": True,
        "max_keywords": 5,
    },
    "error": {
        "include_log": True,
    },
}


class SlackConfig:
    """Slack 설정 관리 클래스"""

    def __init__(self, config_path: Path | None = None):
        """
        설정을 로드합니다.

        Args:
            config_path: 설정 파일 경로 (기본값: config/slack.yml)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "slack.yml"

        self._config = self._load_config(config_path)
        logger.info(f"Slack 설정 로드 완료: {config_path}")

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        """설정 파일을 로드합니다."""
        if not config_path.exists():
            logger.warning(f"설정 파일 없음, 기본값 사용: {config_path}")
            return DEFAULT_CONFIG.copy()

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # 기본값과 병합
            return self._merge_config(DEFAULT_CONFIG, config)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return DEFAULT_CONFIG.copy()

    def _merge_config(
        self, default: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """두 설정 딕셔너리를 병합합니다."""
        result = default.copy()

        for key, value in override.items():
            is_dict_merge = (key in result
                             and isinstance(result[key], dict)
                             and isinstance(value, dict))
            if is_dict_merge:
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    @property
    def slack(self) -> dict[str, Any]:
        """Slack 설정을 반환합니다."""
        return self._config.get("slack", {})

    @property
    def claude(self) -> dict[str, Any]:
        """Claude 설정을 반환합니다."""
        return self._config.get("claude", {})

    @property
    def analysis(self) -> dict[str, Any]:
        """분석 설정을 반환합니다."""
        return self._config.get("analysis", {})

    @property
    def response(self) -> dict[str, Any]:
        """응답 설정을 반환합니다."""
        return self._config.get("response", {})

    @property
    def error(self) -> dict[str, Any]:
        """에러 설정을 반환합니다."""
        return self._config.get("error", {})

    # Claude 설정 편의 프로퍼티
    @property
    def claude_model(self) -> str:
        """Claude 모델명을 반환합니다."""
        return self.claude.get("model", "claude-sonnet-4-20250514")

    @property
    def claude_max_tokens(self) -> int:
        """Claude 최대 토큰 수를 반환합니다."""
        return self.claude.get("max_tokens", 4096)

    @property
    def claude_temperature(self) -> float:
        """Claude temperature를 반환합니다."""
        return self.claude.get("temperature", 0.7)

    @property
    def max_history(self) -> int:
        """대화 히스토리 최대 길이를 반환합니다."""
        return self.claude.get("conversation", {}).get("max_history", 10)

    @property
    def conversation_timeout(self) -> int:
        """대화 세션 타임아웃(분)을 반환합니다."""
        return self.claude.get("conversation", {}).get("timeout_minutes", 30)

    # 분석 설정 편의 프로퍼티
    @property
    def analysis_timeout(self) -> int:
        """분석 타임아웃(초)을 반환합니다."""
        return self.analysis.get("timeout_seconds", 300)

    @property
    def max_queue_size(self) -> int:
        """대기열 최대 크기를 반환합니다."""
        return self.analysis.get("max_queue_size", 5)

    # 응답 설정 편의 프로퍼티
    @property
    def include_files(self) -> bool:
        """파일 첨부 여부를 반환합니다."""
        return self.response.get("include_files", True)

    @property
    def max_keywords(self) -> int:
        """표시할 최대 키워드 수를 반환합니다."""
        return self.response.get("max_keywords", 5)


# 싱글톤 인스턴스
_config_instance: SlackConfig | None = None


def get_config() -> SlackConfig:
    """설정 싱글톤 인스턴스를 반환합니다."""
    global _config_instance
    if _config_instance is None:
        _config_instance = SlackConfig()
    return _config_instance


def reload_config() -> SlackConfig:
    """설정을 다시 로드합니다."""
    global _config_instance
    _config_instance = SlackConfig()
    return _config_instance

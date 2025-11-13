"""
설정 관리 모듈

.env 파일과 config.yml 파일을 로드하고 검증하는 Config Manager를 제공합니다.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


@dataclass
class RSSSourceConfig:
    """RSS 소스 설정"""
    name: str
    url: str
    priority: float = 1.0
    timezone: int = 9  # UTC offset (기본값: KST)
    max_articles: int = 50
    hours_back: int = 24


@dataclass
class TelegramSourceConfig:
    """텔레그램 소스 설정
    
    Bot API와 MTProto 두 방식을 모두 지원합니다.
    - Bot API: auth_method="bot_api", bot_token 필요
    - MTProto: auth_method="mtproto", tg_cred_id 필수 (환경변수에서 자격증명 로드)
    
    자격증명 기반 관리:
    - tg_cred_id가 설정되면 환경변수에서 TG_CRED_<ID>_API_ID 등을 로드
    - 동일한 자격증명(api_id, api_hash, phone)으로 여러 채널에 접근 가능
    - 세션 파일은 자격증명별로 하나만 생성 (동일 자격증명의 여러 채널은 같은 세션 파일 공유)
    - api_id, api_hash, phone_number는 환경변수에서만 로드되며, config.yml에 직접 기입하지 않음
    """
    name: str
    channel_id: str
    auth_method: str = "bot_api"  # "bot_api" 또는 "mtproto"
    # Bot API 인증 정보
    bot_token: Optional[str] = None  # Bot API 토큰 (auth_method="bot_api"일 때 사용)
    # 자격증명 기반 관리 (MTProto)
    tg_cred_id: Optional[str] = None  # 텔레그램 자격증명 ID (예: "1", "ONE", "MAIN") - 필수, 환경변수에서 자격증명 정보 로드
    # MTProto 인증 정보 (환경변수에서 로드된 값, config.yml에 직접 기입하지 않음)
    api_id: Optional[int] = None  # Telegram API ID (환경변수에서 로드)
    api_hash: Optional[str] = None  # Telegram API Hash (환경변수에서 로드)
    phone_number: Optional[str] = None  # 전화번호 (환경변수에서 로드, session_file 사용 시 불필요)
    session_file: Optional[str] = None  # 세션 파일 경로 (자동 생성 또는 명시)
    timezone: int = 9
    max_messages: int = 100


@dataclass
class LLMConfig:
    """LLM 분석 옵션"""
    model: str = "gemini-2.0-flash-exp"
    provider: str = "google"
    max_tokens: int = 4000
    temperature: float = 0.1
    chunk_size: int = 50000  # 청크당 최대 토큰 수 (프롬프트 포함)
    parallel_concurrency: int = 3  # LangGraph Stage 4 병렬 처리 동시 실행 수 (0이면 무제한)


@dataclass
class NormalizationConfig:
    """키워드 정규화 옵션"""
    embedding_threshold: float = 0.85  # DBSCAN 클러스터링 임계값 (코사인 유사도)
    dbscan_min_samples: int = 2
    llm_verification_enabled: bool = True
    llm_verification_top_n: int = 20  # 상위 2N개 키워드 선정 (N=10일 때 20개)
    embedding_provider: str = "google"  # "google" 또는 "keybert"
    embedding_model: Optional[str] = None  # provider별 모델명


@dataclass
class OutputConfig:
    """출력 구성"""
    top_keywords_count: int = 10  # 최종 상위 키워드 개수
    summary_paragraphs: int = 4  # 내러티브 요약 문단 수
    log_level: str = "INFO"
    log_filename_strategy: Literal["timestamp", "fixed_window"] = "timestamp"
    log_fixed_window_days: int = 10
    display_timezone: int = 9  # UTC offset (표현용 타임존, 기본값: 9 = KST)
    output_dir: str = "output"


@dataclass
class CollectionPeriodConfig:
    """수집 기간 설정"""
    start_time: Optional[str] = None  # ISO 8601 형식 또는 None
    end_time: Optional[str] = None  # ISO 8601 형식 또는 None
    recent_hours: Optional[int] = None  # 최근 N시간 (start_time/end_time이 없을 때 사용)


@dataclass
class AppConfig:
    """애플리케이션 전체 설정"""
    # 환경 변수
    gemini_api_key: str
    
    # 수집 기간
    collection_period: CollectionPeriodConfig
    
    # 데이터 소스
    rss_sources: List[RSSSourceConfig] = field(default_factory=list)
    telegram_sources: List[TelegramSourceConfig] = field(default_factory=list)
    
    # LLM 설정
    llm: LLMConfig = field(default_factory=LLMConfig)
    
    # 키워드 정규화 설정
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    
    # 출력 설정
    output: OutputConfig = field(default_factory=OutputConfig)


class ConfigManager:
    """설정 파일 로드 및 검증을 담당하는 매니저"""
    
    def __init__(self, config_path: str, env_path: Optional[str] = None):
        """
        ConfigManager 초기화
        
        Args:
            config_path: config.yml 파일 경로
            env_path: .env 파일 경로 (None이면 프로젝트 루트에서 자동 탐색)
        """
        self.config_path = Path(config_path)
        self.env_path = Path(env_path) if env_path else Path.cwd() / ".env"
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
    
    def load_env(self) -> Dict[str, str]:
        """
        .env 파일을 로드합니다.
        
        Returns:
            환경 변수 딕셔너리
        """
        if not self.env_path.exists():
            logger.warning(f".env 파일을 찾을 수 없습니다: {self.env_path}")
            return {}
        
        load_dotenv(dotenv_path=self.env_path)
        
        env_vars = {
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        }
        
        # 필수 환경 변수 검증
        if not env_vars["GEMINI_API_KEY"]:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        logger.info(f".env 파일 로드 완료: {self.env_path}")
        return env_vars
    
    def load_config(self) -> Dict[str, Any]:
        """
        config.yml 파일을 로드합니다.
        
        Returns:
            설정 딕셔너리
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        if not config:
            raise ValueError("설정 파일이 비어있습니다.")
        
        logger.info(f"설정 파일 로드 완료: {self.config_path}")
        return config
    
    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        설정 파일의 유효성을 검증합니다.
        
        Args:
            config: 검증할 설정 딕셔너리
            
        Raises:
            ValueError: 설정이 유효하지 않은 경우
        """
        errors: List[str] = []
        
        # 수집 기간 검증
        if "collection_period" in config:
            period = config["collection_period"]
            if "recent_hours" not in period and "start_time" not in period:
                errors.append("collection_period에 recent_hours 또는 start_time이 필요합니다.")
            if "recent_hours" in period and period["recent_hours"] <= 0:
                errors.append("recent_hours는 0보다 커야 합니다.")
        
        # RSS 소스 검증
        if "rss_sources" in config:
            for idx, source in enumerate(config["rss_sources"]):
                if "name" not in source or "url" not in source:
                    errors.append(f"rss_sources[{idx}]에 name과 url이 필요합니다.")
                if "url" in source and not source["url"].startswith(("http://", "https://")):
                    errors.append(f"rss_sources[{idx}].url이 유효한 URL이 아닙니다.")
        
        # 텔레그램 소스 검증
        if "telegram_sources" in config:
            for idx, source in enumerate(config["telegram_sources"]):
                if "name" not in source or "channel_id" not in source:
                    errors.append(f"telegram_sources[{idx}]에 name과 channel_id가 필요합니다.")
                
                auth_method = source.get("auth_method", "bot_api")
                if auth_method == "bot_api":
                    # Bot API 인증 검증
                    bot_token = source.get("bot_token") or source.get("access_token")  # 하위 호환성
                    if not bot_token:
                        errors.append(f"telegram_sources[{idx}]에 bot_token이 필요합니다 (auth_method=bot_api).")
                elif auth_method == "mtproto":
                    # MTProto 인증 검증: tg_cred_id 필수
                    tg_cred_id = source.get("tg_cred_id")
                    if not tg_cred_id:
                        errors.append(f"telegram_sources[{idx}]에 tg_cred_id가 필요합니다 (auth_method=mtproto).")
                    else:
                        # 환경변수에서 자격증명 확인
                        cred_slug = tg_cred_id.upper().replace("-", "_")
                        env_api_id = os.getenv(f"TG_CRED_{cred_slug}_API_ID")
                        env_api_hash = os.getenv(f"TG_CRED_{cred_slug}_API_HASH")
                        if not env_api_id:
                            errors.append(f"telegram_sources[{idx}]에 tg_cred_id가 설정되었지만 환경변수 TG_CRED_{cred_slug}_API_ID가 없습니다.")
                        if not env_api_hash:
                            errors.append(f"telegram_sources[{idx}]에 tg_cred_id가 설정되었지만 환경변수 TG_CRED_{cred_slug}_API_HASH가 없습니다.")
                    
                    # session_file 검증 (자동 생성되므로 선택사항이지만 명시 가능)
                    # phone_number는 환경변수에서 로드되므로 config.yml에 기입하지 않음
                else:
                    errors.append(f"telegram_sources[{idx}].auth_method는 'bot_api' 또는 'mtproto'여야 합니다.")
        
        # LLM 설정 검증
        if "llm" in config:
            llm = config["llm"]
            if "model" in llm and not llm["model"]:
                errors.append("llm.model이 비어있습니다.")
            if "max_tokens" in llm and llm["max_tokens"] <= 0:
                errors.append("llm.max_tokens는 0보다 커야 합니다.")
            if "temperature" in llm and not (0.0 <= llm["temperature"] <= 2.0):
                errors.append("llm.temperature는 0.0과 2.0 사이여야 합니다.")
        
        # 정규화 설정 검증
        if "normalization" in config:
            norm = config["normalization"]
            if "embedding_threshold" in norm and not (0.0 <= norm["embedding_threshold"] <= 1.0):
                errors.append("normalization.embedding_threshold는 0.0과 1.0 사이여야 합니다.")
            if "llm_verification_top_n" in norm and norm["llm_verification_top_n"] <= 0:
                errors.append("normalization.llm_verification_top_n은 0보다 커야 합니다.")
        
        # 출력 설정 검증
        if "output" in config:
            output = config["output"]
            if "top_keywords_count" in output and output["top_keywords_count"] <= 0:
                errors.append("output.top_keywords_count는 0보다 커야 합니다.")
            if "summary_paragraphs" in output and output["summary_paragraphs"] <= 0:
                errors.append("output.summary_paragraphs는 0보다 커야 합니다.")
        
        if errors:
            error_msg = "설정 검증 실패:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
    
    def parse_config(self, config: Dict[str, Any], env_vars: Dict[str, str]) -> AppConfig:
        """
        설정 딕셔너리를 AppConfig 객체로 변환합니다.
        
        Args:
            config: 설정 딕셔너리
            env_vars: 환경 변수 딕셔너리
            
        Returns:
            AppConfig 객체
        """
        # 수집 기간 파싱
        period_config = config.get("collection_period", {})
        collection_period = CollectionPeriodConfig(
            start_time=period_config.get("start_time"),
            end_time=period_config.get("end_time"),
            recent_hours=period_config.get("recent_hours")
        )
        
        # RSS 소스 파싱
        rss_sources = []
        for source in config.get("rss_sources", []):
            rss_sources.append(RSSSourceConfig(
                name=source["name"],
                url=source["url"],
                priority=source.get("priority", 1.0),
                timezone=source.get("timezone", 9),
                max_articles=source.get("max_articles", 50),
                hours_back=source.get("hours_back", 24)
            ))
        
        # 텔레그램 소스 파싱
        telegram_sources = []
        for source in config.get("telegram_sources", []):
            # 하위 호환성: access_token이 있으면 bot_token으로 변환
            bot_token = source.get("bot_token") or source.get("access_token")
            
            # 자격증명 기반 관리: tg_cred_id가 필수이며 환경변수에서 자격증명 정보 로드
            tg_cred_id = source.get("tg_cred_id")
            session_file = source.get("session_file")
            
            # api_id, api_hash, phone_number는 환경변수에서만 로드 (config.yml에 직접 기입하지 않음)
            api_id = None
            api_hash = None
            phone_number = None
            
            if tg_cred_id:
                # 환경변수에서 자격증명 정보 로드
                cred_slug = tg_cred_id.upper().replace("-", "_")
                env_api_id = os.getenv(f"TG_CRED_{cred_slug}_API_ID")
                env_api_hash = os.getenv(f"TG_CRED_{cred_slug}_API_HASH")
                env_phone = os.getenv(f"TG_CRED_{cred_slug}_PHONE")
                
                if env_api_id:
                    try:
                        api_id = int(env_api_id)
                    except ValueError:
                        logger.warning(f"TG_CRED_{cred_slug}_API_ID가 유효한 정수가 아닙니다: {env_api_id}")
                if env_api_hash:
                    api_hash = env_api_hash
                if env_phone:
                    phone_number = env_phone
                
                # 세션 파일이 명시되지 않았으면 자격증명 기반으로 생성
                if not session_file:
                    session_file = f"secrets/telegram_sessions/tg_cred_{tg_cred_id.lower()}.session"
            else:
                # tg_cred_id가 없으면 MTProto 사용 불가 (Bot API는 문제없음)
                auth_method = source.get("auth_method", "bot_api")
                if auth_method == "mtproto":
                    logger.warning(f"telegram_sources[{len(telegram_sources)}]에 tg_cred_id가 없습니다. MTProto를 사용하려면 tg_cred_id가 필요합니다.")
            
            # session_file 경로 처리: 상대 경로를 절대 경로로 변환
            if session_file:
                session_path = Path(session_file)
                if not session_path.is_absolute():
                    # 상대 경로인 경우 config.yml 위치 기준으로 절대 경로 변환
                    project_root = self.config_path.parent.resolve()
                    session_file = str((project_root / session_path).resolve())
                    logger.debug(f"세션 파일 경로 변환: {source.get('session_file')} → {session_file}")
                else:
                    # 절대 경로인 경우 그대로 사용
                    session_file = str(session_path.resolve())
            
            telegram_sources.append(TelegramSourceConfig(
                name=source["name"],
                channel_id=source["channel_id"],
                auth_method=source.get("auth_method", "bot_api"),
                bot_token=bot_token,
                tg_cred_id=tg_cred_id,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone_number,
                session_file=session_file,
                timezone=source.get("timezone", 9),
                max_messages=source.get("max_messages", 100)
            ))
        
        # LLM 설정 파싱
        llm_config = config.get("llm", {})
        llm = LLMConfig(
            model=llm_config.get("model", "gemini-2.0-flash-exp"),
            provider=llm_config.get("provider", "google"),
            max_tokens=llm_config.get("max_tokens", 4000),
            temperature=llm_config.get("temperature", 0.1),
            chunk_size=llm_config.get("chunk_size", 50000),
            parallel_concurrency=llm_config.get("parallel_concurrency", 3),
        )
        
        # 정규화 설정 파싱
        norm_config = config.get("normalization", {})
        normalization = NormalizationConfig(
            embedding_threshold=norm_config.get("embedding_threshold", 0.85),
            dbscan_min_samples=norm_config.get("dbscan_min_samples", 2),
            llm_verification_enabled=norm_config.get("llm_verification_enabled", True),
            llm_verification_top_n=norm_config.get("llm_verification_top_n", 20),
            embedding_provider=norm_config.get("embedding_provider", "google"),
            embedding_model=norm_config.get("embedding_model")
        )
        
        # 출력 설정 파싱
        output_config = config.get("output", {})
        output = OutputConfig(
            top_keywords_count=output_config.get("top_keywords_count", 10),
            summary_paragraphs=output_config.get("summary_paragraphs", 4),
            log_level=output_config.get("log_level", "INFO"),
            log_filename_strategy=output_config.get("log_filename_strategy", "timestamp"),
            log_fixed_window_days=output_config.get("log_fixed_window_days", 10),
            display_timezone=output_config.get("display_timezone", 9),
            output_dir=output_config.get("output_dir", "output")
        )
        
        return AppConfig(
            gemini_api_key=env_vars["GEMINI_API_KEY"],
            collection_period=collection_period,
            rss_sources=rss_sources,
            telegram_sources=telegram_sources,
            llm=llm,
            normalization=normalization,
            output=output
        )
    
    def load(self) -> AppConfig:
        """
        .env 파일과 config.yml 파일을 로드하고 검증하여 AppConfig를 반환합니다.
        
        Returns:
            검증된 AppConfig 객체
            
        Raises:
            FileNotFoundError: 설정 파일을 찾을 수 없는 경우
            ValueError: 설정이 유효하지 않은 경우
        """
        logger.info("설정 파일 로드 시작...")
        
        # 환경 변수 로드
        env_vars = self.load_env()
        
        # 설정 파일 로드
        config = self.load_config()
        
        # 설정 검증
        self.validate_config(config)
        
        # AppConfig 객체 생성
        app_config = self.parse_config(config, env_vars)
        
        logger.info("설정 파일 로드 완료")
        logger.debug(f"RSS 소스 개수: {len(app_config.rss_sources)}")
        logger.debug(f"텔레그램 소스 개수: {len(app_config.telegram_sources)}")
        logger.debug(f"LLM 모델: {app_config.llm.model}")
        logger.debug(f"최종 키워드 개수: {app_config.output.top_keywords_count}")
        
        return app_config


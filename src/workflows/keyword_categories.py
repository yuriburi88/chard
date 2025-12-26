"""
키워드 카테고리 분류 규칙

키워드를 Macro, Crypto 카테고리로 분류합니다.
(기존 Crypto Native + Crypto-Macro를 Crypto로 통합)
"""

from dataclasses import dataclass
from typing import Literal


# 새로운 2-카테고리 시스템
CategoryType = Literal["macro", "crypto"]

# 하위 호환성을 위한 기존 타입 (deprecated)
LegacyCategoryType = Literal["macro", "crypto_native", "crypto_macro"]


# ============================================================================
# Macro 키워드: 거시경제 요인
# ============================================================================
MACRO_KEYWORDS = {
    # 금리 및 통화정책
    "금리",
    "기준금리",
    "금리인상",
    "금리인하",
    "금리동결",
    "금리정책",
    "금리 인하",
    "금리 인상",
    "연준",
    "fed",
    "federal reserve",
    "fomc",
    "제롬파월",
    "파월",
    "ecb",
    "유럽중앙은행",
    "boe",
    "영란은행",
    "일본은행",
    "boj",
    "한국은행",
    "bok",
    "중앙은행",
    "통화정책",
    "긴축",
    "완화",
    # 인플레이션 및 경제지표
    "인플레이션",
    "물가",
    "cpi",
    "pce",
    "ppi",
    "소비자물가지수",
    "inflation",
    "gdp",
    "경제성장률",
    "실업률",
    "고용",
    "비농업고용",
    "nfp",
    "pmi",
    "제조업지수",
    "소비자신뢰지수",
    "경제 성장",
    "경제 지표",
    "경기 전망",
    # 환율 및 통화
    "달러",
    "달러인덱스",
    "dxy",
    "환율",
    "원달러",
    "엔달러",
    "유로달러",
    "강달러",
    "약달러",
    "외환",
    "통화가치",
    "외환 시장",
    "fx",
    # 주식시장
    "나스닥",
    "nasdaq",
    "s&p500",
    "sp500",
    "다우존스",
    "dow",
    "주식시장",
    "증시",
    "코스피",
    "코스닥",
    "미국증시",
    "tech주",
    "기술주",
    "빅테크",
    # 채권 및 금리상품
    "국채",
    "채권",
    "수익률",
    "yield",
    "10년물",
    "2년물",
    "채권수익률",
    "장단기금리차",
    "역전",
    # 경기 및 경제 상황
    "경기침체",
    "recession",
    "경기둔화",
    "경기회복",
    "경기확장",
    "스태그플레이션",
    "디플레이션",
    "경기순환",
    "경제",
    "한국 경제",
    "미국 경제",
    "글로벌 경제",
    "트럼프"
    # 정부 및 정책
    "재정정책",
    "양적완화",
    "qe",
    "qt",
    "양적긴축",
    "테이퍼링",
    "부채한도",
    "정부지출",
    "재정적자",
    "세금",
    "세율",
    # 지정학적 이슈
    "전쟁",
    "분쟁",
    "제재",
    "무역전쟁",
    "관세",
    "러시아",
    "우크라이나",
    "중동",
    "대만",
    "중국",
    # 은행 및 금융시스템
    "은행위기",
    "금융위기",
    "뱅크런",
    "예금보험",
    "금융시스템",
    "신용경색",
    "유동성위기",
    "svb",
    "실리콘밸리은행",
    # 기타 금융/투자
    "연기금",
    "국민연금",
    "pension",
    "sovereign wealth",
    # 규제 기관 (일반)
    "sec",
    "증권거래위원회",
    "cftc",
    "금융당국",
    "규제",
    "regulation",
    "고용지표",
}

# ============================================================================
# Crypto Native 키워드: 암호화폐 고유 동향
# ============================================================================
CRYPTO_NATIVE_KEYWORDS = {
    # 주요 암호화폐 (추가)
    "비트코인",
    "bitcoin",
    "btc",
    "이더리움",
    "ethereum",
    "eth",
    "솔라나",
    "solana",
    "sol",
    "리플",
    "ripple",
    "xrp",
    "카르다노",
    "cardano",
    "ada",
    "폴카닷",
    "polkadot",
    "dot",
    "아발란체",
    "avalanche",
    "avax",
    "폴리곤",
    "polygon",
    "matic",
    "체인링크",
    "chainlink",
    "link",
    "코스모스",
    "cosmos",
    "atom",
    # 블록체인 기술
    "블록체인",
    "blockchain",
    "합의알고리즘",
    "pow",
    "pos",
    "샤딩",
    "sharding",
    "롤업",
    "rollup",
    "레이어1",
    "l1",
    "레이어2",
    "l2",
    "사이드체인",
    "sidechain",
    "제로지식증명",
    "zk",
    "zkp",
    "영지식증명",
    # DeFi (탈중앙화 금융)
    "디파이",
    "defi",
    "탈중앙화금융",
    "탈중앙화거래소",
    "dex",
    "유동성풀",
    "amm",
    "자동마켓메이커",
    "유동성마이닝",
    "yield farming",
    "이자농사",
    "스테이킹",
    "staking",
    "lending",
    "대출",
    "borrowing",
    "차입",
    "tvl",
    "총예치금",
    "프로토콜수익",
    "protocol revenue",
    "유니스왑",
    "uniswap",
    "커브",
    "curve",
    "aave",
    "컴파운드",
    "compound",
    # NFT 및 메타버스
    "nft",
    "non-fungible token",
    "대체불가토큰",
    "메타버스",
    "metaverse",
    "가상세계",
    "pfp",
    "generative art",
    "opensea",
    "블러",
    "blur",
    # 프로토콜 및 프로젝트
    "아비트럼",
    "arbitrum",
    "옵티미즘",
    "optimism",
    "베이스",
    "base",
    "zksync",
    # 온체인 데이터
    "온체인",
    "onchain",
    "해시레이트",
    "hashrate",
    "난이도",
    "difficulty",
    "네트워크활동",
    "트랜잭션",
    "transaction",
    "gas",
    "가스비",
    "밈풀",
    "mempool",
    "블록생성",
    "블록시간",
    "활성주소",
    "active address",
    "고래",
    "whale",
    # 토큰 경제학
    "토큰이코노미",
    "tokenomics",
    "토큰분배",
    "베스팅",
    "vesting",
    "에어드랍",
    "airdrop",
    "토큰발행",
    "mint",
    "burn",
    "소각",
    "인플레이션율",
    "emission",
    "리워드",
    # 거버넌스
    "dao",
    "거버넌스",
    "governance",
    "투표",
    "제안",
    "proposal",
    "커뮤니티",
    "decentralization",
    "탈중앙화",
    # 스마트컨트랙트 및 개발
    "스마트컨트랙트",
    "smart contract",
    "dapp",
    "디앱",
    "evm",
    "solidity",
    "rust",
    "move",
    "오픈소스",
    "github",
    "audit",
    "감사",
    "보안감사",
    # Web3 & 신기술 트렌드
    "web3",
    "웹3",
    "web3게임",
    "gamefi",
    "p2e",
    "socialfi",
    "depin",
    "탈중앙화id",
    "did",
    "ai",
    "인공지능",
    "ai agent",
    "ai crypto",
    "rwa",
    "real world assets",
    "실물자산토큰화",
    "meme",
    "밈코인",
    "meme coin",
    "디지털자산",
}

# ============================================================================
# Crypto-Macro 키워드: 교차 영향
# ============================================================================
CRYPTO_MACRO_KEYWORDS = {
    # ETF 및 기관 투자
    "etf",
    "현물etf",
    "비트코인etf",
    "이더리움etf",
    "그레이스케일",
    "grayscale",
    "gbtc",
    "ethe",
    "블랙록",
    "blackrock",
    "피델리티",
    "fidelity",
    "ark",
    "캐시우드",
    "cathie wood",
    "기관투자",
    "기관자금",
    "기관 투자",
    "institutional",
    "월가",
    "wall street",
    # 상장 및 거래소
    "상장",
    "listing",
    "거래소",
    "exchange",
    "코인베이스",
    "coinbase",
    "바이낸스",
    "binance",
    "업비트",
    "빗썸",
    "kraken",
    "크라켄",
    "upbit",
    "해킹",
    "hacking",
    "보안",
    "security",
    "해킹/보안",
    "업비트 해킹",
    "바이낸스 해킹",
    # 규제 및 법률
    "sec",
    "증권거래위원회",
    "cftc",
    "finra",
    "규제",
    "regulation",
    "규제당국",
    "금융당국",
    "증권",
    "상품",
    "commodity",
    "규제준수",
    "compliance",
    "라이센스",
    "면허",
    "소송",
    "lawsuit",
    "판결",
    "디지털 자산 규제",
    "암호화폐 규제",
    # CBDC 및 정부 디지털화폐
    "cbdc",
    "중앙은행디지털화폐",
    "디지털달러",
    "디지털위안",
    "디지털유로",
    "e-krw",
    "디지털원화",
    # 결제 및 채택
    "결제",
    "payment",
    "송금",
    "remittance",
    "크로스보더",
    "paypal",
    "페이팔",
    "visa",
    "비자",
    "mastercard",
    "마스터카드",
    "스트라이프",
    "stripe",
    "square",
    "스퀘어",
    "엘살바도르",
    "법정화폐",
    "legal tender",
    # 자산운용 및 투자상품
    "자산운용",
    "asset management",
    "헤지펀드",
    "hedge fund",
    "포트폴리오",
    "portfolio",
    "분산투자",
    "diversification",
    # 상관관계
    "상관관계",
    "correlation",
    "디커플링",
    "decoupling",
    "리스크온",
    "risk-on",
    "리스크오프",
    "risk-off",
    "안전자산",
    "safe haven",
    "위험자산",
    "risk asset",
    # 채택 및 메인스트림
    "채택",
    "adoption",
    "mainstream",
    "메인스트림",
    "대량채택",
    "mass adoption",
    "일반투자자",
    "retail",
    # 스테이블코인 (매크로와 크립토의 교차점)
    "스테이블코인",
    "stablecoin",
    "usdt",
    "usdc",
    "dai",
    "테더",
    "tether",
    "circle",
    # AI 및 웹3 (기업 투자 관련)
    "ai 및 웹3",
    "ai/web3",
}

# ============================================================================
# Crypto 통합 키워드: Crypto Native + Crypto-Macro 병합
# ============================================================================
CRYPTO_KEYWORDS = CRYPTO_NATIVE_KEYWORDS | CRYPTO_MACRO_KEYWORDS


@dataclass
class KeywordCategory:
    """키워드 카테고리 정보"""

    keyword: str
    category: CategoryType
    confidence: float  # 0.0 ~ 1.0


@dataclass
class MultiLabelCategory:
    """멀티 레이블 카테고리 정보"""

    keyword: str
    categories: dict[CategoryType, float]  # 카테고리별 신뢰도


class KeywordCategorizer:
    """키워드를 카테고리별로 분류하는 클래스 (2-카테고리: Macro, Crypto)"""

    def __init__(self, dynamic_manager=None):
        """
        Args:
            dynamic_manager: DynamicKeywordManager 인스턴스 (선택사항)
                            제공되면 동적 학습된 키워드도 함께 사용됩니다.
        """
        # 고정 키워드 세트 (2-카테고리 시스템)
        self.macro_set = {kw.lower() for kw in MACRO_KEYWORDS}
        self.crypto_set = {kw.lower() for kw in CRYPTO_KEYWORDS}

        # 하위 호환성을 위한 레거시 세트 (deprecated)
        self.crypto_native_set = {kw.lower() for kw in CRYPTO_NATIVE_KEYWORDS}
        self.crypto_macro_set = {kw.lower() for kw in CRYPTO_MACRO_KEYWORDS}

        # 동적 키워드 병합
        if dynamic_manager:
            dynamic_keywords = dynamic_manager.get_all_keywords()
            self.macro_set.update(dynamic_keywords.get("macro", set()))
            # crypto_native와 crypto_macro를 모두 crypto로 병합
            self.crypto_set.update(dynamic_keywords.get("crypto", set()))
            self.crypto_set.update(dynamic_keywords.get("crypto_native", set()))
            self.crypto_set.update(dynamic_keywords.get("crypto_macro", set()))

    def categorize_keyword(self, keyword: str) -> KeywordCategory:
        """
        단일 키워드를 카테고리로 분류 (2-카테고리: Macro, Crypto)

        Args:
            keyword: 분류할 키워드

        Returns:
            KeywordCategory 객체
        """
        keyword_lower = keyword.lower()

        # 정확히 일치하는 경우
        if keyword_lower in self.macro_set:
            return KeywordCategory(keyword, "macro", 1.0)
        if keyword_lower in self.crypto_set:
            return KeywordCategory(keyword, "crypto", 1.0)

        # 부분 매칭 (신뢰도 낮음)
        max_confidence = 0.0
        best_category: CategoryType = "crypto"  # 기본값

        # Macro 부분 매칭 확인
        for ref_kw in self.macro_set:
            if ref_kw in keyword_lower or keyword_lower in ref_kw:
                confidence = len(ref_kw) / max(len(keyword_lower), len(ref_kw))
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_category = "macro"

        # Crypto 부분 매칭 확인
        if max_confidence < 0.5:
            for ref_kw in self.crypto_set:
                if ref_kw in keyword_lower or keyword_lower in ref_kw:
                    confidence = len(ref_kw) / max(len(keyword_lower), len(ref_kw))
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_category = "crypto"

        # 매칭 실패 시 기본값 (crypto, 낮은 신뢰도)
        if max_confidence == 0.0:
            max_confidence = 0.3

        return KeywordCategory(keyword, best_category, max_confidence)

    def categorize_keywords(
        self, keywords: list[dict], min_confidence: float = 0.5
    ) -> dict[CategoryType, list[dict]]:
        """
        키워드 리스트를 카테고리별로 분류 (2-카테고리: Macro, Crypto)

        Args:
            keywords: 키워드 딕셔너리 리스트 (AggregatorNode 출력 형식)
            min_confidence: 최소 신뢰도 임계값

        Returns:
            카테고리별로 분류된 키워드 딕셔너리
        """
        categorized: dict[CategoryType, list[dict]] = {"macro": [], "crypto": []}

        for kw_dict in keywords:
            term = kw_dict.get("term", "")
            if not term:
                continue

            category_info = self.categorize_keyword(term)

            # 신뢰도 임계값 확인
            if category_info.confidence >= min_confidence:
                # 키워드 딕셔너리에 카테고리 정보 추가
                kw_dict_with_category = kw_dict.copy()
                kw_dict_with_category["category"] = category_info.category
                kw_dict_with_category["category_confidence"] = category_info.confidence

                categorized[category_info.category].append(kw_dict_with_category)
            else:
                # 신뢰도 낮은 경우 crypto로 기본 분류
                kw_dict_with_category = kw_dict.copy()
                kw_dict_with_category["category"] = "crypto"
                kw_dict_with_category["category_confidence"] = 0.3
                categorized["crypto"].append(kw_dict_with_category)

        return categorized

    def categorize_keyword_multilabel(
        self, keyword: str, category_thresholds: dict[CategoryType, float] = None
    ) -> MultiLabelCategory:
        """
        단일 키워드를 멀티 레이블 방식으로 분류 (2-카테고리: Macro, Crypto)

        Args:
            keyword: 분류할 키워드
            category_thresholds: 카테고리별 최소 신뢰도 임계값 (선택사항)
                예: {"macro": 0.4, "crypto": 0.3}

        Returns:
            MultiLabelCategory 객체 (각 카테고리별 신뢰도 포함)
        """
        keyword_lower = keyword.lower()
        categories: dict[CategoryType, float] = {}

        # 기본 임계값: 카테고리별 차등 적용
        if category_thresholds is None:
            category_thresholds = {
                "macro": 0.4,  # 거시경제: 중간 수준
                "crypto": 0.3,  # 암호화폐: 관대 (기본 카테고리)
            }

        # Macro 카테고리 매칭 확인
        macro_confidence = self._calculate_category_confidence(
            keyword_lower, self.macro_set
        )
        if macro_confidence >= category_thresholds.get("macro", 0.0):
            categories["macro"] = macro_confidence

        # Crypto 카테고리 매칭 확인
        crypto_confidence = self._calculate_category_confidence(
            keyword_lower, self.crypto_set
        )
        if crypto_confidence >= category_thresholds.get("crypto", 0.0):
            categories["crypto"] = crypto_confidence

        # 아무 카테고리에도 매칭되지 않으면 crypto를 기본값으로
        if not categories:
            categories["crypto"] = 0.25  # 기본값 약간 낮춤

        return MultiLabelCategory(keyword, categories)

    def _tokenize_keyword(self, keyword: str) -> list[str]:
        """
        복합 키워드를 토큰화합니다.

        예: "BTC (비트코인)" → ["btc", "비트코인"]
            "AI (인공지능)" → ["ai", "인공지능"]

        Args:
            keyword: 원본 키워드

        Returns:
            토큰 리스트 (소문자)
        """
        import re

        # 괄호 안팎 분리: "BTC (비트코인)" → ["BTC", "비트코인"]
        tokens = re.split(r"[(),/\[\]{}]", keyword)

        # 공백 제거 및 소문자 변환
        tokens = [t.strip().lower() for t in tokens if t.strip()]

        return tokens

    def _calculate_category_confidence(
        self, keyword_lower: str, category_set: set
    ) -> float:
        """
        특정 카테고리에 대한 키워드의 신뢰도를 계산합니다.

        복합 키워드는 토큰화하여 각 토큰의 최대 매칭도를 사용합니다.

        Args:
            keyword_lower: 소문자로 변환된 키워드
            category_set: 카테고리 키워드 집합

        Returns:
            신뢰도 (0.0 ~ 1.0)
        """
        # 1. 원본 키워드 정확 일치
        if keyword_lower in category_set:
            return 1.0

        # 2. 토큰화된 키워드로 정확 일치 확인
        tokens = self._tokenize_keyword(keyword_lower)
        for token in tokens:
            if token in category_set:
                return 1.0  # 토큰 중 하나라도 정확 일치하면 1.0

        # 3. 부분 매칭 확인 (원본 키워드)
        max_confidence = 0.0
        for ref_kw in category_set:
            if ref_kw in keyword_lower or keyword_lower in ref_kw:
                confidence = len(ref_kw) / max(len(keyword_lower), len(ref_kw))
                max_confidence = max(max_confidence, confidence)

        # 4. 부분 매칭 확인 (토큰화된 키워드)
        for token in tokens:
            for ref_kw in category_set:
                if ref_kw in token or token in ref_kw:
                    confidence = len(ref_kw) / max(len(token), len(ref_kw))
                    max_confidence = max(max_confidence, confidence)

        return max_confidence

    def categorize_keywords_multilabel(
        self,
        keywords: list[dict],
        min_confidence: float = None,
        category_thresholds: dict[CategoryType, float] = None,
    ) -> dict[CategoryType, list[dict]]:
        """
        키워드 리스트를 멀티 레이블 방식으로 카테고리별 분류 (2-카테고리: Macro, Crypto)

        각 키워드는 여러 카테고리에 동시에 속할 수 있습니다.

        Args:
            keywords: 키워드 딕셔너리 리스트 (AggregatorNode 출력 형식)
            min_confidence: 전체 카테고리에 적용할 최소 신뢰도 (선택사항, deprecated)
            category_thresholds: 카테고리별 최소 신뢰도 임계값 (선택사항)
                예: {"macro": 0.4, "crypto": 0.3}

        Returns:
            카테고리별로 분류된 키워드 딕셔너리 (중복 허용)
        """
        # min_confidence가 제공되면 모든 카테고리에 동일하게 적용
        if min_confidence is not None and category_thresholds is None:
            category_thresholds = {
                "macro": min_confidence,
                "crypto": min_confidence,
            }

        categorized: dict[CategoryType, list[dict]] = {"macro": [], "crypto": []}

        for kw_dict in keywords:
            term = kw_dict.get("term", "")
            if not term:
                continue

            multi_category = self.categorize_keyword_multilabel(
                term, category_thresholds
            )

            # multi_category.categories에는 이미 임계값을 통과한 카테고리만 포함됨
            for category, confidence in multi_category.categories.items():
                kw_dict_with_category = kw_dict.copy()
                kw_dict_with_category["categories"] = multi_category.categories
                kw_dict_with_category["category_confidence"] = confidence

                categorized[category].append(kw_dict_with_category)

        return categorized

    def get_category_summary(
        self, categorized: dict[CategoryType, list[dict]]
    ) -> dict[str, int]:
        """
        카테고리별 키워드 수 요약 (2-카테고리: Macro, Crypto)

        Args:
            categorized: categorize_keywords 반환값

        Returns:
            카테고리별 키워드 개수
        """
        return {
            "macro": len(categorized.get("macro", [])),
            "crypto": len(categorized.get("crypto", [])),
            "total": sum(len(v) for v in categorized.values()),
        }

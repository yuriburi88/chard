"""
Slack 메시지 포맷터

분석 결과를 Slack 메시지 형식으로 변환합니다.
Block Kit 형식을 지원하여 더 나은 UX를 제공합니다.
"""

import logging
from typing import Any


logger = logging.getLogger(__name__)


# 시장 심리 이모지 매핑
SENTIMENT_EMOJI = {
    "bullish": "🟢",
    "bearish": "🔴",
    "neutral": "⚪",
    "very_bullish": "🟢🟢",
    "very_bearish": "🔴🔴",
}

# 카테고리 이모지 매핑
CATEGORY_EMOJI = {
    "macro": "🌍",
    "crypto": "₿",
    "crypto_native": "🔗",
    "regulation": "⚖️",
    "defi": "💱",
    "nft": "🖼️",
}


def format_loading_message(action: str = "분석") -> dict[str, Any]:
    """
    로딩 중 메시지를 생성합니다.

    Args:
        action: 진행 중인 작업 이름

    Returns:
        Slack 메시지 블록
    """
    return {
        "text": f"{action} 중... ⏳",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{action} 중입니다...* ⏳\n잠시만 기다려 주세요.",
                },
            }
        ],
    }


def format_error_message(
    error_type: str = "general",
    details: str | None = None,
) -> dict[str, Any]:
    """
    에러 메시지를 포맷팅합니다.

    Args:
        error_type: 에러 유형 (general, timeout, rate_limit, connection)
        details: 추가 에러 상세 정보

    Returns:
        Slack 메시지 블록
    """
    error_messages = {
        "general": "죄송합니다, 요청을 처리하는 중 오류가 발생했습니다. 😢",
        "timeout": "분석 시간이 초과되었습니다. ⏱️",
        "rate_limit": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요. ⏳",
        "connection": "서버 연결에 실패했습니다. 🌐",
        "not_found": "요청한 데이터를 찾을 수 없습니다. 🔍",
    }

    message = error_messages.get(error_type, error_messages["general"])

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *오류 발생*\n{message}",
            },
        }
    ]

    if details:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"상세: {details[:200]}",
                }
            ],
        })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "잠시 후 다시 시도해 주세요.",
        },
    })

    return {
        "text": message,
        "blocks": blocks,
    }


def format_keywords_table(
    keywords: list[dict[str, Any]],
    limit: int = 10,
) -> str:
    """
    키워드 목록을 테이블 형식 문자열로 변환합니다.

    Args:
        keywords: 키워드 리스트
        limit: 표시할 최대 키워드 수

    Returns:
        포맷팅된 키워드 테이블 문자열
    """
    if not keywords:
        return "_키워드 데이터가 없습니다._"

    lines = []
    for i, kw in enumerate(keywords[:limit], 1):
        if isinstance(kw, dict):
            term = kw.get("term", kw.get("keyword", "Unknown"))
            score = kw.get("score", kw.get("importance", 0))
            category = kw.get("category", "")

            # 카테고리 이모지
            cat_emoji = CATEGORY_EMOJI.get(category.lower(), "") if category else ""

            # 점수 바 시각화 (최대 5칸)
            score_normalized = min(score / 20, 1.0)  # 100점 만점 기준
            filled = int(score_normalized * 5)
            score_bar = "█" * filled + "░" * (5 - filled)

            lines.append(f"{i}. *{term}* {cat_emoji}")
            lines.append(f"   `{score_bar}` {score:.1f}점")
        else:
            lines.append(f"{i}. {kw}")

    return "\n".join(lines)


def format_market_sentiment(
    sentiment: dict[str, Any] | None,
) -> str:
    """
    시장 심리를 포맷팅합니다.

    Args:
        sentiment: 시장 심리 데이터

    Returns:
        포맷팅된 시장 심리 문자열
    """
    if not sentiment:
        return "_시장 심리 데이터 없음_"

    direction = sentiment.get("direction", "neutral").lower()
    confidence = sentiment.get("confidence", 0)

    emoji = SENTIMENT_EMOJI.get(direction, "⚪")

    # 방향 한국어 변환
    direction_kr = {
        "bullish": "상승",
        "bearish": "하락",
        "neutral": "중립",
        "very_bullish": "강한 상승",
        "very_bearish": "강한 하락",
    }.get(direction, direction)

    return f"{emoji} *{direction_kr}* (신뢰도 {confidence:.0%})"


def format_analysis_result(
    data: dict[str, Any],
    include_keywords: bool = True,
    include_sentiment: bool = True,
    include_insights: bool = True,
) -> dict[str, Any]:
    """
    분석 결과를 Slack Block Kit 형식으로 변환합니다.

    Args:
        data: 분석 결과 데이터
        include_keywords: 키워드 포함 여부
        include_sentiment: 시장 심리 포함 여부
        include_insights: 인사이트 포함 여부

    Returns:
        Slack 메시지 블록
    """
    blocks = []

    # 헤더
    date_str = data.get("date", "최근")
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"📊 {date_str} 시장 분석 리포트",
            "emoji": True,
        },
    })

    blocks.append({"type": "divider"})

    # 시장 심리 섹션
    if include_sentiment:
        sentiment = data.get("insights", {}).get("market_sentiment")
        if sentiment:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📈 시장 심리*\n{format_market_sentiment(sentiment)}",
                },
            })

    # 키워드 섹션
    if include_keywords:
        keywords = data.get("aggregated_keywords", data.get("keywords", []))
        if keywords:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔑 주요 키워드*\n{format_keywords_table(keywords, 5)}",
                },
            })

    # 인사이트 섹션
    if include_insights:
        insights = data.get("insights", {})

        # 매크로 내러티브
        macro_narrative = insights.get("macro_narrative")
        if macro_narrative:
            # 너무 길면 잘라서 표시
            narrative_text = macro_narrative[:500]
            if len(macro_narrative) > 500:
                narrative_text += "..."

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🌍 매크로 인사이트*\n{narrative_text}",
                },
            })

        # 크립토 내러티브
        crypto_narrative = insights.get("crypto_narrative")
        if crypto_narrative:
            narrative_text = crypto_narrative[:500]
            if len(crypto_narrative) > 500:
                narrative_text += "..."

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*₿ 크립토 인사이트*\n{narrative_text}",
                },
            })

    # 품질 점수
    quality = data.get("quality_score", data.get("quality", {}))
    if quality:
        if isinstance(quality, dict):
            score = quality.get("overall", quality.get("score", 0))
        else:
            score = quality

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"✅ 분석 품질: {score:.1f}%",
                }
            ],
        })

    blocks.append({"type": "divider"})

    # 푸터
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "_CHARD 분석 리포트 | 더 자세한 내용은 첨부 파일을 확인하세요_",
            }
        ],
    })

    # 텍스트 요약 (블록 미지원 클라이언트용)
    text_summary = f"📊 {date_str} 시장 분석 리포트"

    return {
        "text": text_summary,
        "blocks": blocks,
    }


def format_simple_response(text: str) -> dict[str, Any]:
    """
    간단한 텍스트 응답을 포맷팅합니다.

    Args:
        text: 응답 텍스트

    Returns:
        Slack 메시지
    """
    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                },
            }
        ],
    }


def format_help_message() -> dict[str, Any]:
    """
    도움말 메시지를 생성합니다.

    Returns:
        Slack 메시지 블록
    """
    help_text = """*CHARD 사용 가이드* 🤖

*기본 명령어*
• `시황 알려줘` - 최신 시장 분석
• `비트코인 분석해줘` - 특정 키워드 분석
• `RSS만 분석해줘` - 소스 필터링
• `키워드 알려줘` - 트렌딩 키워드

*후속 질문*
• `왜 이게 1위야?` - 이전 결과 설명
• `더 자세히` - 상세 분석

*팁*
• 분석은 1-2분 정도 소요됩니다
• DM으로도 대화할 수 있습니다"""

    return {
        "text": "CHARD 사용 가이드",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": help_text,
                },
            }
        ],
    }

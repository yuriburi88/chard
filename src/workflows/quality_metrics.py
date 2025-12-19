"""
내러티브 및 키워드 품질 평가 시스템 (Phase 3)

- 키워드 분류 품질 평가 (2-카테고리: Macro, Crypto)
- 내러티브 생성 품질 평가 (3단계: Macro → Crypto → Integrated)
- 동적 학습 효과 측정
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """품질 평가 메트릭"""

    # 키워드 분류 품질
    total_keywords: int
    categorized_keywords: Dict[str, int]  # {category: count}
    category_balance_score: float  # 0.0 ~ 1.0 (균형도)

    # 내러티브 품질
    narratives_generated: Dict[str, bool]  # {category: generated}
    narrative_lengths: Dict[str, int]  # {category: character_count}
    narrative_quality_score: float  # 0.0 ~ 1.0

    # 동적 학습 효과
    dynamic_keywords_learned: int
    dynamic_keywords_used: int
    learning_effectiveness: float  # 0.0 ~ 1.0

    # 전체 품질 점수
    overall_quality_score: float  # 0.0 ~ 1.0

    # 경고 및 권장사항
    warnings: List[str]
    recommendations: List[str]


class QualityEvaluator:
    """품질 평가기"""

    def __init__(self):
        self.min_keywords_per_category = 1  # 카테고리별 최소 키워드 수
        self.min_narrative_length = 200     # 내러티브 최소 길이 (한글 기준)
        self.target_category_balance = 0.3  # 목표 균형도 (최소 30%)

    def evaluate(
        self,
        categorized_keywords: Dict[str, List[Dict]],
        narratives: Dict[str, str],
        dynamic_keywords_cache: Dict = None
    ) -> QualityMetrics:
        """
        전체 품질을 평가합니다.

        Args:
            categorized_keywords: 카테고리별 키워드 딕셔너리
            narratives: 카테고리별 내러티브 텍스트
            dynamic_keywords_cache: 동적 키워드 캐시 (선택사항)

        Returns:
            QualityMetrics 객체
        """
        warnings = []
        recommendations = []

        # 1. 키워드 분류 품질 평가 (2-카테고리 시스템)
        keyword_counts = {
            "macro": len(categorized_keywords.get("macro", [])),
            "crypto": len(categorized_keywords.get("crypto", []))
        }
        total_keywords = sum(keyword_counts.values())

        # 카테고리 균형도 계산 (엔트로피 기반)
        balance_score = self._calculate_balance_score(keyword_counts)

        # 2. 내러티브 품질 평가 (3단계: macro, crypto, integrated)
        narratives_generated = {}
        narrative_lengths = {}

        for category in ["macro", "crypto", "integrated"]:
            narrative_text = narratives.get(category, "")
            narratives_generated[category] = len(narrative_text) > 0
            narrative_lengths[category] = len(narrative_text)

            # 경고: 내러티브 미생성 (integrated 제외)
            if not narratives_generated[category] and category != "integrated":
                warnings.append(f"{category} 내러티브가 생성되지 않았습니다.")
                recommendations.append(
                    f"{category} 카테고리의 키워드를 더 추가하거나 임계값을 낮춰보세요."
                )

            # 경고: 내러티브 너무 짧음
            elif narrative_lengths[category] < self.min_narrative_length and narratives_generated[category]:
                warnings.append(
                    f"{category} 내러티브가 너무 짧습니다 ({narrative_lengths[category]}자)."
                )

        narrative_quality = self._calculate_narrative_quality(narratives_generated, narrative_lengths)

        # 3. 동적 학습 효과 측정
        dynamic_learned = 0
        dynamic_used = 0

        if dynamic_keywords_cache:
            dynamic_learned = len(dynamic_keywords_cache)
            # 동적 키워드가 실제로 사용되었는지 확인
            dynamic_used = self._count_dynamic_keywords_used(
                categorized_keywords,
                dynamic_keywords_cache
            )

        learning_effectiveness = (
            dynamic_used / dynamic_learned if dynamic_learned > 0 else 0.0
        )

        # 경고: 동적 학습 효과 낮음
        if dynamic_learned > 0 and learning_effectiveness < 0.3:
            warnings.append(
                f"동적 학습된 키워드 {dynamic_learned}개 중 {dynamic_used}개만 사용되었습니다."
            )
            recommendations.append(
                "동적 학습 임계값(min_frequency)을 조정하거나 학습 알고리즘을 개선하세요."
            )

        # 4. 카테고리별 키워드 부족 경고
        for category, count in keyword_counts.items():
            if count < self.min_keywords_per_category:
                warnings.append(f"{category} 카테고리에 키워드가 부족합니다 ({count}개).")
                recommendations.append(
                    f"{category} 카테고리의 임계값을 낮추거나 고정 키워드를 추가하세요."
                )

        # 5. 전체 품질 점수 계산
        overall_score = self._calculate_overall_score(
            balance_score, narrative_quality, learning_effectiveness
        )

        return QualityMetrics(
            total_keywords=total_keywords,
            categorized_keywords=keyword_counts,
            category_balance_score=balance_score,
            narratives_generated=narratives_generated,
            narrative_lengths=narrative_lengths,
            narrative_quality_score=narrative_quality,
            dynamic_keywords_learned=dynamic_learned,
            dynamic_keywords_used=dynamic_used,
            learning_effectiveness=learning_effectiveness,
            overall_quality_score=overall_score,
            warnings=warnings,
            recommendations=recommendations
        )

    def _calculate_balance_score(self, keyword_counts: Dict[str, int]) -> float:
        """
        카테고리 균형도를 계산합니다.

        완벽하게 균등하면 1.0, 한쪽으로 치우치면 0.0에 가까워집니다.
        """
        total = sum(keyword_counts.values())
        if total == 0:
            return 0.0

        # 각 카테고리의 비율
        ratios = [count / total for count in keyword_counts.values() if count > 0]

        if not ratios:
            return 0.0

        # 표준편차 기반 균형도 (낮을수록 균형적)
        import statistics
        if len(ratios) == 1:
            return 0.0  # 하나의 카테고리만 있으면 불균형

        mean_ratio = statistics.mean(ratios)
        std_dev = statistics.stdev(ratios)

        # 정규화: std_dev가 0이면 완벽한 균형 (1.0)
        # std_dev가 크면 불균형 (0.0에 가까움)
        balance = max(0.0, 1.0 - (std_dev * 3))  # 3배수로 스케일링

        return balance

    def _calculate_narrative_quality(
        self,
        generated: Dict[str, bool],
        lengths: Dict[str, int]
    ) -> float:
        """
        내러티브 품질 점수를 계산합니다.

        - 모든 카테고리 생성 시 가산점
        - 적절한 길이 유지 시 가산점
        """
        score = 0.0

        # 핵심 2개 카테고리 생성 확인 (macro, crypto)
        core_categories = ["macro", "crypto"]
        generated_count = sum(1 for cat in core_categories if generated.get(cat, False))

        # 생성률 점수 (0.5 가중치)
        generation_score = (generated_count / len(core_categories)) * 0.5
        score += generation_score

        # 길이 적절성 점수 (0.5 가중치)
        length_scores = []
        for cat in core_categories:
            if generated.get(cat, False):
                length = lengths.get(cat, 0)
                # 최소 길이 이상이면 1.0, 미만이면 비율
                length_score = min(1.0, length / self.min_narrative_length)
                length_scores.append(length_score)

        if length_scores:
            avg_length_score = sum(length_scores) / len(length_scores)
            score += avg_length_score * 0.5

        return score

    def _count_dynamic_keywords_used(
        self,
        categorized_keywords: Dict[str, List[Dict]],
        dynamic_cache: Dict
    ) -> int:
        """
        동적 학습된 키워드 중 실제로 사용된 개수를 셉니다.
        """
        used_count = 0
        dynamic_terms = set(dynamic_cache.keys())

        for category_keywords in categorized_keywords.values():
            for kw_dict in category_keywords:
                term = kw_dict.get("term", "").lower()
                if term in dynamic_terms:
                    used_count += 1
                    break  # 중복 카운트 방지

        return used_count

    def _calculate_overall_score(
        self,
        balance: float,
        narrative_quality: float,
        learning_effectiveness: float
    ) -> float:
        """
        전체 품질 점수를 계산합니다.

        가중치:
        - 카테고리 균형: 30%
        - 내러티브 품질: 50%
        - 학습 효과: 20%
        """
        return (
            balance * 0.3 +
            narrative_quality * 0.5 +
            learning_effectiveness * 0.2
        )

    def print_report(self, metrics: QualityMetrics) -> str:
        """
        품질 평가 리포트를 문자열로 생성합니다.
        """
        lines = []
        lines.append("=" * 60)
        lines.append("품질 평가 리포트 (Phase 3)")
        lines.append("=" * 60)
        lines.append("")

        # 전체 점수
        lines.append(f"📊 전체 품질 점수: {metrics.overall_quality_score:.2%}")
        lines.append("")

        # 키워드 분류
        lines.append("🔑 키워드 분류 품질")
        lines.append(f"  - 총 키워드: {metrics.total_keywords}개")
        for category, count in metrics.categorized_keywords.items():
            lines.append(f"    - {category}: {count}개")
        lines.append(f"  - 균형도 점수: {metrics.category_balance_score:.2%}")
        lines.append("")

        # 내러티브 품질
        lines.append("📝 내러티브 품질")
        for category, generated in metrics.narratives_generated.items():
            status = "✅ 생성됨" if generated else "❌ 미생성"
            length = metrics.narrative_lengths.get(category, 0)
            lines.append(f"  - {category}: {status} ({length}자)")
        lines.append(f"  - 내러티브 품질 점수: {metrics.narrative_quality_score:.2%}")
        lines.append("")

        # 동적 학습
        if metrics.dynamic_keywords_learned > 0:
            lines.append("🤖 동적 학습 효과")
            lines.append(f"  - 학습된 키워드: {metrics.dynamic_keywords_learned}개")
            lines.append(f"  - 사용된 키워드: {metrics.dynamic_keywords_used}개")
            lines.append(f"  - 효과성 점수: {metrics.learning_effectiveness:.2%}")
            lines.append("")

        # 경고
        if metrics.warnings:
            lines.append("⚠️  경고")
            for warning in metrics.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        # 권장사항
        if metrics.recommendations:
            lines.append("💡 권장사항")
            for rec in metrics.recommendations:
                lines.append(f"  - {rec}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

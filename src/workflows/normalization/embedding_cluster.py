"""
키워드 임베딩 생성 유틸리티.

Gemini Embedding API 또는 KeyBERT 기반 SentenceTransformer를 활용해
키워드 텍스트를 벡터 공간으로 투영합니다. AggregatorNode의 1차 정규화
단계(4.4.1)에 해당하며, 후속 DBSCAN 클러스터링을 위해 일관된 차원의
벡터 배열을 반환합니다.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, MutableMapping, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# LangChain 기반 임베딩 래퍼 가용 여부 확인
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    GOOGLE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    GOOGLE_EMBEDDINGS_AVAILABLE = False
    logger.warning(
        "[EmbeddingCluster] langchain-google-genai 패키지가 설치되어 있지 않아 Gemini 임베딩을 사용할 수 없습니다."
    )

# KeyBERT 대체 경로 확인
try:
    from keybert import KeyBERT  # type: ignore[import]

    KEYBERT_AVAILABLE = True
except ImportError:
    KEYBERT_AVAILABLE = False
    logger.info(
        "[EmbeddingCluster] KeyBERT 패키지가 설치되어 있지 않아 로컬 임베딩 대체 경로를 비활성화합니다."
    )

try:
    from langchain_openai import OpenAIEmbeddings  # type: ignore[import]

    OPENAI_EMBEDDINGS_AVAILABLE = True
except ImportError:
    OPENAI_EMBEDDINGS_AVAILABLE = False
    logger.info(
        "[EmbeddingCluster] langchain-openai 패키지가 설치되어 있지 않아 OpenAI 임베딩을 사용할 수 없습니다."
    )

DEFAULT_GEMINI_EMBEDDING_MODEL = "models/text-embedding-004"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_GEMINI_TASK_TYPE = "retrieval_document"


async def generate_keyword_embeddings(
    texts: Sequence[str],
    *,
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    concurrency_limit: int = 4,
    normalize: bool = True,
) -> np.ndarray:
    """
    키워드 텍스트 시퀀스에 대한 임베딩을 비동기적으로 생성합니다.

    Args:
        texts: 임베딩을 생성할 키워드 문자열 시퀀스.
        provider: 사용할 임베딩 공급자. "gemini", "openai", "keybert" 중 하나.
        api_key: 임베딩 API 호출에 사용할 API 키. None이면 환경변수에서 로드합니다.
        model: 임베딩 모델 식별자. 공급자별 기본값이 자동으로 선택됩니다.
        task_type: Gemini 임베딩 API의 task_type 매개변수 (Gemini 전용).
        concurrency_limit: 동시에 실행할 임베딩 요청 수 제한.
        normalize: True일 경우 L2 정규화를 적용합니다.

    Returns:
        입력 텍스트 순서를 유지하는 NumPy 2차원 배열 (샘플 수 x 임베딩 차원).

    Raises:
        ValueError: 입력 검증 실패 또는 지원되지 않는 공급자 지정 시.
        RuntimeError: 지정한 공급자가 사용 불가능할 때.
    """
    if not texts:
        raise ValueError("임베딩을 생성할 텍스트가 비어 있습니다.")

    if any(text is None for text in texts):
        raise ValueError("None 값을 포함한 텍스트는 임베딩을 생성할 수 없습니다.")

    logger.info(
        "[EmbeddingCluster] 임베딩 생성 시작: provider=%s, model=%s, text_count=%d",
        provider,
        model or "(auto)",
        len(texts),
    )

    await _log_full_texts(texts)

    provider_lower = provider.lower()

    if provider_lower == "gemini":
        embeddings = await _generate_with_gemini(
            texts=texts,
            api_key=api_key,
            model=model or DEFAULT_GEMINI_EMBEDDING_MODEL,
            task_type=(task_type or DEFAULT_GEMINI_TASK_TYPE),
            concurrency_limit=concurrency_limit,
        )
    elif provider_lower == "openai":
        embeddings = await _generate_with_openai(
            texts=texts,
            api_key=api_key,
            model=model or DEFAULT_OPENAI_EMBEDDING_MODEL,
        )
    elif provider_lower == "keybert":
        embeddings = await _generate_with_keybert(
            texts=texts,
            normalize=normalize,
        )
    else:
        raise ValueError(f"지원되지 않는 임베딩 공급자입니다: {provider}")

    if normalize:
        embeddings = _l2_normalize(embeddings)

    logger.info(
        "[EmbeddingCluster] 임베딩 생성 완료: provider=%s, embedding_shape=%s",
        provider,
        embeddings.shape,
    )

    return embeddings


async def _generate_with_gemini(
    *,
    texts: Sequence[str],
    api_key: Optional[str],
    model: str,
    task_type: str,
    concurrency_limit: int,
) -> np.ndarray:
    """
    LangChain GoogleGenerativeAIEmbeddings를 사용하여 임베딩을 생성합니다.

    Args:
        texts: 임베딩을 생성할 텍스트 목록.
        api_key: 명시적 API 키. None이면 환경 변수를 활용합니다.
        model: 사용할 Gemini 임베딩 모델명.
        task_type: Gemini 임베딩 task_type.
        concurrency_limit: 동시에 허용할 API 호출 수.

    Returns:
        NumPy 배열 형태의 임베딩 결과.
    """
    if not GOOGLE_EMBEDDINGS_AVAILABLE:
        raise RuntimeError(
            "langchain-google-genai 패키지가 설치되어 있지 않아 Gemini 임베딩을 사용할 수 없습니다."
        )

    resolved_api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    logger.debug(
        "[EmbeddingCluster] Gemini 임베딩 호출: model=%s, task_type=%s, concurrency_limit=%d, text_count=%d",
        model,
        task_type,
        concurrency_limit,
        len(texts),
    )

    embedder = GoogleGenerativeAIEmbeddings(
        model=model,
        task_type=task_type,
        google_api_key=resolved_api_key,
    )

    def _embed() -> List[List[float]]:
        return embedder.embed_documents(list(texts))

    vectors = await asyncio.to_thread(_embed)

    return np.asarray(vectors, dtype=np.float32)


async def _generate_with_openai(
    *,
    texts: Sequence[str],
    api_key: Optional[str],
    model: str,
) -> np.ndarray:
    """
    LangChain OpenAIEmbeddings를 사용하여 임베딩을 생성합니다.

    Args:
        texts: 임베딩을 생성할 텍스트 목록.
        api_key: 명시적 OpenAI API 키. None이면 환경 변수를 활용합니다.
        model: 사용할 OpenAI 임베딩 모델명.

    Returns:
        NumPy 배열 형태의 임베딩 결과.
    """
    if not OPENAI_EMBEDDINGS_AVAILABLE:
        raise RuntimeError(
            "langchain-openai 패키지가 설치되어 있지 않아 OpenAI 임베딩을 사용할 수 없습니다."
        )

    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    logger.debug(
        "[EmbeddingCluster] OpenAI 임베딩 호출: model=%s, text_count=%d",
        model,
        len(texts),
    )

    embedder = OpenAIEmbeddings(
        model=model,
        openai_api_key=resolved_api_key,
    )

    def _embed() -> List[List[float]]:
        return embedder.embed_documents(list(texts))

    vectors = await asyncio.to_thread(_embed)

    return np.asarray(vectors, dtype=np.float32)


async def _generate_with_keybert(
    *,
    texts: Sequence[str],
    normalize: bool,
) -> np.ndarray:
    """
    KeyBERT의 SentenceTransformer 모델을 활용해 임베딩을 생성합니다.

    Args:
        texts: 임베딩을 생성할 텍스트 목록.
        normalize: SentenceTransformer 결과에 대해 L2 정규화를 적용할지 여부.

    Returns:
        NumPy 배열 형태의 임베딩 결과.
    """
    if not KEYBERT_AVAILABLE:
        raise RuntimeError("KeyBERT 패키지가 설치되어 있지 않습니다. provider='gemini'를 사용하세요.")

    logger.info("[EmbeddingCluster] KeyBERT 임베딩 생성 시작 (text_count=%d)", len(texts))

    kw_model = KeyBERT()

    def _encode_batch() -> np.ndarray:
        embeddings = kw_model.model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=normalize,
        )
        return embeddings.astype(np.float32, copy=False)

    vectors = await asyncio.to_thread(_encode_batch)

    logger.info("[EmbeddingCluster] KeyBERT 임베딩 생성 완료 (shape=%s)", vectors.shape)

    return vectors


async def cluster_keywords_by_embedding(
    keywords: Sequence[MutableMapping[str, object]],
    *,
    similarity_threshold: float = 0.85,
    min_cluster_size: int = 1,
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    concurrency_limit: int = 4,
    normalize_embeddings: bool = True,
) -> List[MutableMapping[str, object]]:
    """
    DBSCAN을 사용해 키워드를 임베딩 기반으로 클러스터링합니다.

    Args:
        keywords: 키워드 정보를 담은 매핑 시퀀스. 각 항목은 최소한 `term` 키를 포함해야 합니다.
        similarity_threshold: 코사인 유사도 임계값. eps는 1 - similarity_threshold로 계산됩니다.
        min_cluster_size: DBSCAN의 min_samples 값. 1이면 모든 키워드가 최소 한 개의 클러스터에 포함됩니다.
        provider: 임베딩 생성 공급자. 기본값은 Gemini.
        api_key: Gemini 임베딩 호출 시 사용할 API 키.
        model: Gemini 임베딩 모델 명.
        task_type: Gemini 임베딩 task_type.
        concurrency_limit: 임베딩 생성 동시 실행 제한.
        normalize_embeddings: True일 경우 임베딩 벡터에 L2 정규화를 적용합니다.

    Returns:
        클러스터 정보를 포함하는 키워드 매핑 리스트. 각 항목에는 `cluster_id`와 `cluster_members` 필드가 추가됩니다.

    Raises:
        ValueError: 입력 유효성 검증 실패 시.
    """
    if not keywords:
        raise ValueError("클러스터링할 키워드가 비어 있습니다.")

    missing_term = [kw for kw in keywords if "term" not in kw or not str(kw["term"]).strip()]
    if missing_term:
        raise ValueError("모든 키워드는 'term' 필드를 포함해야 합니다.")

    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold는 0.0과 1.0 사이여야 합니다.")

    if min_cluster_size < 1:
        raise ValueError("min_cluster_size는 1 이상이어야 합니다.")

    keyword_terms = [str(kw["term"]) for kw in keywords]
    logger.info(
        "[EmbeddingCluster] DBSCAN 클러스터링 시작: keyword_count=%d, similarity_threshold=%.3f, provider=%s",
        len(keyword_terms),
        similarity_threshold,
        provider,
    )

    await _log_full_texts(keyword_terms)

    embeddings = await generate_keyword_embeddings(
        keyword_terms,
        provider=provider,
        api_key=api_key,
        model=model,
        task_type=task_type,
        concurrency_limit=concurrency_limit,
        normalize=normalize_embeddings,
    )

    from sklearn.cluster import DBSCAN

    eps = max(0.0, 1.0 - similarity_threshold)

    logger.debug(
        "[EmbeddingCluster] DBSCAN 매개변수: eps=%.4f, min_samples=%d, metric=cosine",
        eps,
        min_cluster_size,
    )

    clustering = DBSCAN(
        eps=eps,
        min_samples=min_cluster_size,
        metric="cosine",
        n_jobs=-1,
    )
    cluster_labels = clustering.fit_predict(embeddings)

    logger.info(
        "[EmbeddingCluster] DBSCAN 결과: cluster_labels=%s",
        cluster_labels.tolist(),
    )

    label_to_members: dict[int, List[str]] = {}
    for index, label in enumerate(cluster_labels):
        label_to_members.setdefault(int(label), []).append(keyword_terms[index])

    logger.debug("[EmbeddingCluster] 클러스터 구성: %s", label_to_members)

    enriched_keywords: List[MutableMapping[str, object]] = []
    for index, keyword in enumerate(keywords):
        label = int(cluster_labels[index])
        members = label_to_members[label]

        keyword_copy = dict(keyword)
        keyword_copy["cluster_id"] = label
        keyword_copy["cluster_members"] = members

        enriched_keywords.append(keyword_copy)

    logger.info("[EmbeddingCluster] 클러스터링 완료: cluster_count=%d", len(label_to_members))

    return enriched_keywords


def aggregate_clustered_keywords(
    clustered_keywords: Sequence[MutableMapping[str, object]],
    *,
    evidence_limit: int = 3,
    source_weight: float = 0.1,
    occurrence_weight: float = 0.05,
    evidence_weight: float = 0.02,
) -> List[Dict[str, object]]:
    """
    클러스터링된 키워드 목록을 그룹별로 통합하고 메타데이터를 계산합니다.

    Args:
        clustered_keywords: `cluster_keywords_by_embedding` 결과.
        evidence_limit: 클러스터 통합 시 유지할 증거 문장 최대 개수.

    Returns:
        통합된 키워드 메타데이터 리스트. 각 항목은 `term`, `original_variants`,
        `score`, `evidence`, `sources`, `occurrence_count` 필드를 포함합니다.

    Raises:
        ValueError: 입력 데이터에 `cluster_id` 정보가 없을 때.
    """
    if not clustered_keywords:
        raise ValueError("통합할 클러스터링 키워드가 비어 있습니다.")

    missing_cluster = [kw for kw in clustered_keywords if "cluster_id" not in kw]
    if missing_cluster:
        raise ValueError("모든 키워드에는 'cluster_id' 필드가 포함되어야 합니다.")

    logger.info(
        "[EmbeddingCluster] 클러스터 그룹핑 시작: keyword_count=%d",
        len(clustered_keywords),
    )

    cluster_groups: Dict[int, List[MutableMapping[str, object]]] = {}

    for keyword in clustered_keywords:
        cluster_id = int(keyword["cluster_id"])
        cluster_groups.setdefault(cluster_id, []).append(keyword)

    logger.debug("[EmbeddingCluster] 클러스터 그룹핑 결과: %s", cluster_groups.keys())

    aggregated_keywords: List[Dict[str, object]] = []

    for cluster_id, keywords_in_cluster in cluster_groups.items():
        if len(keywords_in_cluster) == 1:
            keyword = keywords_in_cluster[0]
            base_score = float(keyword.get("score", 0.0))
            # evidence_ids 처리 (evidence 필드는 무시)
            evidence_ids = keyword.get("evidence_ids", [])
            if not evidence_ids and "evidence" in keyword:
                logger.warning(
                    f"[aggregate_clustered_keywords] 키워드 '{keyword.get('term')}'에 'evidence' 필드가 있지만 "
                    f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
                )
            evidence_ids = evidence_ids[:evidence_limit] if isinstance(evidence_ids, list) else []
            
            sources_values = list(keyword.get("sources", []))

            aggregated_keywords.append(
                {
                    "term": str(keyword["term"]),
                    "original_variants": [str(keyword["term"])],
                    "score": base_score,
                    "evidence_ids": evidence_ids,
                    "sources": sources_values,
                    "occurrence_count": 1,
                    "cluster_id": cluster_id,
                    "score_components": {
                        "raw_scores": [base_score],
                        "source_count": len(set(sources_values)),
                        "occurrence_count": 1,
                        "evidence_count": len(evidence_ids),
                    },
                }
            )

            continue

        all_terms = [str(item["term"]) for item in keywords_in_cluster]
        all_scores = [float(item.get("score", 0.0)) for item in keywords_in_cluster]

        all_evidence_ids: List[int] = []
        all_sources: List[str] = []

        for item in keywords_in_cluster:
            # evidence_ids 처리 (evidence 필드는 무시)
            evidence_ids = item.get("evidence_ids", [])
            if not evidence_ids and "evidence" in item:
                logger.warning(
                    f"[aggregate_clustered_keywords] 클러스터 {cluster_id}의 키워드에 'evidence' 필드가 있지만 "
                    f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
                )
            
            if isinstance(evidence_ids, list):
                for evidence_id in evidence_ids:
                    if isinstance(evidence_id, int) and evidence_id not in all_evidence_ids:
                        all_evidence_ids.append(evidence_id)
            
            all_sources.extend(list(item.get("sources", [])))

        unique_sources = sorted(set(all_sources))

        representative_index = int(np.argmax(all_scores))
        representative_term = all_terms[representative_index]

        base_score = float(np.mean(all_scores)) if all_scores else 0.0

        evidence_ids_subset = all_evidence_ids[:evidence_limit]
        aggregated_keywords.append(
            {
                "term": representative_term,
                "original_variants": all_terms,
                "score": base_score,
                "evidence_ids": evidence_ids_subset,
                "sources": unique_sources,
                "occurrence_count": len(keywords_in_cluster),
                "cluster_id": cluster_id,
                "score_components": {
                    "raw_scores": all_scores,
                    "source_count": len(unique_sources),
                    "occurrence_count": len(keywords_in_cluster),
                    "evidence_count": len(evidence_ids_subset),
                },
            }
        )

        logger.debug(
            "[EmbeddingCluster] 클러스터 %d 통합: representative=%s, members=%s, final_score=%.4f",
            cluster_id,
            representative_term,
            all_terms,
            base_score,
        )

    recalculated_keywords = recalculate_cluster_scores(
        aggregated_keywords,
        source_weight=source_weight,
        occurrence_weight=occurrence_weight,
        evidence_weight=evidence_weight,
        max_evidence_bonus=evidence_limit,
    )

    logger.info(
        "[EmbeddingCluster] 클러스터 그룹핑 완료: aggregated_count=%d",
        len(recalculated_keywords),
    )

    return recalculated_keywords


def recalculate_cluster_scores(
    aggregated_keywords: Sequence[MutableMapping[str, object]],
    *,
    source_weight: float = 0.1,
    occurrence_weight: float = 0.05,
    evidence_weight: float = 0.02,
    max_evidence_bonus: int = 3,
) -> List[Dict[str, object]]:
    """
    클러스터 통합 결과에 가중치를 적용하여 최종 점수를 재계산합니다.

    Args:
        aggregated_keywords: `aggregate_clustered_keywords`에서 생성된 리스트.
        source_weight: 고유 출처 수에 곱할 가중치 계수.
        occurrence_weight: 동일 클러스터 내 키워드 개수에 곱할 가중치 계수.
        evidence_weight: 증거 문장 수에 곱할 가중치 계수.
        max_evidence_bonus: 증거 문장 가중치 적용 시 고려할 최대 개수.

    Returns:
        최종 점수와 점수 분해 정보를 포함한 리스트.
    """
    if not aggregated_keywords:
        raise ValueError("점수를 재계산할 키워드가 비어 있습니다.")

    logger.info(
        "[EmbeddingCluster] 스코어 재계산 시작: keyword_count=%d",
        len(aggregated_keywords),
    )

    recalculated: List[Dict[str, object]] = []

    for keyword in aggregated_keywords:
        score_components = keyword.get("score_components", {}) if isinstance(keyword, MutableMapping) else {}
        raw_scores = score_components.get("raw_scores") or [keyword.get("score", 0.0)]
        raw_scores = [float(value) for value in raw_scores if value is not None]

        if not raw_scores:
            base_mean = 0.0
        else:
            base_mean = float(np.mean(raw_scores))

        source_count = int(score_components.get("source_count", len(set(keyword.get("sources", [])))))
        occurrence_count = int(score_components.get("occurrence_count", keyword.get("occurrence_count", 1)))
        # evidence_ids 개수 계산
        evidence_ids = keyword.get("evidence_ids", [])
        if not evidence_ids and "evidence" in keyword:
            logger.warning(
                f"[_recalculate_scores] 키워드 '{keyword.get('term')}'에 'evidence' 필드가 있지만 "
                f"'evidence_ids'가 없습니다. 'evidence' 필드는 무시됩니다."
            )
        evidence_count = int(score_components.get("evidence_count", len(evidence_ids) if isinstance(evidence_ids, list) else 0))
        evidence_count = min(evidence_count, max_evidence_bonus)

        source_factor = 1.0 + (source_count * source_weight)
        occurrence_factor = 1.0 + (max(occurrence_count - 1, 0) * occurrence_weight)
        evidence_factor = 1.0 + (evidence_count * evidence_weight)

        final_score = base_mean * source_factor * occurrence_factor * evidence_factor

        score_breakdown = {
            "base_mean": base_mean,
            "raw_scores": raw_scores,
            "source_count": source_count,
            "occurrence_count": occurrence_count,
            "evidence_count": evidence_count,
            "source_factor": source_factor,
            "occurrence_factor": occurrence_factor,
            "evidence_factor": evidence_factor,
        }

        updated_keyword: Dict[str, object] = dict(keyword)
        updated_keyword["score"] = final_score
        updated_keyword["score_breakdown"] = score_breakdown

        recalculated.append(updated_keyword)

        logger.debug(
            "[EmbeddingCluster] 스코어 재계산: term=%s, base_mean=%.4f, final_score=%.4f, breakdown=%s",
            updated_keyword.get("term"),
            base_mean,
            final_score,
            score_breakdown,
        )

    recalculated.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)

    logger.info("[EmbeddingCluster] 스코어 재계산 완료")

    return recalculated


async def _log_full_texts(texts: Sequence[str]) -> None:
    """
    처리 중인 텍스트를 모두 로그로 출력합니다.
    """
    for index, text in enumerate(texts):
        logger.debug("[EmbeddingCluster] 텍스트 확인 index=%d, text=%s", index, text)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """
    L2 정규화를 적용하여 임베딩을 정규화합니다.

    Args:
        vectors: 정규화할 임베딩 배열.

    Returns:
        L2 정규화된 임베딩 배열.
    """
    if vectors.size == 0:
        return vectors

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0

    return vectors / norms



import os
from typing import Dict, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


def compute_similarity_and_clusters(items: List[Dict], n_clusters: int = 3):
    texts = [it["summary"] for it in items]
    ids = [it["paper_id"] for it in items]
    if len(texts) == 0:
        return ids, np.zeros((0, 0)), {}
    if len(texts) == 1:
        return ids, np.array([[1.0]]), {0: [ids[0]]}

    vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X = vec.fit_transform(texts)
    sim = cosine_similarity(X)

    n_clusters = min(n_clusters, len(items))
    clustering = AgglomerativeClustering(n_clusters=n_clusters, metric="cosine", linkage="average")
    labels = clustering.fit_predict(X.toarray())

    clusters: Dict[int, List[str]] = {}
    for pid, lab in zip(ids, labels):
        clusters.setdefault(int(lab), []).append(pid)
    return ids, sim, clusters


def render_similarity_table(ids: List[str], sim) -> str:
    # top pairs
    pairs = []
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((ids[i], ids[j], float(sim[i, j])))
    pairs.sort(key=lambda x: x[2], reverse=True)
    pairs = pairs[: min(10, len(pairs))]
    lines = ["| Paper A | Paper B | Similarity |", "|---|---|---:|"]
    for a, b, s in pairs:
        lines.append(f"| {a} | {b} | {s:.3f} |")
    return "\n".join(lines)


def _select_representative(fig_paths: List[str], max_count: int = 4) -> List[str]:
    """Pick up to `max_count` representative images, spaced across the list.

    - If no images, return empty.
    - If <= max_count, return as-is.
    - Else, pick indices spread roughly evenly from start to end.
    """
    n = len(fig_paths)
    if n == 0:
        return []
    if n <= max_count:
        return fig_paths
    k = max_count
    # Evenly spaced indices including first and last
    indices = []
    for i in range(k):
        # round to nearest index across [0, n-1]
        idx = round(i * (n - 1) / (k - 1)) if k > 1 else n // 2
        if not indices or idx != indices[-1]:
            indices.append(idx)
    # In rare rounding collisions, backfill missing spots
    while len(indices) < k:
        # add any missing index in range, prefer middle
        cand = n // 2
        if cand not in indices:
            indices.append(cand)
        else:
            # linear probe
            for off in range(1, n):
                a = cand - off
                b = cand + off
                if 0 <= a < n and a not in indices:
                    indices.append(a)
                    break
                if 0 <= b < n and b not in indices:
                    indices.append(b)
                    break
            if len(indices) >= k:
                break
    # dedupe and clamp
    uniq = []
    for idx in indices:
        if 0 <= idx < n and idx not in uniq:
            uniq.append(idx)
    return [fig_paths[i] for i in uniq[:k]]


def generate_report(
    report_dir: str,
    corpus_summary: str,
    items: List[Dict],
) -> str:
    os.makedirs(report_dir, exist_ok=True)
    ids, sim, clusters = compute_similarity_and_clusters(items)

    lines: List[str] = []
    lines.append("# 종합 보고서")
    lines.append("")
    lines.append("## (1) 전체 종합 요약")
    lines.append("")
    lines.append(corpus_summary.strip())
    lines.append("")

    lines.append("## (2) 논문 간 유사성/차별성")
    lines.append("")
    lines.append("### 유사도 상위 페어")
    if len(ids) >= 2:
        lines.append(render_similarity_table(ids, sim))
    else:
        lines.append("단일 문서: 유사도 표 생략")
    lines.append("")
    lines.append("### 클러스터 결과")
    for cid, members in clusters.items():
        lines.append(f"- Cluster {cid}: {', '.join(members)}")
    lines.append("")

    lines.append("## (3) 논문별 개별 요약")
    lines.append("")
    for it in items:
        meta = it["metadata"]
        title = meta.get("title") or it["paper_id"]
        lines.append(f"### {title} ({it['paper_id']})")
        lines.append("")
        lines.append(f"- 원본: `{meta.get('source_pdf')}`")
        lines.append(f"- 페이지 수: {meta.get('page_count')}")
        if meta.get("author"):
            lines.append(f"- 저자: {meta.get('author')}")
        if meta.get("creationDate"):
            lines.append(f"- 발행일: {meta.get('creationDate')}")
        lines.append("")
        # Embed extracted figures as images (relative to report_dir)
        fig_paths = it.get("figures_paths") or []
        reps = _select_representative(fig_paths, max_count=4)
        if reps:
            lines.append("대표 이미지 (최대 4장):")
            lines.append("")
            for p in reps:
                rel = os.path.relpath(p, start=report_dir)
                alt = os.path.basename(p)
                # Use HTML img for size control in most renderers
                lines.append(f"<img src=\"{rel}\" alt=\"{alt}\" width=\"240\" />")
            lines.append("")
        else:
            lines.append("추출 이미지: 없음")
        lines.append("")
        lines.append("요약:")
        lines.append("")
        lines.append(it["summary"].strip())
        lines.append("")

    out_path = os.path.join(report_dir, "summary.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path

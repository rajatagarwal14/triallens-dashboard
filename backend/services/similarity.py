from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
import numpy as np


def _build_text(study: dict) -> str:
    parts = [
        " ".join(study.get("conditions", [])),
        " ".join(study.get("keywords", [])),
        study.get("eligibility", {}).get("criteria", ""),
        " ".join(i["name"] for i in study.get("interventions", [])),
        study.get("summary", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def compute_similarities(target: dict, candidates: List[dict]) -> List[dict]:
    if not candidates:
        return []

    target_text = _build_text(target)
    candidate_texts = [_build_text(c) for c in candidates]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=8000,
        sublinear_tf=True,
    )
    all_texts = [target_text] + candidate_texts
    try:
        tfidf = vectorizer.fit_transform(all_texts)
    except ValueError:
        return []

    scores = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    results = []
    for study, score in zip(candidates, scores):
        if study["nctId"] == target["nctId"]:
            continue
        shared_conditions = list(
            set(c.lower() for c in study.get("conditions", []))
            & set(c.lower() for c in target.get("conditions", []))
        )
        shared_keywords = list(
            set(k.lower() for k in study.get("keywords", []))
            & set(k.lower() for k in target.get("keywords", []))
        )
        results.append({
            "study": study,
            "score": round(float(score), 4),
            "sharedConditions": shared_conditions[:4],
            "sharedKeywords": shared_keywords[:5],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:20]

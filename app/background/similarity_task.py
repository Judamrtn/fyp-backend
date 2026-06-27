"""
Upgraded TF-IDF similarity engine — multi-field weighted scoring.

Weights:
  Title       30%
  Abstract    30%
  Objectives  25%
  Keywords    15%

Each field is vectorized separately then combined as a weighted score.
This gives much better accuracy than title-only matching.
"""
import logging
from typing import List, Tuple
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.database import SessionLocal
from app.models.proposal import Proposal, ProposalObjective
from app.models.allocation import ProjectRegistration
from app.models.similarity import SimilarityCheck, SimilarityConfig
from app.config import settings

logger = logging.getLogger(__name__)

# Field weights — must sum to 1.0
WEIGHTS = {
    "title":      0.30,
    "abstract":   0.30,
    "objectives": 0.25,
    "keywords":   0.15,
}


def _get_threshold(db, department_id) -> int:
    config = db.query(SimilarityConfig).filter(
        SimilarityConfig.department_id == department_id
    ).first()
    return config.threshold if config else settings.default_similarity_threshold


def _build_corpus(db) -> List[dict]:
    registrations = db.query(ProjectRegistration).filter(
        ProjectRegistration.deleted_at.is_(None),
        ProjectRegistration.is_public == True,
    ).all()

    corpus = []
    for r in registrations:
        objectives_text = ""
        keywords_text   = ""

        if r.proposal_id is not None:
            objs = db.query(ProposalObjective).filter(
                ProposalObjective.proposal_id == r.proposal_id,
                ProposalObjective.deleted_at.is_(None),
            ).all()
            objectives_text = " ".join(o.objective_text for o in objs)

            proposal = db.query(Proposal).filter(
                Proposal.id == r.proposal_id
            ).first()
            if proposal and proposal.keywords:
                keywords_text = proposal.keywords

        corpus.append({
            "proposal_id": str(r.proposal_id) if r.proposal_id else str(r.id),
            "title":       r.title or "",
            "abstract":    r.abstract or "",
            "objectives":  objectives_text,
            "keywords":    keywords_text,
        })

    return corpus
    """
    Returns list of dicts with fields: proposal_id, title, abstract, objectives, keywords
    from all approved project registrations.
    """
    registrations = db.query(ProjectRegistration).filter(
        ProjectRegistration.deleted_at.is_(None),
        ProjectRegistration.is_public == True,
    ).all()

    corpus = []
    for r in registrations:
        # Get objectives for this project via its proposal
        objectives_text = ""
        if r.proposal_id:
            objs = db.query(ProposalObjective).filter(
                ProposalObjective.proposal_id == r.proposal_id,
                ProposalObjective.deleted_at.is_(None),
            ).all()
            objectives_text = " ".join(o.objective_text for o in objs)

        corpus.append({
            "proposal_id": str(r.proposal_id),
            "title":       r.title or "",
            "abstract":    r.abstract or "",
            "objectives":  objectives_text,
            "keywords":    "",   # keywords not stored in ProjectRegistration — pulled from Proposal below
        })

    # Enrich with keywords from proposals
    for item in corpus:
        proposal = db.query(Proposal).filter(
            Proposal.id == item["proposal_id"]
        ).first()
        if proposal and proposal.keywords:
            item["keywords"] = proposal.keywords

    return corpus


def _field_similarity(query_text: str, corpus_texts: List[str]) -> np.ndarray:
    """
    Compute cosine similarity between query and all corpus items for one field.
    Returns array of shape (len(corpus_texts),).
    Returns zeros if query or all corpus texts are empty.
    """
    if not query_text.strip() or not any(t.strip() for t in corpus_texts):
        return np.zeros(len(corpus_texts))

    all_texts = corpus_texts + [query_text]
    try:
        vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
        )
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        query_vec    = tfidf_matrix[-1]
        corpus_mat   = tfidf_matrix[:-1]
        scores = cosine_similarity(query_vec, corpus_mat).flatten()
        return scores
    except Exception:
        return np.zeros(len(corpus_texts))


def compute_similarity(
    query: dict,
    corpus: List[dict],
    top_n: int = 5,
) -> Tuple[float, List[dict]]:
    """
    Returns (max_weighted_score_pct, top_n_matches).
    query and each corpus item must have keys: title, abstract, objectives, keywords.
    """
    if not corpus:
        return 0.0, []

    # Compute per-field similarity arrays
    field_scores = {}
    for field in WEIGHTS:
        query_text   = query.get(field, "") or ""
        corpus_texts = [item.get(field, "") or "" for item in corpus]
        field_scores[field] = _field_similarity(query_text, corpus_texts)

    # Weighted combination
    combined = np.zeros(len(corpus))
    for field, weight in WEIGHTS.items():
        combined += weight * field_scores[field]

    combined_pct = combined * 100   # convert to percentage

    # Top-N
    top_indices = np.argsort(combined_pct)[::-1][:top_n]
    top_matches = [
        {
            "proposal_id": corpus[i]["proposal_id"],
            "title":       corpus[i]["title"],
            "score":       round(float(combined_pct[i]), 2),
            "breakdown": {
                "title":      round(float(field_scores["title"][i] * 100), 2),
                "abstract":   round(float(field_scores["abstract"][i] * 100), 2),
                "objectives": round(float(field_scores["objectives"][i] * 100), 2),
                "keywords":   round(float(field_scores["keywords"][i] * 100), 2),
            }
        }
        for i in top_indices
        if combined_pct[i] > 0
    ]

    max_score = float(np.max(combined_pct)) if len(combined_pct) > 0 else 0.0
    return round(max_score, 2), top_matches


def run_similarity_check(proposal_id: str) -> None:
    db = SessionLocal()
    try:
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            logger.warning("Similarity check: proposal %s not found.", proposal_id)
            return

        # Build query dict
        objectives_text = " ".join(
            o.objective_text for o in proposal.objectives
        )
        query = {
            "title":      proposal.title or "",
            "abstract":   proposal.abstract or "",
            "objectives": objectives_text,
            "keywords":   proposal.keywords or "",
        }

        corpus    = _build_corpus(db)
        threshold = _get_threshold(db, proposal.department_id)

        score, top_matches = compute_similarity(query, corpus)
        flagged = score >= threshold

        check = SimilarityCheck(
            proposal_id    = proposal.id,
            score          = score,
            top_matches    = top_matches,
            threshold_used = threshold,
            overridden     = False,
        )
        db.add(check)

        proposal.similarity_score = score
        proposal.similarity_flag  = flagged

        db.commit()
        logger.info(
            "Similarity check done: proposal=%s score=%.1f%% flagged=%s",
            proposal_id, score, flagged,
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Similarity check failed for proposal %s: %s", proposal_id, exc)
    finally:
        db.close()
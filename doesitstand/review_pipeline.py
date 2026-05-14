"""Core review pipeline: extract → ground → 3 parallel reviewers → meta-review."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from doesitstand.arxiv_client import search_cached
from doesitstand.contracts import validate_artifact
from doesitstand.llm_client import llm_json_flash_with_retry, llm_json_pro_with_retry, get_cost_report, reset_cost_tracker
from doesitstand.openalex_client import search_by_query_cached
from doesitstand.pdf_extract import (
    extract_pdf_text, get_head_excerpt, get_sandwich_excerpt,
    extract_sections, get_reviewer_text,
)
from doesitstand.prompts import get_prompt
# from doesitstand.stats import compute_score_cis  # Sprint 4: re-enable after calibration dataset

logger = logging.getLogger(__name__)

# Max arxiv results per query
_ARXIV_MAX_RESULTS = 10
_ARXIV_GROUNDING_TIMEOUT_S = 12
_ARXIV_GROUNDING_MAX_RETRIES = 1
_OPENALEX_GROUNDING_TIMEOUT_S = 12
_OPENALEX_GROUNDING_MAX_RETRIES = 1


# ---------------------------------------------------------------------------
# Cross-reviewer agreement
# ---------------------------------------------------------------------------

def _extract_keywords_from_review(review_data: dict) -> set[str]:
    """Extract lowercase keyword tokens from a reviewer's markdown."""
    md = review_data.get("review_markdown", "")
    # Extract bullet-point items and section headers as tokens
    tokens = re.findall(r"(?:^[-*]\s+|\n#+\s+)([^\n]{5,80})", md)
    return {t.lower().strip() for t in tokens}


def compute_reviewer_agreement(reviews: dict[str, dict]) -> dict[str, Any]:
    """Compute pairwise Jaccard similarity between reviewer weakness sets."""
    pairs = [
        ("reviewer_a", "reviewer_b"),
        ("reviewer_a", "reviewer_c"),
        ("reviewer_b", "reviewer_c"),
    ]
    keywords = {k: _extract_keywords_from_review(v) for k, v in reviews.items()}
    agreement = {}
    for r1, r2 in pairs:
        s1, s2 = keywords.get(r1, set()), keywords.get(r2, set())
        union = s1 | s2
        jaccard = len(s1 & s2) / max(len(union), 1)
        agreement[f"{r1}_vs_{r2}"] = {
            "jaccard": round(jaccard, 3),
            "shared_topics": len(s1 & s2),
            "total_topics": len(union),
        }
    return agreement


# ---------------------------------------------------------------------------
# Stage 1: Extraction
# ---------------------------------------------------------------------------


def run_extraction(
    text: str,
    venue: str = "",
    version: str = "v3",
    seed: int = 42,
) -> dict[str, Any]:
    prompt = get_prompt("extraction", version)
    head_text = get_head_excerpt(text)
    user = prompt["user"].format(head_text=head_text, venue=venue)
    result = llm_json_flash_with_retry(prompt["system"], user, seed=seed, stage="extraction")
    return result


# ---------------------------------------------------------------------------
# Stage 2: ArXiv grounding
# ---------------------------------------------------------------------------


def run_arxiv_grounding(
    extraction: dict,
    cache_dir: str | Path = ".cache/arxiv",
    no_cache: bool = False,
    max_results: int = _ARXIV_MAX_RESULTS,
) -> dict[str, Any]:
    search_queries = extraction.get("search_queries", [])
    queries_run = []

    for sq in search_queries:
        query_str = sq.get("query", "")
        if not query_str:
            continue
        try:
            results = search_cached(
                query_str,
                max_results=max_results,
                cache_dir=cache_dir,
                no_cache=no_cache,
                timeout_s=_ARXIV_GROUNDING_TIMEOUT_S,
                max_retries=_ARXIV_GROUNDING_MAX_RETRIES,
            )
            queries_run.append(
                {
                    "query": query_str,
                    "category": sq.get("category", ""),
                    "rationale": sq.get("rationale", ""),
                    "results": [r.to_dict() for r in results],
                }
            )
            logger.debug("ArXiv query %r → %d results", query_str, len(results))
        except Exception as exc:
            logger.warning("ArXiv search failed for %r: %s", query_str, exc)
            try:
                oa_results = search_by_query_cached(
                    query=query_str,
                    max_results=max_results,
                    timeout_s=_OPENALEX_GROUNDING_TIMEOUT_S,
                    max_retries=_OPENALEX_GROUNDING_MAX_RETRIES,
                    cache_dir=Path(cache_dir).parent / "openalex_search",
                    no_cache=no_cache,
                )
                queries_run.append(
                    {
                        "query": query_str,
                        "category": sq.get("category", ""),
                        "results": [r.to_dict() for r in oa_results],
                        "source": "openalex_fallback",
                        "error": f"arxiv_failed: {exc}",
                    }
                )
                logger.info("OpenAlex fallback query %r → %d results", query_str, len(oa_results))
            except Exception as oa_exc:
                queries_run.append(
                    {
                        "query": query_str,
                        "category": sq.get("category", ""),
                        "results": [],
                        "error": f"arxiv_failed: {exc}; openalex_failed: {oa_exc}",
                    }
                )

    unique_ids: set[str] = set()
    for q in queries_run:
        for r in q.get("results", []):
            unique_ids.add(r.get("arxiv_id", ""))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queries_run": queries_run,
        "unique_results_count": len(unique_ids),
    }


# ---------------------------------------------------------------------------
# Stage 3: Individual reviewers (parallel)
# ---------------------------------------------------------------------------


def _run_single_reviewer(
    reviewer_key: str,
    prompt: dict,
    extraction: dict,
    grounding: dict,
    head_text: str,
    venue: str,
    seed: int,
) -> tuple[str, dict]:
    user = prompt["user"].format(
        venue=venue,
        extraction=json.dumps(extraction),
        grounding=json.dumps(grounding),
        head_text=head_text,
    )
    result = llm_json_pro_with_retry(prompt["system"], user, seed=seed, stage=reviewer_key)
    return reviewer_key, result


def run_reviewers_parallel(
    extraction: dict,
    grounding: dict,
    head_text: str,
    venue: str = "",
    seed: int = 42,
    version: str = "v3",
    sections: dict[str, str] | None = None,
    full_text: str = "",
) -> dict[str, dict]:
    reviewer_keys = ["reviewer_a", "reviewer_b", "reviewer_c"]
    prompts = {k: get_prompt(k, version) for k in reviewer_keys}

    # Build reviewer-specific text from sections when available
    reviewer_texts: dict[str, str] = {}
    if sections and full_text:
        for key in reviewer_keys:
            reviewer_texts[key] = get_reviewer_text(sections, full_text, key)
        logger.info("Using section-aware text for reviewers")

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _run_single_reviewer,
                key,
                prompts[key],
                extraction,
                grounding,
                reviewer_texts.get(key, head_text),
                venue,
                seed,
            ): key
            for key in reviewer_keys
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, result = future.result()
                results[key] = result
                logger.debug("Reviewer %s done", key)
            except Exception as exc:
                logger.error("Reviewer %s failed: %s", key, exc)
                results[key] = {"review_markdown": f"[ERROR: {exc}]"}

    return results


def _check_reviewer_errors(results: dict[str, dict]) -> list[str]:
    """Identify reviewers that returned error markers."""
    errors = []
    for key in ("reviewer_a", "reviewer_b", "reviewer_c"):
        md = results.get(key, {}).get("review_markdown", "")
        if md.startswith("[ERROR:"):
            errors.append(f"{key}: {md}")
    return errors


# ---------------------------------------------------------------------------
# Stage 4: Meta-review (two-step: write then score)
# ---------------------------------------------------------------------------


def run_meta_review(
    reviews: dict,
    extraction: dict,
    grounding: dict,
    venue: str = "",
    seed: int = 42,
    version: str = "v3",
    two_step: bool = True,
) -> dict[str, Any]:
    # Error isolation gate
    reviewer_errors = _check_reviewer_errors(reviews)

    review_a = json.dumps(reviews.get("reviewer_a", {}))
    review_b = json.dumps(reviews.get("reviewer_b", {}))
    review_c = json.dumps(reviews.get("reviewer_c", {}))
    extraction_str = json.dumps(extraction)
    grounding_str = json.dumps(grounding)

    if two_step:
        # Step 1: write the meta-review markdown
        write_prompt = get_prompt("meta_write", version)
        write_user = write_prompt["user"].format(
            venue=venue,
            review_a=review_a,
            review_b=review_b,
            review_c=review_c,
            extraction=extraction_str,
            grounding=grounding_str,
        )
        meta_write = llm_json_pro_with_retry(write_prompt["system"], write_user, seed=seed, stage="meta_write")

        # Step 2: assign scores
        score_prompt = get_prompt("meta_score", version)
        score_user = score_prompt["user"].format(
            venue=venue,
            meta_review_md=meta_write.get("final_review_markdown", ""),
            extraction=extraction_str,
            grounding=grounding_str,
            review_a=review_a,
            review_b=review_b,
            review_c=review_c,
        )
        meta_score = llm_json_pro_with_retry(score_prompt["system"], score_user, seed=seed, stage="meta_score")

        # Cap confidence when reviewer perspectives are missing
        final_confidence = meta_score.get("final_confidence", 3)
        if reviewer_errors:
            final_confidence = min(final_confidence, 3)
            logger.warning(
                "Capping confidence to %d due to %d reviewer error(s): %s",
                final_confidence, len(reviewer_errors), reviewer_errors,
            )

        return {
            "consensus_points": meta_write.get("consensus_points", []),
            "conflicts": meta_write.get("conflicts", []),
            "resolution_rationale": meta_write.get("resolution_rationale", ""),
            "final_review_markdown": meta_write.get("final_review_markdown", ""),
            "final_decision": meta_score.get("final_decision", "Borderline"),
            "final_confidence": final_confidence,
            "final_scores": meta_score.get("final_scores", {}),
            "reviewer_errors": reviewer_errors if reviewer_errors else None,
        }
    else:
        combined_prompt = get_prompt("meta_combined", version)
        combined_user = combined_prompt["user"].format(
            venue=venue,
            review_a=review_a,
            review_b=review_b,
            review_c=review_c,
            extraction=extraction_str,
            grounding=grounding_str,
        )
        result = llm_json_pro_with_retry(combined_prompt["system"], combined_user, seed=seed, stage="meta_combined")
        # Cap confidence on combined path too
        if reviewer_errors:
            confidence = result.get("final_confidence", 3)
            result["final_confidence"] = min(confidence, 3)
            result["reviewer_errors"] = reviewer_errors
            logger.warning(
                "Capping confidence (combined path) due to %d reviewer error(s)",
                len(reviewer_errors),
            )
        return result


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def run_review(
    pdf_path: str | Path,
    outdir: str | Path,
    venue: str = "",
    version: str = "v3",
    seed: int = 42,
    no_cache: bool = False,
) -> tuple[Path, Path]:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = outdir / ".cache" / "arxiv"

    reset_cost_tracker()

    logger.info("Extracting text from %s", pdf_path)
    text = extract_pdf_text(pdf_path)
    head_text = get_head_excerpt(text)
    sandwich_text = get_sandwich_excerpt(text)

    # Section-aware extraction for reviewer-specific text
    sections = extract_sections(text)
    if sections:
        logger.info("Detected %d sections: %s", len(sections), list(sections.keys()))

    logger.info("Running LLM extraction")
    extraction = run_extraction(sandwich_text, venue, version, seed)

    logger.info(
        "Running ArXiv grounding (%d queries)",
        len(extraction.get("search_queries", [])),
    )
    grounding = run_arxiv_grounding(extraction, cache_dir=cache_dir, no_cache=no_cache)

    logger.info("Running 3 parallel reviewers")
    reviews = run_reviewers_parallel(
        extraction, grounding, head_text, venue, seed, version,
        sections=sections, full_text=text,
    )

    # Cross-reviewer agreement metrics
    agreement = compute_reviewer_agreement(reviews)
    logger.info("Reviewer agreement: %s", json.dumps(agreement))

    logger.info("Running meta-review")
    meta_review = run_meta_review(reviews, extraction, grounding, venue, seed, version)

    evidence = {
        "paper_path": str(Path(pdf_path).resolve()),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": version,
        "seed": seed,
        "extraction": extraction,
        "grounding": grounding,
        "reviews": reviews,
        "meta_review": meta_review,
        "reviewer_agreement": agreement,
        "cost": get_cost_report(),
        # score_confidence_intervals: Sprint 4 — needs calibration dataset (n≥20 papers with human scores)
    }

    validate_artifact(evidence, "evidence.v1")

    evidence_path = outdir / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False))
    logger.info("Wrote %s", evidence_path)

    review_md = meta_review.get("final_review_markdown", "")
    review_path = outdir / "review.md"
    review_path.write_text(review_md, encoding="utf-8")
    logger.info("Wrote %s", review_path)

    return review_path, evidence_path

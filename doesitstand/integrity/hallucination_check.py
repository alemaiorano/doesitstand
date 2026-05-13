"""Heuristic hallucination check: compare grounding IDs cited in the review vs paper's references."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)


def _extract_cited_ids(markdown: str) -> set[str]:
    """Extract arxiv IDs mentioned in the review markdown."""
    return set(_ARXIV_URL_RE.findall(markdown))


def _strip_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id)


def run_hallucination_check(
    evidence_path: str | Path,
    reference_report_path: str | Path,
    outdir: str | Path,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    evidence = json.loads(Path(evidence_path).read_text())
    ref_report = json.loads(Path(reference_report_path).read_text())

    # IDs in the paper's own reference list
    paper_ref_ids: set[str] = set()
    for ref in ref_report.get("references", []):
        aid = ref.get("arxiv_id")
        if aid:
            paper_ref_ids.add(_strip_version(aid))

    # IDs from grounding queries (external papers fetched during review)
    grounding_ids: set[str] = set()
    for q in evidence.get("grounding", {}).get("queries_run", []):
        for r in q.get("results", []):
            aid = r.get("arxiv_id", "")
            if aid:
                grounding_ids.add(_strip_version(aid))

    # IDs cited in the final review markdown
    review_md = evidence.get("meta_review", {}).get("final_review_markdown", "")
    # Also check individual reviewer markdowns
    for reviewer_data in evidence.get("reviews", {}).values():
        review_md += "\n" + reviewer_data.get("review_markdown", "")

    cited_in_review: set[str] = {_strip_version(i) for i in _extract_cited_ids(review_md)}

    # Potential hallucinations: IDs cited in the review but NOT in the paper's references
    # AND NOT in the grounding (i.e., not sourced from anywhere we know)
    unsourced = cited_in_review - paper_ref_ids - grounding_ids

    potential_hallucinations = [
        {
            "arxiv_id": aid,
            "type": "unsourced_citation",
            "note": "Cited in review but not found in paper references or grounding digest",
        }
        for aid in sorted(unsourced)
    ]

    report = {
        "paper_path": evidence.get("paper_path", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_ref_ids_count": len(paper_ref_ids),
        "grounding_ids_count": len(grounding_ids),
        "cited_in_review_count": len(cited_in_review),
        "potential_hallucinations": potential_hallucinations,
        "hallucination_count": len(potential_hallucinations),
    }

    out_path = outdir / "hallucination_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("Wrote %s (%d potential hallucinations)", out_path, len(potential_hallucinations))
    return out_path

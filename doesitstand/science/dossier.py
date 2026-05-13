"""Build a structured paper dossier from evidence.json (no LLM call needed)."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from doesitstand.contracts import validate_artifact

logger = logging.getLogger(__name__)


def build_dossier(
    evidence_path: str | Path,
    outdir: str | Path,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    evidence = json.loads(Path(evidence_path).read_text())
    extraction = evidence.get("extraction", {})
    grounding = evidence.get("grounding", {})

    # Collect related works from grounding, deduplicated by arxiv_id.
    # Allowlist of relevant ArXiv categories to avoid off-domain false positives.
    # cs.OH (Other CS), cs.CY (Computers & Society), cs.NI (Networking) etc. are excluded
    # because ArXiv full-text search (`all:`) routinely returns off-domain results.
    _ALLOWED_CAT_PREFIXES = (
        "cs.AI", "cs.CL", "cs.CV", "cs.DB", "cs.DC", "cs.DS",
        "cs.GT", "cs.IR", "cs.IT", "cs.LG", "cs.MA", "cs.NE",
        "cs.PL", "cs.SE", "cs.CR", "cs.HC",
        "stat.ML", "stat.AP", "stat.ME",
        "econ.EM",
    )
    seen_ids: set[str] = set()
    related_works = []
    for q in grounding.get("queries_run", []):
        for r in q.get("results", []):
            aid = r.get("arxiv_id", "")
            if not aid or aid in seen_ids:
                continue
            cat = r.get("primary_category") or ""
            if not any(cat.startswith(p) for p in _ALLOWED_CAT_PREFIXES):
                logger.debug("Skipping off-domain ArXiv result %s (category=%r)", aid, cat)
                continue
            seen_ids.add(aid)
            related_works.append({
                "arxiv_id": aid,
                "title": r.get("title", ""),
                "relation": q.get("category", "related"),
            })

    claims = extraction.get("claims", [])
    summary = extraction.get("summary", "")
    # Derive a brief "method" description from the summary (first sentence or two)
    method_sentences = summary.split(". ")
    method = ". ".join(method_sentences[:2]).strip()
    if method and not method.endswith("."):
        method += "."

    dossier = {
        "paper_path": evidence.get("paper_path", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": extraction.get("title", ""),
        "summary": summary,
        "method": method,
        "results": claims,
        "claims": claims,
        "keywords": extraction.get("keywords", []),
        "related_works": related_works,
    }

    validate_artifact(dossier, "dossier.v1")

    out_path = outdir / "paper_dossier.json"
    out_path.write_text(json.dumps(dossier, indent=2, ensure_ascii=False))
    logger.info("Wrote %s (%d related works)", out_path, len(related_works))
    return out_path

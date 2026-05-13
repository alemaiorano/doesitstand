"""Per-claim LLM fact-check against extraction and grounding evidence."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from doesitstand.llm_client import llm_json_pro

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a fact-checker. Given a claim and the paper's extracted facts and a sample of "
    "grounding evidence, assess whether the claim is supported by the provided evidence. "
    "Return ONLY valid JSON."
)

_USER = (
    "Assess whether the following claim is supported by the paper's own extracted facts "
    "and the provided grounding evidence sample.\n"
    "\n"
    "Claim: {claim}\n"
    "\n"
    "Paper extracted facts (JSON):\n"
    "{extraction_json}\n"
    "\n"
    "Grounding evidence sample (first 3 results, JSON):\n"
    "{grounding_sample_json}\n"
    "\n"
    "Output JSON schema:\n"
    "{{\n"
    '  "claim": string,\n'
    '  "verdict": "supported"|"unsupported"|"uncertain",\n'
    '  "evidence_quote": string,\n'
    '  "confidence": 1|2|3|4|5\n'
    "}}"
)


def run_claim_verification(
    evidence_path: str | Path,
    outdir: str | Path,
    max_claims: int = 10,
    seed: int = 42,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    evidence = json.loads(Path(evidence_path).read_text())
    extraction = evidence.get("extraction", {})
    claims = extraction.get("claims", [])[:max_claims]

    # Build a compact grounding sample (first 3 results across all queries)
    grounding_sample = []
    for q in evidence.get("grounding", {}).get("queries_run", []):
        for r in q.get("results", [])[:3]:
            grounding_sample.append(
                {
                    "arxiv_id": r.get("arxiv_id"),
                    "title": r.get("title"),
                    "summary": r.get("summary", "")[:300],
                }
            )
            if len(grounding_sample) >= 3:
                break
        if len(grounding_sample) >= 3:
            break

    extraction_compact = {
        "title": extraction.get("title", ""),
        "summary": extraction.get("summary", ""),
        "keywords": extraction.get("keywords", []),
    }

    results = []
    for claim in claims:
        try:
            user = _USER.format(
                claim=claim,
                extraction_json=json.dumps(extraction_compact),
                grounding_sample_json=json.dumps(grounding_sample),
            )
            verdict = llm_json_pro(_SYSTEM, user, seed=seed)
            results.append(verdict)
            logger.debug("Claim verdict: %s → %s", claim[:60], verdict.get("verdict"))
        except Exception as exc:
            logger.warning("Claim verification failed for %r: %s", claim[:60], exc)
            results.append(
                {
                    "claim": claim,
                    "verdict": "uncertain",
                    "evidence_quote": "",
                    "confidence": 1,
                }
            )

    supported = sum(1 for r in results if r.get("verdict") == "supported")
    unsupported = sum(1 for r in results if r.get("verdict") == "unsupported")
    uncertain = sum(1 for r in results if r.get("verdict") == "uncertain")

    report = {
        "paper_path": evidence.get("paper_path", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claims_checked": len(results),
        "supported_count": supported,
        "unsupported_count": unsupported,
        "uncertain_count": uncertain,
        "claims": results,
    }

    out_path = outdir / "claim_verification_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info(
        "Wrote %s (supported=%d, unsupported=%d, uncertain=%d)",
        out_path,
        supported,
        unsupported,
        uncertain,
    )
    return out_path

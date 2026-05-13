"""Screen hypotheses in an agenda and produce a portfolio."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from doesitstand.contracts import validate_artifact
from doesitstand.llm_client import llm_json_pro
from doesitstand.screen_prompts import get_screen_prompt

logger = logging.getLogger(__name__)


def _deterministic_decision(hyp: dict) -> str:
    """Apply rule-based screening without an LLM call."""
    feasibility = hyp.get("feasibility", {})
    days = feasibility.get("estimated_days", 0) or 0
    risks = feasibility.get("risks", [])
    novelty = hyp.get("novelty_flags", {})
    likely_known = novelty.get("likely_known", False)

    if likely_known:
        return "drop"
    if days > 30 or len(risks) > 2:
        return "review"
    return "keep"


def run_screening(
    agenda_path: str | Path,
    outdir: str | Path,
    use_llm: bool = False,
    version: str = "v1",
    seed: int = 42,
) -> tuple[Path, Path]:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    agenda = json.loads(Path(agenda_path).read_text())

    # Flatten all hypotheses from all clusters
    all_hyps: list[dict] = []
    for cluster in agenda.get("clusters", []):
        all_hyps.extend(cluster.get("hypotheses", []))

    decisions: list[dict] = []

    if use_llm and all_hyps:
        prompt = get_screen_prompt("screening_judge", version)
        user = prompt["user"].format(agenda_json=json.dumps(agenda, indent=2))
        try:
            result = llm_json_pro(prompt["system"], user, seed=seed)
            decisions = result.get("hypotheses", [])
        except Exception as exc:
            logger.warning(
                "Screening LLM failed, falling back to deterministic: %s", exc
            )
            use_llm = False

    if not use_llm:
        for hyp in all_hyps:
            decision = _deterministic_decision(hyp)
            decisions.append(
                {
                    "hypothesis_id": hyp.get("hypothesis_id", ""),
                    "decision": decision,
                    "score": 1.0
                    if decision == "keep"
                    else (0.5 if decision == "review" else 0.0),
                    "reasons": [],
                }
            )

    # Build decision lookup
    decision_map = {d["hypothesis_id"]: d for d in decisions}

    keep, review, drop = [], [], []
    for hyp in all_hyps:
        hid = hyp.get("hypothesis_id", "")
        dec = decision_map.get(hid, {}).get("decision", "review")
        if dec == "keep":
            keep.append(hyp)
        elif dec == "drop":
            drop.append(hyp)
        else:
            review.append(hyp)

    portfolio = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keep": keep,
        "review": review,
        "drop": drop,
    }
    validate_artifact(portfolio, "portfolio.v1")

    screening_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "llm" if use_llm else "deterministic",
        "total_hypotheses": len(all_hyps),
        "keep_count": len(keep),
        "review_count": len(review),
        "drop_count": len(drop),
        "decisions": decisions,
    }

    portfolio_path = outdir / "portfolio.json"
    portfolio_path.write_text(json.dumps(portfolio, indent=2, ensure_ascii=False))

    report_path = outdir / "screening_report.json"
    report_path.write_text(json.dumps(screening_report, indent=2, ensure_ascii=False))

    logger.info(
        "Wrote %s (keep=%d review=%d drop=%d)",
        portfolio_path,
        len(keep),
        len(review),
        len(drop),
    )
    return portfolio_path, report_path

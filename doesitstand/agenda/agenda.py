"""Aggregate hypotheses from multiple runs and build a research agenda."""

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from doesitstand.agenda_prompts import get_agenda_prompt
from doesitstand.contracts import validate_artifact
from doesitstand.llm_client import llm_json_pro

logger = logging.getLogger(__name__)


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _keyword_set(hyp: dict) -> set[str]:
    """Extract a simple keyword set from a hypothesis for clustering."""
    words: set[str] = set()
    for field in ("statement", "rationale", "operationalization"):
        text = hyp.get(field, "")
        words.update(w.lower() for w in text.split() if len(w) > 4)
    for assumption in hyp.get("assumptions", []):
        words.update(w.lower() for w in assumption.split() if len(w) > 4)
    return words


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster_hypotheses(hypotheses: list[dict], threshold: float = 0.25) -> list[dict]:
    """Simple keyword-overlap clustering; no external NLP dependencies."""
    clusters: list[
        dict
    ] = []  # {"cluster_id": str, "label": str, "hypotheses": [...], "keywords": set}

    for hyp in hypotheses:
        kw = _keyword_set(hyp)
        best_cluster = None
        best_score = 0.0

        for cluster in clusters:
            score = _jaccard(kw, cluster["keywords"])
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster is not None and best_score >= threshold:
            best_cluster["hypotheses"].append(hyp)
            best_cluster["keywords"] |= kw
        else:
            cid = f"C{len(clusters) + 1:03d}"
            # Label = top-3 most common words from hypothesis keywords
            top_words = [w for w, _ in Counter(kw).most_common(3)]
            clusters.append(
                {
                    "cluster_id": cid,
                    "label": " / ".join(top_words) if top_words else cid,
                    "hypotheses": [hyp],
                    "keywords": kw,
                }
            )

    # Strip internal keywords set before returning
    return [
        {
            "cluster_id": c["cluster_id"],
            "label": c["label"],
            "hypotheses": c["hypotheses"],
        }
        for c in clusters
    ]


def run_agenda(
    runs_dirs: list[str | Path],
    outdir: str | Path,
    version: str = "v1",
    seed: int = 42,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    all_hypotheses: list[dict] = []
    sources: list[str] = []

    for run_dir in runs_dirs:
        jsonl_path = Path(run_dir) / "hypothesis_backlog.jsonl"
        if jsonl_path.exists():
            hyps = _load_jsonl(jsonl_path)
            all_hypotheses.extend(hyps)
            sources.append(str(jsonl_path))
            logger.info("Loaded %d hypotheses from %s", len(hyps), jsonl_path)
        else:
            logger.warning("No hypothesis_backlog.jsonl in %s", run_dir)

    if not all_hypotheses:
        logger.warning("No hypotheses found across all run dirs")

    clusters = _cluster_hypotheses(all_hypotheses)
    logger.info(
        "Clustered %d hypotheses into %d clusters", len(all_hypotheses), len(clusters)
    )

    # LLM summarize
    agenda_for_llm = {
        "sources": sources,
        "clusters": clusters,
        "total_hypotheses": len(all_hypotheses),
    }
    prompt = get_agenda_prompt("agenda_summarizer", version)
    user = prompt["user"].format(agenda_json=json.dumps(agenda_for_llm, indent=2))
    try:
        summary = llm_json_pro(prompt["system"], user, seed=seed)
    except Exception as exc:
        logger.warning("Agenda summarizer LLM call failed: %s", exc)
        summary = {"program_summary": "", "research_questions": [], "top_clusters": []}

    agenda = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "clusters": clusters,
        "program_summary": summary.get("program_summary", ""),
        "research_questions": summary.get("research_questions", []),
        "top_clusters": summary.get("top_clusters", []),
    }

    validate_artifact(agenda, "agenda.v1")

    out_path = outdir / "research_agenda.json"
    out_path.write_text(json.dumps(agenda, indent=2, ensure_ascii=False))
    logger.info("Wrote %s", out_path)
    return out_path

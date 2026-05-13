"""Rank candidate hypotheses by feasibility and impact."""

import json
import logging
from pathlib import Path

from doesitstand.llm_client import llm_json_pro
from doesitstand.science_prompts import get_science_prompt

logger = logging.getLogger(__name__)


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def rank_hypotheses(
    dossier_path: str | Path,
    hypotheses_path: str | Path,
    outdir: str | Path,
    version: str = "v2",
    seed: int = 42,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    dossier = json.loads(Path(dossier_path).read_text())
    hypotheses = _load_jsonl(Path(hypotheses_path))

    prompt = get_science_prompt("hypothesis_ranker", version)
    user = prompt["user"].format(
        dossier_json=json.dumps(dossier, indent=2),
        hypotheses_json=json.dumps(hypotheses, indent=2),
    )
    result = llm_json_pro(prompt["system"], user, seed=seed)

    out_path = outdir / "hypotheses_ranked.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    logger.info("Wrote %s", out_path)
    return out_path

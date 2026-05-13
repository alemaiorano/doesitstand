"""Generate candidate hypotheses from the paper dossier."""

import json
import logging
from pathlib import Path

from doesitstand.llm_client import llm_json_pro
from doesitstand.science_prompts import get_science_prompt

logger = logging.getLogger(__name__)


def generate_hypotheses(
    dossier_path: str | Path,
    outdir: str | Path,
    version: str = "v2",
    seed: int = 42,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    dossier = json.loads(Path(dossier_path).read_text())
    prompt = get_science_prompt("hypothesis_miner", version)
    user = prompt["user"].format(dossier_json=json.dumps(dossier, indent=2))
    result = llm_json_pro(prompt["system"], user, seed=seed)

    hypotheses = result.get("hypotheses", [])
    # Attach stable hypothesis_id
    for i, hyp in enumerate(hypotheses):
        hyp["hypothesis_id"] = f"H{i + 1:03d}"

    out_path = outdir / "hypothesis_backlog.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for hyp in hypotheses:
            f.write(json.dumps(hyp, ensure_ascii=False) + "\n")

    logger.info("Wrote %s (%d hypotheses)", out_path, len(hypotheses))
    return out_path

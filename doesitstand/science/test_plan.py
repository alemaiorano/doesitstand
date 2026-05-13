"""Generate a minimal test plan for the top-ranked hypothesis."""

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


def generate_test_plan(
    dossier_path: str | Path,
    ranked_path: str | Path,
    hypotheses_path: str | Path,
    outdir: str | Path,
    version: str = "v2",
    seed: int = 42,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    dossier = json.loads(Path(dossier_path).read_text())
    ranked = json.loads(Path(ranked_path).read_text())
    hypotheses = _load_jsonl(Path(hypotheses_path))

    # Build lookup by hypothesis_id
    hyp_by_id = {h["hypothesis_id"]: h for h in hypotheses}

    # Pick top-ranked hypothesis (rank == 1)
    ranking = sorted(ranked.get("ranking", []), key=lambda x: x.get("rank", 999))
    top_id = ranking[0]["hypothesis_id"] if ranking else None
    top_hyp = hyp_by_id.get(top_id, hypotheses[0] if hypotheses else {})

    prompt = get_science_prompt("test_plan_writer", version)
    user = prompt["user"].format(
        dossier_json=json.dumps(dossier, indent=2),
        hypothesis_json=json.dumps(top_hyp, indent=2),
    )
    result = llm_json_pro(prompt["system"], user, seed=seed)

    yaml_content = result.get("test_plan_yaml", "")
    out_path = outdir / "test_plan.yaml"
    out_path.write_text(yaml_content, encoding="utf-8")
    logger.info("Wrote %s", out_path)
    return out_path

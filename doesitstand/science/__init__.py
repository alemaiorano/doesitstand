from pathlib import Path

from doesitstand.science.dossier import build_dossier
from doesitstand.science.hypotheses import generate_hypotheses
from doesitstand.science.ranking import rank_hypotheses
from doesitstand.science.test_plan import generate_test_plan


def run_science(
    evidence_path: str | Path,
    outdir: str | Path,
    seed: int = 42,
) -> tuple[Path, Path, Path, Path]:
    dossier_path = build_dossier(evidence_path, outdir)
    hypotheses_path = generate_hypotheses(dossier_path, outdir, seed=seed)
    ranked_path = rank_hypotheses(dossier_path, hypotheses_path, outdir, seed=seed)
    test_plan_path = generate_test_plan(dossier_path, ranked_path, hypotheses_path, outdir, seed=seed)
    return dossier_path, hypotheses_path, ranked_path, test_plan_path

"""CLI entry point for the paper review system."""

import json
import logging
import sys
from pathlib import Path

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)


@click.group()
def main():
    """Paper review system powered by Gemini."""
    pass


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option(
    "--outdir", "-o", default="./output", show_default=True, help="Output directory"
)
@click.option("--venue", default="", help="Target venue style (e.g. NeurIPS, ICML)")
@click.option("--version", default="v3", show_default=True, help="Prompt version")
@click.option(
    "--seed",
    default=42,
    type=int,
    show_default=True,
    help="Random seed for reproducibility",
)
@click.option("--no-cache", is_flag=True, help="Bypass ArXiv cache")
def review(pdf_path, outdir, venue, version, seed, no_cache):
    """Run the full review pipeline for a single PDF."""
    from doesitstand.review_pipeline import run_review

    Path(outdir).mkdir(parents=True, exist_ok=True)
    review_path, evidence_path = run_review(
        pdf_path, outdir, venue, version, seed, no_cache
    )
    click.echo(
        json.dumps(
            {"review_md": str(review_path), "evidence_json": str(evidence_path)},
            indent=2,
        )
    )


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option(
    "--evidence",
    "evidence_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to evidence.json from the review step",
)
@click.option("--outdir", "-o", default="./output", show_default=True)
@click.option("--max-claims", default=10, type=int, show_default=True)
@click.option("--no-cache", is_flag=True)
def integrity(pdf_path, evidence_path, outdir, max_claims, no_cache):
    """Run integrity checks: reference resolution, hallucination detection, claim verification."""
    from doesitstand.integrity.reference_check import run_reference_check
    from doesitstand.integrity.hallucination_check import run_hallucination_check
    from doesitstand.integrity.claim_verification import run_claim_verification

    Path(outdir).mkdir(parents=True, exist_ok=True)
    ref_path = run_reference_check(pdf_path, outdir, no_cache)
    hall_path = run_hallucination_check(evidence_path, str(ref_path), outdir)
    claim_path = run_claim_verification(evidence_path, outdir, max_claims)
    click.echo(
        json.dumps(
            {
                "reference_check": str(ref_path),
                "hallucination_report": str(hall_path),
                "claim_verification": str(claim_path),
            },
            indent=2,
        )
    )


@main.command()
@click.argument("evidence_path", type=click.Path(exists=True))
@click.option("--outdir", "-o", default="./output", show_default=True)
@click.option("--seed", default=42, type=int, show_default=True)
def science(evidence_path, outdir, seed):
    """Run science planning: dossier, hypotheses, ranking, test plan."""
    from doesitstand.science import run_science

    Path(outdir).mkdir(parents=True, exist_ok=True)
    paths = run_science(evidence_path, outdir, seed)
    click.echo(
        json.dumps(
            {
                "dossier": str(paths[0]),
                "hypotheses": str(paths[1]),
                "ranked": str(paths[2]),
                "test_plan": str(paths[3]),
            },
            indent=2,
        )
    )


@main.command()
@click.argument("runs_dirs", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--outdir", "-o", default="./output", show_default=True)
@click.option("--seed", default=42, type=int, show_default=True)
def agenda(runs_dirs, outdir, seed):
    """Aggregate hypotheses from multiple run directories into a research agenda."""
    from doesitstand.agenda.agenda import run_agenda

    Path(outdir).mkdir(parents=True, exist_ok=True)
    agenda_path = run_agenda(list(runs_dirs), outdir, seed=seed)
    click.echo(json.dumps({"agenda": str(agenda_path)}, indent=2))


@main.command()
@click.argument("agenda_path", type=click.Path(exists=True))
@click.option("--outdir", "-o", default="./output", show_default=True)
@click.option(
    "--use-llm",
    is_flag=True,
    help="Use LLM for screening (default: deterministic rules)",
)
@click.option("--seed", default=42, type=int, show_default=True)
def screen(agenda_path, outdir, use_llm, seed):
    """Screen hypotheses in a research agenda and produce a portfolio."""
    from doesitstand.screening.screen import run_screening

    Path(outdir).mkdir(parents=True, exist_ok=True)
    portfolio_path, report_path = run_screening(agenda_path, outdir, use_llm, seed=seed)
    click.echo(
        json.dumps(
            {
                "portfolio": str(portfolio_path),
                "screening_report": str(report_path),
            },
            indent=2,
        )
    )


@main.command()
@click.argument("paper_dir", type=click.Path(exists=True))
@click.option(
    "--logs",
    default="main.log main_taisap_blind.log",
    show_default=True,
    help="Space-separated log file names relative to paper_dir",
)
@click.option("--skip-ref-check", is_flag=True, help="Skip reference_check.py")
@click.option("--skip-policy", is_flag=True, help="Skip policy/reporting signal checks")
@click.option(
    "--policy-strict", is_flag=True, help="Make missing policy signals fail the run"
)
@click.option(
    "--policy-profile",
    default=None,
    type=click.Path(exists=True),
    help="JSON profile with venue-specific policy signals (e.g. profiles/tmlr.json)",
)
@click.option("--outdir", "-o", default="./output", show_default=True)
def guard(paper_dir, logs, skip_ref_check, skip_policy, policy_strict, policy_profile, outdir):
    """Run LaTeX structural validation: labels, figures, logs, policy signals."""
    from doesitstand.guard import run_guard

    Path(outdir).mkdir(parents=True, exist_ok=True)
    result = run_guard(
        paper_dir=paper_dir,
        log_names=logs,
        skip_ref_check=skip_ref_check,
        skip_policy=skip_policy,
        policy_strict=policy_strict,
        policy_profile=policy_profile,
        outdir=outdir,
    )
    click.echo(json.dumps(result.to_dict(), indent=2))
    sys.exit(result.exit_code)


@main.command()
@click.argument("bib_path", type=click.Path(exists=True))
@click.argument("tex_paths", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--outdir", "-o", default="./output", show_default=True)
def ref_check(bib_path, tex_paths, outdir):
    """Validate BibTeX: duplicate keys, unused/undefined citations."""
    from doesitstand.ref_check import run_ref_check

    Path(outdir).mkdir(parents=True, exist_ok=True)
    result = run_ref_check(bib_path, list(tex_paths), outdir)
    click.echo(json.dumps(result.to_dict(), indent=2))
    sys.exit(1 if result.has_issues else 0)


@main.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--outdir", "-o", default="./output", show_default=True)
@click.option("--venue", default="", help="Target venue style")
@click.option("--version", default="v3", show_default=True)
@click.option("--seed", default=42, type=int, show_default=True)
@click.option("--no-cache", is_flag=True)
@click.option(
    "--integrity/--no-integrity", "run_integrity", default=True, show_default=True
)
@click.option("--science/--no-science", "run_sci", default=True, show_default=True)
@click.option(
    "--runs-dir",
    "runs_dirs",
    multiple=True,
    type=click.Path(exists=True),
    help="Additional run dirs for multi-paper agenda",
)
@click.option("--max-claims", default=10, type=int, show_default=True)
@click.option(
    "--paper-dir",
    "paper_dir",
    default=None,
    type=click.Path(exists=True),
    help="LaTeX paper directory — if provided, runs guard checks (labels, figures, policy signals)",
)
@click.option(
    "--policy-profile",
    default=None,
    type=click.Path(exists=True),
    help="JSON venue policy profile for guard (e.g. profiles/tmlr.json)",
)
def e2e(
    pdf_path,
    outdir,
    venue,
    version,
    seed,
    no_cache,
    run_integrity,
    run_sci,
    runs_dirs,
    max_claims,
    paper_dir,
    policy_profile,
):
    """End-to-end pipeline: review → integrity → science → (optional) agenda + screen."""
    from doesitstand.review_pipeline import run_review
    from doesitstand.integrity.reference_check import run_reference_check
    from doesitstand.integrity.hallucination_check import run_hallucination_check
    from doesitstand.integrity.claim_verification import run_claim_verification
    from doesitstand.science import run_science
    from doesitstand.agenda.agenda import run_agenda
    from doesitstand.screening.screen import run_screening

    outdir_path = Path(outdir).resolve()
    outdir_path.mkdir(parents=True, exist_ok=True)
    results: dict = {}

    # Stage 0: Guard (LaTeX structural + policy checks, optional)
    if paper_dir:
        click.echo("→ Running guard checks...", err=True)
        from doesitstand.guard import run_guard
        guard_result = run_guard(
            paper_dir=paper_dir,
            policy_profile=policy_profile,
            outdir=str(outdir_path),
        )
        results["guard_report"] = str(outdir_path / "guard_report.json")
        if guard_result.exit_code != 0:
            click.echo(
                f"  ⚠ Guard found issues (exit_code={guard_result.exit_code}). "
                "See guard_report.json.",
                err=True,
            )

    # Stage 1: Review
    click.echo("→ Running review pipeline...", err=True)
    review_path, evidence_path = run_review(
        pdf_path, str(outdir_path), venue, version, seed, no_cache
    )
    results["review_md"] = str(review_path)
    results["evidence_json"] = str(evidence_path)

    # Stage 2: Integrity
    if run_integrity:
        click.echo("→ Running integrity checks...", err=True)
        ref_path = run_reference_check(pdf_path, str(outdir_path), no_cache)
        hall_path = run_hallucination_check(
            str(evidence_path), str(ref_path), str(outdir_path)
        )
        claim_path = run_claim_verification(
            str(evidence_path), str(outdir_path), max_claims, seed
        )
        results["reference_check"] = str(ref_path)
        results["hallucination_report"] = str(hall_path)
        results["claim_verification"] = str(claim_path)

    # Stage 3: Science
    if run_sci:
        click.echo("→ Running science planning...", err=True)
        s_paths = run_science(str(evidence_path), str(outdir_path), seed)
        results["dossier"] = str(s_paths[0])
        results["hypotheses"] = str(s_paths[1])
        results["ranked"] = str(s_paths[2])
        results["test_plan"] = str(s_paths[3])

    # Stage 4: Agenda + Screening (multi-paper)
    if runs_dirs:
        click.echo("→ Building research agenda...", err=True)
        all_dirs = list(runs_dirs) + [str(outdir_path)]
        agenda_path = run_agenda(all_dirs, str(outdir_path), seed=seed)
        portfolio_path, screen_path = run_screening(str(agenda_path), str(outdir_path))
        results["agenda"] = str(agenda_path)
        results["portfolio"] = str(portfolio_path)
        results["screening_report"] = str(screen_path)

    click.echo(json.dumps(results, indent=2))

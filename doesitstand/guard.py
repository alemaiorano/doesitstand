"""LaTeX structural validation: labels, figures, logs, policy signals."""

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    label_issues: list[dict] = field(default_factory=list)
    image_issues: list[dict] = field(default_factory=list)
    log_issues: list[dict] = field(default_factory=list)
    policy_signals: dict = field(default_factory=dict)
    exit_code: int = 0

    def to_dict(self) -> dict:
        return {
            "label_issues": self.label_issues,
            "image_issues": self.image_issues,
            "log_issues": self.log_issues,
            "policy_signals": self.policy_signals,
            "exit_code": self.exit_code,
            "passed": self.exit_code == 0,
        }


def _has_rg() -> bool:
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=False)
        return True
    except FileNotFoundError:
        return False


HAS_RG = _has_rg()


def _run_ripgrep(pattern: str, path: Path, glob: str = "*.tex") -> list[str]:
    if HAS_RG:
        result = subprocess.run(
            ["rg", "-i", "-n", "--glob", glob, pattern, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    else:
        matches: list[str] = []
        for f in path.rglob(glob):
            text = f.read_text(errors="ignore")
            for m in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
                matches.append(f"{f}:{m.start()}:{m.group()}")
        return matches


def _list_tex_files(paper_dir: Path) -> list[Path]:
    if HAS_RG:
        result = subprocess.run(
            ["rg", "--files", "--glob", "*.tex", str(paper_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        return [
            Path(p)
            for line in result.stdout.splitlines()
            if line.strip()
            for p in [Path(line.strip())]
            if p.exists()
        ]
    return list(paper_dir.rglob("*.tex"))


def _extract_labels(kind: str, paper_dir: Path) -> list[str]:
    pattern = rf"\\label\{{(?:sec|tab|fig|eq):[^}}]+\}}"
    matches = _run_ripgrep(pattern, paper_dir)
    labels = []
    for m in matches:
        found = re.findall(rf"\\label\{{({kind}:[^}}]+)\}}", m)
        labels.extend(found)
    return sorted(set(labels))


def _count_refs_for_label(label: str, paper_dir: Path) -> int:
    ref_re = rf"\\(?:auto|c|C|eq|name|page|hyper)?ref\{{{re.escape(label)}\}}"
    matches = _run_ripgrep(ref_re, paper_dir)
    return len(matches)


def _check_labels(paper_dir: Path) -> list[dict]:
    issues = []
    for kind, display in [
        ("tab", "Table"),
        ("fig", "Figure"),
        ("sec", "Section"),
        ("eq", "Equation"),
    ]:
        labels = _extract_labels(kind, paper_dir)
        for label in labels:
            refs = _count_refs_for_label(label, paper_dir)
            if refs == 0:
                issues.append(
                    {
                        "kind": kind,
                        "label": label,
                        "message": f"{display} label without reference: {label}",
                    }
                )
    return issues


def _check_images(paper_dir: Path) -> list[dict]:
    issues = []
    img_pattern = r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}"
    matches = _run_ripgrep(img_pattern, paper_dir)

    for m in matches:
        parts = m.split(":", 2)
        if len(parts) < 3:
            continue
        tex_file = Path(parts[0])
        match_str = parts[2]

        rel_path = re.search(r"\{([^}]+)\}", match_str)
        if not rel_path:
            continue
        rel_path = rel_path.group(1)

        tex_dir = tex_file.parent
        candidates = [
            tex_dir / rel_path,
            paper_dir / rel_path,
        ]
        found = any(c.exists() for c in candidates)
        if not found:
            for ext in [".pdf", ".png", ".jpg", ".jpeg", ".eps"]:
                found = any((c.parent / (c.stem + ext)).exists() for c in candidates)
                if found:
                    break

        if not found:
            issues.append(
                {
                    "file": str(tex_file.relative_to(paper_dir)),
                    "missing": rel_path,
                    "message": f"Missing figure file: {rel_path}",
                }
            )
    return issues


def _check_logs(
    paper_dir: Path, log_names: str = "main.log main_taisap_blind.log"
) -> list[dict]:
    issues = []
    log_re = r"undefined references|undefined citations|Citation .* undefined|Reference .* undefined|There were undefined"

    for log_name in log_names.split():
        log_path = paper_dir / log_name
        if not log_path.exists():
            continue

        text = log_path.read_text(errors="ignore")
        found = re.findall(log_re, text, re.IGNORECASE)
        if found:
            issues.append(
                {
                    "log": log_name,
                    "patterns": found[:5],
                    "message": f"Undefined reference/citation patterns in {log_name}",
                }
            )
    return issues


POLICY_SIGNALS = [
    (
        "data_availability",
        "Data availability statement",
        r"data availability|availability of data|data can be (accessed|shared)|dataset\(s\)? (are|is) available|replication package|data.*scripts.*available|openly available",
    ),
    (
        "code_availability",
        "Code availability statement",
        r"code availability|source code|code repository|repository (is|are) available|github\.com|gitlab\.com|zenodo|figshare|dryad|osf\.io",
    ),
    (
        "limitations",
        "Limitations / threats to validity",
        r"limitations|threats to validity|external validity|internal validity",
    ),
    (
        "ethics",
        "Ethics / conflict of interest disclosure",
        r"ethics|ethical approval|irb|conflicts? of interest|competing interests?|AI tools disclosure|generative.AI|no competing",
    ),
    (
        "reproducibility",
        "Reproducibility artifact signals",
        r"reproducib|artifact|doi|zenodo|environment|docker|requirements\.txt|seed",
    ),
]


def _load_profile_signals(profile_path: str | Path) -> list[tuple[str, str, str]]:
    """Load additional policy signals from a JSON profile file."""
    data = json.loads(Path(profile_path).read_text())
    signals = []
    for sig in data.get("signals", []):
        signals.append((sig["id"], sig["name"], sig["regex"]))
    return signals


def _check_policy_signals(
    paper_dir: Path,
    strict: bool = False,
    extra_signals: list[tuple[str, str, str]] | None = None,
) -> dict:
    all_signals = POLICY_SIGNALS + (extra_signals or [])
    results = {}
    for signal_id, name, pattern in all_signals:
        found = _run_ripgrep(pattern, paper_dir)
        results[signal_id] = {
            "name": name,
            "found": len(found) > 0,
            "strict": strict,
            "passed": True,
        }
        if not found and strict:
            results[signal_id]["passed"] = False
    return results


def run_guard(
    paper_dir: str | Path,
    log_names: str = "main.log main_taisap_blind.log",
    bib_path: Optional[str] = None,
    skip_ref_check: bool = False,
    skip_policy: bool = False,
    policy_strict: bool = False,
    policy_profile: Optional[str | Path] = None,
    outdir: Optional[str | Path] = None,
) -> GuardResult:
    paper_dir = Path(paper_dir).resolve()
    result = GuardResult()

    tex_files = _list_tex_files(paper_dir)
    if not tex_files:
        result.label_issues.append({"message": "No .tex files found"})
        result.exit_code = 1
        return result

    result.label_issues = _check_labels(paper_dir)
    result.image_issues = _check_images(paper_dir)
    result.log_issues = _check_logs(paper_dir, log_names)

    if not skip_policy:
        extra = _load_profile_signals(policy_profile) if policy_profile else None
        result.policy_signals = _check_policy_signals(paper_dir, policy_strict, extra)
        for sig in result.policy_signals.values():
            if not sig["passed"]:
                result.exit_code = 1

    for issue_list in [result.label_issues, result.image_issues, result.log_issues]:
        if issue_list:
            result.exit_code = 1

    if outdir:
        outdir = Path(outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        out_path = outdir / "guard_report.json"
        out_path.write_text(json.dumps(result.to_dict(), indent=2))
        logger.info("Wrote %s", out_path)

    return result

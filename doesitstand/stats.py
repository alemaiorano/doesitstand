"""Statistical utilities for DoesItStand review pipeline."""

import random
import re


def bootstrap_ci(
    values: list[float],
    B: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, float]:
    """Compute bootstrap confidence interval for the mean of *values*.

    Returns dict with point_estimate, ci_lower, ci_upper, std_error.
    """
    if not values:
        return {"point_estimate": 0, "ci_lower": 0, "ci_upper": 0, "std_error": 0}

    rng = random.Random(seed)
    n = len(values)
    point = sum(values) / n

    if n < 2:
        return {"point_estimate": point, "ci_lower": point, "ci_upper": point, "std_error": 0}

    boot_means = []
    for _ in range(B):
        sample = rng.choices(values, k=n)
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    lo_idx = int(B * alpha / 2)
    hi_idx = int(B * (1 - alpha / 2))

    se = (sum((m - point) ** 2 for m in boot_means) / B) ** 0.5

    return {
        "point_estimate": round(point, 2),
        "ci_lower": round(boot_means[lo_idx], 2),
        "ci_upper": round(boot_means[hi_idx], 2),
        "std_error": round(se, 3),
    }


_SCORE_DIMENSIONS = [
    "originality", "quality", "clarity",
    "significance", "reproducibility", "overall",
]

# Match patterns like "originality: 7" or "Quality: 5/10" in review text
_SCORE_LINE_RE = re.compile(
    r"(originality|quality|clarity|significance|reproducibility|overall)"
    r"[\s:]*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _extract_scores_from_markdown(md: str) -> dict[str, float]:
    """Extract numerical scores mentioned in reviewer markdown text."""
    scores: dict[str, float] = {}
    for m in _SCORE_LINE_RE.finditer(md):
        dim = m.group(1).lower()
        scores[dim] = float(m.group(2))
    return scores


def compute_score_cis(
    reviews: dict,
    score_keys: list[str] | None = None,
) -> dict[str, dict]:
    """Compute bootstrap CIs for scores across reviewer outputs.

    Tries to extract numerical scores from reviewer markdown text.
    If reviewers don't mention explicit scores, returns an empty dict.
    """
    if score_keys is None:
        score_keys = _SCORE_DIMENSIONS

    per_dim: dict[str, list[float]] = {k: [] for k in score_keys}

    for reviewer_data in reviews.values():
        # Try structured scores first
        scores = reviewer_data.get("scores", {})
        # Fall back to extracting from markdown text
        if not scores:
            md = reviewer_data.get("review_markdown", "")
            scores = _extract_scores_from_markdown(md)
        for key in score_keys:
            val = scores.get(key)
            if isinstance(val, (int, float)):
                per_dim[key].append(float(val))

    return {key: bootstrap_ci(vals) for key, vals in per_dim.items() if vals}

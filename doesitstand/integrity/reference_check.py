"""Extract and resolve citations from a paper PDF."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from doesitstand.contracts import validate_artifact
from doesitstand.reference_resolver import resolve_arxiv_id
from doesitstand.pdf_extract import extract_pdf_text

logger = logging.getLogger(__name__)

_ARXIV_RE = re.compile(r"(?:arxiv[:\s./]*)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_DOI_RE = re.compile(r"\b(10\.\d{4,}/\S+)", re.IGNORECASE)


def _extract_references_section(text: str) -> str:
    """Return the text after the last 'References' / 'Bibliography' heading."""
    # Match heading on its own line, optionally followed by spaces, numbers,
    # or other non-newline chars (e.g. "References 597" from PDF line numbering).
    heading_re = re.compile(
        r"\n(References|Bibliography|REFERENCES|BIBLIOGRAPHY)[^\n]*\n",
        re.IGNORECASE,
    )
    matches = list(heading_re.finditer(text))
    if matches:
        last = matches[-1]
        return text[last.end():]
    return ""


def _split_references(refs_text: str) -> list[str]:
    """Split raw reference block into individual reference strings."""
    if not refs_text.strip():
        return []
    # Try numbered references like [1] or (1)
    numbered = re.split(r"\n\[?\d+\]?[\.\s]", refs_text)
    if len(numbered) > 2:
        return [r.strip() for r in numbered if r.strip()]
    # Fallback: split on blank lines
    return [r.strip() for r in re.split(r"\n\s*\n", refs_text) if r.strip()]


def run_reference_check(
    pdf_path: str | Path,
    outdir: str | Path,
    no_cache: bool = False,
) -> Path:
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = outdir / ".cache"

    text = extract_pdf_text(pdf_path)
    refs_text = _extract_references_section(text)
    raw_refs = _split_references(refs_text)
    logger.info("Found %d raw references in %s", len(raw_refs), pdf_path)

    resolved_refs = []
    resolved_count = 0

    for raw_ref in raw_refs:
        arxiv_match = _ARXIV_RE.search(raw_ref)
        doi_match = _DOI_RE.search(raw_ref)

        arxiv_id = arxiv_match.group(1) if arxiv_match else None
        doi = doi_match.group(1) if doi_match else None
        metadata = None
        resolved = False

        if arxiv_id:
            try:
                result = resolve_arxiv_id(
                    arxiv_id,
                    cache_dir=cache_dir,
                    no_cache=no_cache,
                )
                if result:
                    metadata = result.to_dict()
                    resolved = True
                    resolved_count += 1
            except Exception as exc:
                logger.warning("Reference resolution failed for %r: %s", arxiv_id, exc)
        elif doi:
            resolved = True  # DOI found but not further resolved here
            resolved_count += 1

        resolved_refs.append({
            "raw_ref": raw_ref[:500],  # truncate very long refs
            "arxiv_id": arxiv_id,
            "doi": doi,
            "resolved": resolved,
            "metadata": metadata,
        })

    total = len(resolved_refs)
    report = {
        "paper_path": str(Path(pdf_path).resolve()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "references": resolved_refs,
        "resolution_rate": resolved_count / total if total else 0.0,
    }

    validate_artifact(report, "reference_check_report.v1")

    out_path = outdir / "reference_check_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("Wrote %s (resolution_rate=%.2f)", out_path, report["resolution_rate"])
    return out_path

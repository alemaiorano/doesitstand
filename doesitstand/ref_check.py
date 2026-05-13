"""BibTeX validation: duplicate keys, duplicate titles, unused/undefined citations."""

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RefCheckResult:
    duplicate_keys: dict = field(default_factory=dict)
    duplicate_titles: dict = field(default_factory=dict)
    unused_references: set = field(default_factory=set)
    undefined_citations: set = field(default_factory=set)
    total_references: int = 0
    unique_references: int = 0
    total_citations: int = 0
    unique_citations: int = 0
    citation_frequency: dict = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.duplicate_keys
            or self.duplicate_titles
            or self.unused_references
            or self.undefined_citations
        )

    def to_dict(self) -> dict:
        return {
            "duplicate_keys": self.duplicate_keys,
            "duplicate_titles": self.duplicate_titles,
            "unused_references": sorted(list(self.unused_references)),
            "undefined_citations": sorted(list(self.undefined_citations)),
            "summary": {
                "total_references": self.total_references,
                "unique_references": self.unique_references,
                "total_citations": self.total_citations,
                "unique_citations": self.unique_citations,
            },
            "citation_frequency": self.citation_frequency,
            "has_issues": self.has_issues,
        }


_BIBTEX_DIRECTIVES = frozenset({"comment", "preamble", "string"})


def extract_citation_keys(bib_content: str) -> list[str]:
    pattern = r"@(\w+)\{([^,]+),"
    return [
        key.strip()
        for entry_type, key in re.findall(pattern, bib_content)
        if entry_type.lower() not in _BIBTEX_DIRECTIVES
    ]


def extract_titles(bib_content: str) -> list[str]:
    pattern = r"title=\{([^}]+)\}"
    return re.findall(pattern, bib_content)


def extract_cited_keys(tex_content: str) -> list[str]:
    pattern = (
        r"\\(?:cite[tp]?|citeauthor|citeyear|citealt|citealp"
        r"|parencite|textcite|autocite|fullcite|footcite|nocite"
        r")\*?"
        r"(?:\[[^\]]*\])*"
        r"\{([^}]+)\}"
    )
    matches = re.findall(pattern, tex_content)
    cited_keys = []
    for match in matches:
        keys = [k.strip() for k in match.split(",")]
        cited_keys.extend(keys)
    return cited_keys


def check_references(
    bib_file: Path,
    tex_files: list[Path],
) -> RefCheckResult:
    result = RefCheckResult()

    bib_content = bib_file.read_text(encoding="utf-8")

    bib_keys = extract_citation_keys(bib_content)
    result.total_references = len(bib_keys)
    result.unique_references = len(set(bib_keys))

    key_counts = Counter(bib_keys)
    result.duplicate_keys = {k: v for k, v in key_counts.items() if v > 1}

    titles = extract_titles(bib_content)
    title_counts = Counter(titles)
    result.duplicate_titles = {t: v for t, v in title_counts.items() if v > 1}

    all_cited_keys = []
    for tex_file in tex_files:
        tex_content = tex_file.read_text(encoding="utf-8")
        cited_keys = extract_cited_keys(tex_content)
        all_cited_keys.extend(cited_keys)

    result.total_citations = len(all_cited_keys)
    result.unique_citations = len(set(all_cited_keys))

    cited_set = set(all_cited_keys)
    bib_set = set(bib_keys)

    result.unused_references = bib_set - cited_set
    result.undefined_citations = cited_set - bib_set

    cite_counts = Counter(all_cited_keys)
    result.citation_frequency = dict(cite_counts.most_common())

    return result


def find_tex_files(paths: list[str | Path]) -> list[Path]:
    tex_files = []
    for path_str in paths:
        path = Path(path_str)
        if path.is_file() and path.suffix == ".tex":
            tex_files.append(path)
        elif path.is_dir():
            tex_files.extend(path.glob("**/*.tex"))
    return tex_files


def run_ref_check(
    bib_path: str | Path,
    tex_paths: list[str | Path],
    outdir: Optional[str | Path] = None,
) -> RefCheckResult:
    bib_path = Path(bib_path)
    tex_files = find_tex_files(tex_paths)

    result = check_references(bib_path, tex_files)

    if outdir:
        outdir = Path(outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        out_path = outdir / "ref_check_report.json"
        out_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        logger.info("Wrote %s", out_path)

    return result

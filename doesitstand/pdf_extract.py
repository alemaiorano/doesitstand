from pathlib import Path
import re

import pypdf


def extract_pdf_text(pdf_path: str | Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    full_text = "\n\n".join(pages)
    # Remove null bytes and normalize excessive whitespace
    full_text = full_text.replace("\x00", "")
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    return full_text.strip()


def get_head_excerpt(text: str, max_chars: int = 20000) -> str:
    if len(text) <= max_chars:
        return text
    # Try to cut at a section boundary
    chunk = text[:max_chars]
    # Prefer cutting at a markdown-style heading or blank paragraph break
    for pattern in (r"\n#+\s", r"\n\n"):
        match = None
        for m in re.finditer(pattern, chunk):
            match = m
        if match and match.start() > max_chars // 2:
            return chunk[: match.start()].strip()
    return chunk.strip()


def get_sandwich_excerpt(
    text: str, head_chars: int = 15000, tail_chars: int = 5000
) -> str:
    """Return head + tail of the paper text.

    Captures both the introduction/method (head) and the limitations/conclusion/
    references sections (tail) that are often beyond the head-only 20k window.
    The two parts are joined with an ellipsis marker so the LLM knows text was
    omitted.
    """
    total = head_chars + tail_chars
    if len(text) <= total:
        return text
    head = get_head_excerpt(text, head_chars)
    # Take the last tail_chars chars; try to start at a paragraph boundary
    raw_tail = text[-tail_chars:]
    first_para = raw_tail.find("\n\n")
    if first_para > 0 and first_para < tail_chars // 4:
        raw_tail = raw_tail[first_para:].strip()
    return head + "\n\n[...]\n\n" + raw_tail.strip()


# ---------------------------------------------------------------------------
# Section-aware extraction
# ---------------------------------------------------------------------------

# Common section header patterns in scientific papers
_SECTION_HEADER_RE = re.compile(
    r"\n(\d+(?:\.\d+)*)\s+([A-Z][^\n]{2,80})",
    re.MULTILINE,
)
_APPENDIX_RE = re.compile(r"\n(Appendix\s+[A-Z])\b", re.MULTILINE)
_REFERENCES_RE = re.compile(r"\n(References)\s*\n", re.MULTILINE)


def extract_sections(text: str) -> dict[str, str]:
    """Split paper text into named sections via header detection.

    Returns a dict mapping section labels (e.g. "1 Introduction") to their
    body text. Sections are detected by numbered headers (``1 Introduction``),
    ``Appendix X`` markers, and a ``References`` marker.
    """
    sections: dict[str, str] = {}
    # Collect all split points
    splits: list[tuple[int, str]] = []

    for m in _SECTION_HEADER_RE.finditer(text):
        label = f"{m.group(1)} {m.group(2).strip()}"
        splits.append((m.start(), label))

    for m in _APPENDIX_RE.finditer(text):
        splits.append((m.start(), m.group(1).strip()))

    for m in _REFERENCES_RE.finditer(text):
        splits.append((m.start(), m.group(1).strip()))

    if not splits:
        return sections

    splits.sort(key=lambda s: s[0])

    for i, (start, label) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(text)
        body = text[start:end].strip()
        sections[label] = body

    return sections


# Reviewer section assignments based on focal areas
_REVIEWER_SECTIONS = {
    "reviewer_a": [  # Methods & Claims
        re.compile(r"\b(3|framework|method|approach|architecture|model)\b", re.I),
        re.compile(r"\b(4|system|implementation)\b", re.I),
    ],
    "reviewer_b": [  # Experiments & Reproducibility
        re.compile(r"\b(5|setup|experiment|configuration)\b", re.I),
        re.compile(r"\b(6|result|evaluation|analysis)\b", re.I),
        re.compile(r"\b(appendix|supplementary|supplement)\b", re.I),
    ],
    "reviewer_c": [  # Clarity & Impact
        re.compile(r"\b(1|introduction|intro)\b", re.I),
        re.compile(r"\b(7|discussion|limitation|threat)\b", re.I),
        re.compile(r"\b(8|conclusion|future|summary)\b", re.I),
    ],
}


def get_reviewer_text(
    sections: dict[str, str],
    full_text: str,
    reviewer_key: str,
    budget: int = 12000,
) -> str:
    """Build reviewer-specific text from section-aware extraction.

    Selects sections matching the reviewer's focal areas. Falls back to the
    full sandwich excerpt if no sections match.
    """
    patterns = _REVIEWER_SECTIONS.get(reviewer_key, [])
    selected: list[str] = []

    for label, body in sections.items():
        if any(p.search(label) for p in patterns):
            selected.append(body)

    if not selected:
        return get_sandwich_excerpt(full_text)

    combined = "\n\n".join(selected)
    if len(combined) > budget:
        combined = get_head_excerpt(combined, budget)

    return combined

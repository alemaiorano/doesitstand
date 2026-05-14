"""Python port of marketing-simulator/apps/api/src/services/arxiv.ts"""
import fcntl
import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

from doesitstand.env import ARXIV_BASE_URL, ARXIV_USER_AGENT

logger = logging.getLogger(__name__)

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


@dataclass
class ArxivEntry:
    id: str
    arxiv_id: str
    title: str
    summary: str
    published: str
    updated: str
    authors: list[str] = field(default_factory=list)
    primary_category: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    pdf_url: Optional[str] = None
    doi: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "summary": self.summary,
            "published": self.published,
            "updated": self.updated,
            "authors": self.authors,
            "primary_category": self.primary_category,
            "categories": self.categories,
            "pdf_url": self.pdf_url,
            "doi": self.doi,
        }


def _extract_arxiv_id(url: str) -> str:
    """Extract bare arxiv ID from a URL like http://arxiv.org/abs/2301.12345v2"""
    part = url.rstrip("/").split("/")[-1]
    # Strip version suffix like v2
    if re.search(r"v\d+$", part):
        part = re.sub(r"v\d+$", "", part)
    return part


def _enforce_rate_limit(cache_dir: Path, min_interval_s: float = 5.0):
    """File-based rate limiter for ArXiv API (~1 req/5s) with cross-process locking."""
    stamp_file = Path(cache_dir) / ".last_request"
    stamp_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = stamp_file.with_suffix(".lock")

    with open(lock_file, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            if stamp_file.exists():
                try:
                    elapsed = time.time() - float(stamp_file.read_text().strip())
                    if elapsed < min_interval_s:
                        time.sleep(min_interval_s - elapsed)
                except (ValueError, OSError):
                    pass
            stamp_file.write_text(str(time.time()))
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def search(
    query: str,
    start: int = 0,
    max_results: int = 10,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    timeout_s: int = 30,
    max_retries: int = 3,
    cache_dir: str | Path | None = None,
) -> list[ArxivEntry]:
    if cache_dir is not None:
        _enforce_rate_limit(cache_dir)

    params: dict = {
        "search_query": f"all:{query}",
        "start": start,
        "max_results": max_results,
    }
    if sort_by:
        params["sortBy"] = sort_by
    if sort_order:
        params["sortOrder"] = sort_order

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                ARXIV_BASE_URL,
                params=params,
                headers={"Accept": "application/atom+xml", "User-Agent": ARXIV_USER_AGENT},
                timeout=timeout_s,
            )
            resp.raise_for_status()
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning("ArXiv request failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, exc, wait)
                time.sleep(wait)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = 2 ** attempt * 10
                    logger.warning("ArXiv rate limited (429, attempt %d/%d) — retrying in %ds", attempt + 1, max_retries, wait)
                    time.sleep(wait)
                continue
            raise
    else:
        raise last_exc  # type: ignore[misc]

    root = ET.fromstring(resp.text)
    entries: list[ArxivEntry] = []

    for entry_el in root.findall(f"{{{ATOM_NS}}}entry"):

        def _text(tag: str, ns: str = ATOM_NS) -> str:
            el = entry_el.find(f"{{{ns}}}{tag}")
            if el is not None and el.text:
                return re.sub(r"\s+", " ", el.text).strip()
            return ""

        raw_id = _text("id")
        arxiv_id = _extract_arxiv_id(raw_id)

        authors = [
            re.sub(r"\s+", " ", name_el.text or "").strip()
            for author_el in entry_el.findall(f"{{{ATOM_NS}}}author")
            for name_el in author_el.findall(f"{{{ATOM_NS}}}name")
            if name_el.text
        ]

        primary_cat_el = entry_el.find(f"{{{ARXIV_NS}}}primary_category")
        primary_category = (
            primary_cat_el.get("term") if primary_cat_el is not None else None
        )

        categories = [
            el.get("term", "")
            for el in entry_el.findall(f"{{{ATOM_NS}}}category")
            if el.get("term")
        ]

        # PDF link: <link title="pdf" ...> or <link type="application/pdf" ...>
        pdf_url: Optional[str] = None
        for link_el in entry_el.findall(f"{{{ATOM_NS}}}link"):
            if link_el.get("title") == "pdf" or link_el.get("type") == "application/pdf":
                pdf_url = link_el.get("href")
                break

        doi_text = _text("doi", ARXIV_NS) or None

        entries.append(
            ArxivEntry(
                id=raw_id,
                arxiv_id=arxiv_id,
                title=_text("title"),
                summary=_text("summary"),
                published=_text("published"),
                updated=_text("updated"),
                authors=authors,
                primary_category=primary_category,
                categories=categories,
                pdf_url=pdf_url,
                doi=doi_text,
            )
        )

    return entries


def search_cached(
    query: str,
    start: int = 0,
    max_results: int = 10,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    cache_dir: str | Path = ".cache/arxiv",
    no_cache: bool = False,
    timeout_s: int = 30,
    max_retries: int = 3,
) -> list[ArxivEntry]:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    key = hashlib.sha256(
        f"{query}|{start}|{max_results}|{sort_by}|{sort_order}".encode()
    ).hexdigest()
    cache_file = cache_path / f"{key}.json"

    if not no_cache and cache_file.exists():
        data = json.loads(cache_file.read_text())
        return [ArxivEntry(**e) for e in data]

    results = search(
        query,
        start,
        max_results,
        sort_by,
        sort_order,
        timeout_s=timeout_s,
        max_retries=max_retries,
        cache_dir=str(cache_path),
    )
    cache_file.write_text(json.dumps([e.to_dict() for e in results], indent=2))
    return results

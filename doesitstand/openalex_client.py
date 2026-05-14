"""OpenAlex API client for resolving papers by arXiv ID."""
import json
import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

from doesitstand.arxiv_client import ArxivEntry
from doesitstand.env import ARXIV_USER_AGENT

logger = logging.getLogger(__name__)


def _atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words: dict[int, str] = {}
    for word, positions in inv.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[k] for k in sorted(words.keys()))


def _extract_arxiv_id(doi: str | None, landing_url: str | None) -> str:
    """Extract bare arXiv ID from DOI or landing page URL."""
    if landing_url:
        part = landing_url.rstrip("/").split("/")[-1]
        if re.search(r"v\d+$", part):
            part = re.sub(r"v\d+$", "", part)
        return part
    if doi:
        m = re.search(r"arXiv\.(\S+)", doi)
        if m:
            return m.group(1)
    return ""


def _oa_to_entry(data: dict) -> ArxivEntry:
    loc = data.get("primary_location") or {}
    landing = (loc.get("landing_page_url") or "").replace("https://", "http://")
    doi_raw = data.get("doi") or ""
    doi_clean = doi_raw.removeprefix("https://doi.org/")
    arxiv_id = _extract_arxiv_id(doi_clean, landing)
    year = data.get("publication_year")
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in data.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]
    return ArxivEntry(
        id=landing or f"http://arxiv.org/abs/{arxiv_id}",
        arxiv_id=arxiv_id,
        title=data.get("title") or data.get("display_name") or "",
        summary=_reconstruct_abstract(data.get("abstract_inverted_index")),
        published=str(year) if year else "",
        updated=str(year) if year else "",
        authors=authors,
        primary_category=None,
        categories=[],
        pdf_url=loc.get("pdf_url"),
        doi=doi_clean or None,
    )


def fetch_by_arxiv_id(
    arxiv_id: str,
    timeout_s: int = 15,
    max_retries: int = 3,
) -> Optional[ArxivEntry]:
    """Fetch paper metadata from OpenAlex using arXiv DOI."""
    doi = f"10.48550/arXiv.{arxiv_id}"
    url = f"https://api.openalex.org/works/doi:{doi}"
    headers = {"User-Agent": ARXIV_USER_AGENT}

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_s)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _oa_to_entry(resp.json())
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                last_exc = exc
                wait = 2 ** attempt * 5
                logger.warning("OpenAlex rate limited (429, attempt %d/%d) — retrying in %ds", attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2
                logger.warning("OpenAlex request failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                time.sleep(wait)
    if last_exc is not None:
        raise last_exc
    return None


def fetch_by_arxiv_id_cached(
    arxiv_id: str,
    timeout_s: int = 15,
    max_retries: int = 3,
    cache_dir: str | Path = ".cache/openalex",
    no_cache: bool = False,
) -> Optional[ArxivEntry]:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(arxiv_id.encode()).hexdigest()
    cache_file = cache_path / f"{key}.json"

    if not no_cache and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if data is None:
                return None
            return ArxivEntry(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Ignoring corrupted OpenAlex cache file %s: %s", cache_file, exc)

    result = fetch_by_arxiv_id(arxiv_id, timeout_s=timeout_s, max_retries=max_retries)
    _atomic_write_text(cache_file, json.dumps(result.to_dict() if result else None, indent=2))
    return result


def search_by_query(
    query: str,
    max_results: int = 10,
    timeout_s: int = 15,
    max_retries: int = 2,
) -> list[ArxivEntry]:
    """Search OpenAlex works by free-text query and map into ArxivEntry objects."""
    url = "https://api.openalex.org/works"
    headers = {"User-Agent": ARXIV_USER_AGENT}
    params = {"search": query, "per-page": max_results}

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout_s)
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("results", [])
            return [_oa_to_entry(item) for item in results]
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                last_exc = exc
                wait = 2 ** attempt * 3
                logger.warning("OpenAlex search rate limited (429, attempt %d/%d) — retrying in %ds", attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2
                logger.warning("OpenAlex search failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                time.sleep(wait)
    if last_exc is not None:
        raise last_exc
    return []


def search_by_query_cached(
    query: str,
    max_results: int = 10,
    timeout_s: int = 15,
    max_retries: int = 2,
    cache_dir: str | Path = ".cache/openalex_search",
    no_cache: bool = False,
) -> list[ArxivEntry]:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{query}|{max_results}".encode()).hexdigest()
    cache_file = cache_path / f"{key}.json"

    if not no_cache and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return [ArxivEntry(**e) for e in data]
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Ignoring corrupted OpenAlex search cache %s: %s", cache_file, exc)

    results = search_by_query(
        query=query,
        max_results=max_results,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    _atomic_write_text(cache_file, json.dumps([e.to_dict() for e in results], indent=2))
    return results

"""Resolve arXiv IDs using OpenAlex with ArXiv API fallback."""
import logging
from pathlib import Path

from doesitstand.arxiv_client import ArxivEntry, search_cached
from doesitstand.openalex_client import fetch_by_arxiv_id_cached

logger = logging.getLogger(__name__)


def resolve_arxiv_id(
    arxiv_id: str,
    cache_dir: str | Path = ".cache",
    no_cache: bool = False,
) -> ArxivEntry | None:
    """Resolve an arXiv ID via OpenAlex -> ArXiv fallback chain."""
    # Step 1: OpenAlex (fast, no strict rate limit)
    try:
        result = fetch_by_arxiv_id_cached(
            arxiv_id,
            cache_dir=Path(cache_dir) / "openalex",
            no_cache=no_cache,
        )
        if result is not None:
            logger.debug("Resolved %s via OpenAlex", arxiv_id)
            return result
    except Exception as exc:
        logger.warning("OpenAlex lookup failed for %s: %s", arxiv_id, exc)

    # Step 2: ArXiv API (slow, 1 req/5s with locking)
    try:
        results = search_cached(
            arxiv_id,
            max_results=1,
            cache_dir=str(Path(cache_dir) / "arxiv"),
            no_cache=no_cache,
        )
        if results:
            logger.debug("Resolved %s via ArXiv (fallback)", arxiv_id)
            return results[0]
    except Exception as exc:
        logger.warning("ArXiv fallback failed for %s: %s", arxiv_id, exc)

    logger.info("Could not resolve arXiv ID %s via any source", arxiv_id)
    return None

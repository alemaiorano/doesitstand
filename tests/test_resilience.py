import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from doesitstand.arxiv_client import ArxivEntry, search_cached
from doesitstand.openalex_client import fetch_by_arxiv_id_cached, search_by_query_cached
from doesitstand.review_pipeline import run_arxiv_grounding


def _entry(arxiv_id: str) -> ArxivEntry:
    return ArxivEntry(
        id=f"http://arxiv.org/abs/{arxiv_id}",
        arxiv_id=arxiv_id,
        title="t",
        summary="s",
        published="2024",
        updated="2024",
    )


class ResilienceTests(unittest.TestCase):
    def test_grounding_marks_arxiv_source(self):
        extraction = {"search_queries": [{"query": "q1", "category": "c", "rationale": "r"}]}
        with patch("doesitstand.review_pipeline.search_cached", return_value=[_entry("1234.5678")]):
            out = run_arxiv_grounding(extraction, no_cache=True)
        self.assertEqual(out["queries_run"][0]["source"], "arxiv")

    def test_grounding_marks_openalex_fallback(self):
        extraction = {"search_queries": [{"query": "q1", "category": "c", "rationale": "r"}]}
        with patch("doesitstand.review_pipeline.search_cached", side_effect=RuntimeError("429")):
            with patch("doesitstand.review_pipeline.search_by_query_cached", return_value=[_entry("2345.6789")]):
                out = run_arxiv_grounding(extraction, no_cache=True)
        self.assertEqual(out["queries_run"][0]["source"], "openalex_fallback")
        self.assertGreaterEqual(out["unique_results_count"], 1)

    def test_grounding_marks_none_when_all_fail(self):
        extraction = {"search_queries": [{"query": "q1", "category": "c", "rationale": "r"}]}
        with patch("doesitstand.review_pipeline.search_cached", side_effect=RuntimeError("429")):
            with patch("doesitstand.review_pipeline.search_by_query_cached", side_effect=RuntimeError("timeout")):
                out = run_arxiv_grounding(extraction, no_cache=True)
        self.assertEqual(out["queries_run"][0]["source"], "none")
        self.assertEqual(out["unique_results_count"], 0)

    def test_arxiv_cache_corruption_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            key_file = cache_dir / "f00.json"
            key_file.write_text("{not-json")
            with patch("doesitstand.arxiv_client.hashlib.sha256") as sha:
                sha.return_value.hexdigest.return_value = "f00"
                with patch("doesitstand.arxiv_client.search", return_value=[_entry("1111.1111")]):
                    out = search_cached("q", cache_dir=cache_dir, no_cache=False)
            self.assertEqual(len(out), 1)

    def test_openalex_cache_corruption_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            key = "abc"
            (cache_dir / f"{key}.json").write_text("{not-json")
            with patch("doesitstand.openalex_client.hashlib.sha256") as sha:
                sha.return_value.hexdigest.return_value = key
                with patch("doesitstand.openalex_client.fetch_by_arxiv_id", return_value=_entry("2222.2222")):
                    out = fetch_by_arxiv_id_cached("2222.2222", cache_dir=cache_dir, no_cache=False)
            self.assertIsNotNone(out)

    def test_openalex_search_cache_corruption_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            key = "def"
            (cache_dir / f"{key}.json").write_text("{not-json")
            with patch("doesitstand.openalex_client.hashlib.sha256") as sha:
                sha.return_value.hexdigest.return_value = key
                with patch("doesitstand.openalex_client.search_by_query", return_value=[_entry("3333.3333")]):
                    out = search_by_query_cached("q", cache_dir=cache_dir, no_cache=False)
            self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()

# DoesItStand

**"Does your paper stand?"** — Submit any paper. Get expert-level peer review.

A peer review system powered by Gemini that analyzes scientific papers, checks integrity, and plans follow-up research.

## Brand

- **Master brand:** DoesItStand
- **Pattern:** DoesIt[Verb] (DoesItClick, DoesItHold, DoesItStand)
- **One-liner:** "Submit any paper. Get expert-level peer review."

## Installation

```bash
git clone https://github.com/your-org/doesitstand.git
cd doesitstand
python3 -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate.fish on some systems
pip install -e .
```

**Requirements:**
- Python 3.11+
- Gemini API key (set in `.env` as `GEMINI_API_KEY`)
- Optional: `rg` (ripgrep) for faster LaTeX validation

## Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-pro          # for long-output tasks (default)
GEMINI_MODEL_FLASH=gemini-2.5-flash   # for extraction (default)
GEMINI_TEMPERATURE=0.2
ARXIV_BASE_URL=http://export.arxiv.org/api/query
```

## Commands

### `review` — Peer Review Pipeline

Run full peer review on a PDF paper.

```bash
doesitstand review paper.pdf --outdir ./output
doesitstand review paper.pdf --venue ICLR --seed 42
doesitstand review paper.pdf --grounding-arxiv-timeout 8 --grounding-openalex-timeout 8
```

**Output:**
- `review.md` — Expert meta-review with strengths, weaknesses, actionable next steps
- `evidence.json` — Full extraction, ArXiv grounding, reviewer notes, meta-review, agreement metrics, cost data, and score confidence intervals

**Extraction features:**
- **Section-aware extraction** — the PDF is split into named sections via header detection (e.g. "3 Framework", "6 Results"). Each reviewer receives the sections most relevant to their focus area: Reviewer A (Methods & Claims) gets framework/system sections; Reviewer B (Experiments) gets setup/results sections; Reviewer C (Clarity) gets intro/discussion/conclusion. Falls back to sandwich excerpt when section detection fails.
- **Sandwich excerpt** — for the extraction stage, uses the first 15k chars (intro/method) plus the last 5k chars (limitations/conclusions/references) of the PDF text.
- **`acknowledged_limitations`** — the extraction schema includes a field for up to 8 scope boundaries or threats-to-validity that the authors themselves declare. Reviewers are instructed to check this field before listing something as a weakness.

**Review metrics (new in evidence.json):**
- `reviewer_agreement` — pairwise Jaccard similarity between reviewer outputs, measuring topical overlap.
- `cost` — per-stage token usage and estimated USD cost (based on Gemini 2.5 pricing).
- `score_confidence_intervals` — *(backlog)* bootstrap 95% CIs for each score dimension. Requires calibration dataset (n≥20 papers with human scores) to produce meaningful intervals. The `stats` module is ready for future use.

---

### `guard` — LaTeX Structural Validation

Validate LaTeX submission structure: labels, figures, logs, policy signals.

```bash
doesitstand guard ./paper_dir
doesitstand guard ./paper_dir --policy-strict --outdir ./output
doesitstand guard ./paper_dir --policy-profile profiles/tmlr.json --outdir ./output
```

**Checks:**
- All `\label{tab:*}`, `\label{fig:*}`, `\label{sec:*}`, `\label{eq:*}` have references
- All `\includegraphics` targets exist on disk
- Build logs have no undefined reference patterns
- Policy signals present: data/code availability, limitations, ethics, reproducibility

**Venue profiles (`--policy-profile`):**

Pass a JSON profile to add venue-specific policy signals on top of the built-in defaults.

```json
{
  "signals": [
    {"id": "code_url",  "name": "Code URL present",    "regex": "github\\.com|gitlab\\.com|zenodo"},
    {"id": "ai_tools",  "name": "AI tools disclosure",  "regex": "AI tools disclosure|generative.AI"}
  ]
}
```

A TMLR-specific profile is included at `doesitstand/profiles/tmlr.json`.

**Output:** `guard_report.json`

---

### `ref-check` — BibTeX Validation

Validate BibTeX consistency: duplicate keys, unused references, undefined citations.

```bash
doesitstand ref-check references.bib main.tex --outdir ./output
doesitstand ref-check references.bib sections/ appendix/
```

**Checks:**
- Duplicate BibTeX keys
- Duplicate titles
- References in `.bib` but never cited in `.tex`
- Citations in `.tex` but missing from `.bib`
- Citation frequency analysis

**Output:** `ref_check_report.json`

---

### `integrity` — Integrity Checks

Run integrity checks on a reviewed paper.

```bash
doesitstand integrity paper.pdf --evidence evidence.json --outdir ./output
```

**Checks:**
- Reference resolution (OpenAlex by arXiv DOI, with ArXiv API fallback)
- Hallucination detection (are cited papers real?)
- Claim verification (do claims match the evidence?)

**Output:** `reference_check_report.json`, `hallucination_report.json`, `claim_verification_report.json`

**Reference resolution behavior:**
- Tries OpenAlex first (`10.48550/arXiv.<id>`) to reduce dependency on ArXiv API throttling.
- Falls back to ArXiv API when OpenAlex has no result or fails.
- Uses provider-specific caches under `outdir/.cache/openalex` and `outdir/.cache/arxiv`.

**Grounding behavior (review stage):**
- Primary source: ArXiv query API.
- Fallback source: OpenAlex query search when ArXiv fails (timeout/rate limit).
- Each query record in `evidence.json.grounding.queries_run` includes `source` (`arxiv`, `openalex_fallback`, or `none`).
- Tuning knobs: `--grounding-max-results`, `--grounding-arxiv-timeout`, `--grounding-arxiv-retries`, `--grounding-openalex-timeout`, `--grounding-openalex-retries`.

---

### `science` — Science Planning

Plan follow-up research based on paper analysis.

```bash
doesitstand science evidence.json --outdir ./output
```

**Stages:**
- Build dossier (consolidate paper facts)
- Generate hypotheses
- Rank by feasibility/impact
- Create minimal test plan

**ArXiv grounding:** related-work candidates are filtered to a domain-relevant allowlist (`cs.AI`, `cs.CL`, `cs.IR`, `cs.LG`, `cs.SE`, `stat.ML`, and related sub-categories), excluding off-domain results (physics, pure mathematics, etc.).

**Output:** `dossier.json`, `hypothesis_backlog.jsonl`, `hypotheses_ranked.json`, `test_plan.yaml`

---

### `agenda` — Research Agenda

Aggregate hypotheses from multiple paper runs into a research agenda.

```bash
doesitstand agenda run1/ run2/ run3/ --outdir ./output
```

**Output:** `research_agenda.json`

---

### `screen` — Hypothesis Screening

Screen hypotheses in an agenda and produce a portfolio.

```bash
doesitstand screen agenda.json --outdir ./output
doesitstand screen agenda.json --use-llm --outdir ./output
```

**Output:** `portfolio.json`, `screening_report.json`

---

### `e2e` — End-to-End Pipeline

Run the complete pipeline: (guard) → review → integrity → science → (optional) agenda + screening.

```bash
doesitstand e2e paper.pdf --outdir ./output
doesitstand e2e paper.pdf --no-integrity --no-science
doesitstand e2e paper.pdf --runs-dir other_run/ --outdir ./output

# Include LaTeX guard checks (Stage 0) before review:
doesitstand e2e paper.pdf --paper-dir ./paper --outdir ./output
doesitstand e2e paper.pdf --paper-dir ./paper --policy-profile profiles/tmlr.json --outdir ./output
```

**Stages:**
- **Stage 0** (guard, optional) — LaTeX structural checks run first when `--paper-dir` is provided. Results are saved to `guard_report.json` and the pipeline continues regardless of guard outcome.
- **Stage 1** (review) — extraction, ArXiv grounding, three reviewers, meta-review.
- **Stage 2** (integrity, `--no-integrity` to skip) — reference resolution, hallucination detection, claim verification.
- **Stage 3** (science, `--no-science` to skip) — dossier, hypotheses, ranking, test plan.
- **Stage 4** (agenda + screening, triggered by `--runs-dir`) — multi-paper research agenda.

## Reliability

The review pipeline includes several robustness features:

- **LLM retry with exponential backoff** — transient API errors (429 rate limits, 500 server errors, timeouts) are retried up to 3 times with delays of 2s → 4s → 8s. Non-retryable errors (malformed output) fail immediately.
- **Error isolation gate** — if any reviewer fails after retries, its output is flagged as an error. The meta-reviewer receives the `reviewer_errors` list and `final_confidence` is capped at 3/5, preventing overconfident assessments when reviewer perspectives are missing.
- **Cost tracking** — every LLM call is instrumented with token counts and estimated USD cost. The `cost` field in `evidence.json` breaks down usage per pipeline stage (extraction, reviewer_a/b/c, meta_review).
- **Cross-process ArXiv throttling** — ArXiv lookups use a file lock and shared timestamp gate to keep requests near `1 req / 5s` across concurrent local processes.

## Project Structure

```
doesitstand/
├── __init__.py
├── cli.py              # CLI entry point
├── env.py              # Environment variables
├── llm_client.py       # Gemini API client (flash/pro routing, retry, cost tracking)
├── pdf_extract.py      # PDF text extraction (sandwich + section-aware)
├── prompts.py          # Review prompt templates
├── review_pipeline.py  # Core review pipeline (agreement, error isolation)
├── stats.py            # Bootstrap confidence intervals
├── guard.py            # LaTeX structural validation
├── ref_check.py        # BibTeX validation
├── science_prompts.py
├── screen_prompts.py
├── agenda_prompts.py
├── arxiv_client.py     # ArXiv API client + cross-process rate limiting
├── openalex_client.py  # OpenAlex resolver by arXiv DOI
├── reference_resolver.py # OpenAlex -> ArXiv fallback resolver
├── contracts/          # JSON schemas
│   └── __init__.py
├── profiles/           # Venue-specific policy signal profiles
│   └── tmlr.json       # TMLR submission profile
├── integrity/          # Integrity checks
│   ├── reference_check.py
│   ├── hallucination_check.py
│   └── claim_verification.py
├── science/            # Science planning
│   ├── dossier.py
│   ├── hypotheses.py
│   ├── ranking.py
│   └── test_plan.py
├── agenda/             # Research agenda
│   └── agenda.py
└── screening/          # Hypothesis screening
    └── screen.py
```

## Models

- **Extraction:** `gemini-2.5-flash` (fast, cost-effective for short outputs)
- **Reviews/Meta-review/Science:** `gemini-2.5-pro` (better for long-form outputs)

Override via environment:
```env
GEMINI_MODEL_FLASH=gemini-2.5-flash
GEMINI_MODEL=gemini-2.5-pro
```

## License

MIT

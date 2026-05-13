"""Science prompts v2 — transcribed from docs/pseudocode.md"""

SCIENCE_PROMPTS = {
    "v2": {
        "hypothesis_miner": {
            "system": (
                "You are a research planning assistant. Your goal is to propose falsifiable "
                "hypotheses and minimal tests. You MUST ground each hypothesis in the provided "
                "dossier (claims/citations). Return ONLY valid JSON."
            ),
            "user": (
                "Given the paper dossier (structured evidence), produce 5-10 candidate hypotheses "
                "for follow-up research.\n"
                "\n"
                "Constraints:\n"
                "- Each hypothesis must be falsifiable and operationalized.\n"
                "- Include at least 2 evidence links per hypothesis, pointing to claim indices "
                "and/or cited arXiv ids.\n"
                "- Include explicit falsification tests (minimal experiments/analyses).\n"
                "- Include explicit measurable metrics (name + unit).\n"
                "- Do NOT propose actions that require external tools (web browsing, emailing "
                "authors, wet-lab experiments).\n"
                "\n"
                "Output JSON schema (ALL fields required in each hypothesis):\n"
                "{{\n"
                '  "hypotheses": [\n'
                "    {{\n"
                '      "hypothesis_version": "v2",\n'
                '      "statement": string,\n'
                '      "rationale": string,\n'
                '      "predictions": [string],\n'
                '      "falsification_tests": [string],\n'
                '      "metrics": [{{"name": string, "unit": string, "direction": '
                '"increase"|"decrease"|"no_change"|"unknown", "baseline": string|number|null}}],\n'
                '      "operationalization": string,\n'
                '      "minimal_test": string,\n'
                '      "falsifier": string,\n'
                '      "assumptions": [string],\n'
                '      "dataset_or_source": string,\n'
                '      "evidence_links": [\n'
                '        {{"kind": "claim", "index": number}} OR {{"kind": "citation", "arxiv_id": string}}\n'
                "      ],\n"
                '      "novelty_flags": {{"likely_known": true|false, "related_arxiv_ids": [string]}},\n'
                '      "feasibility": {{"estimated_days": number, "requirements": [string], "risks": [string]}}\n'
                "    }}\n"
                "  ]\n"
                "}}\n"
                "\n"
                "Paper dossier JSON:\n"
                "{dossier_json}"
            ),
        },
        "hypothesis_ranker": {
            "system": (
                "You are a pragmatic research lead. You will rank candidate hypotheses for "
                "follow-up work. Prioritize: (1) falsifiability, (2) feasibility under tight "
                "budget, (3) expected impact/insight, (4) novelty relative to provided "
                "citations, (5) auditability (clear measurable outcomes). Return ONLY valid JSON."
            ),
            "user": (
                "Given a paper dossier and a list of candidate hypotheses, produce a ranking.\n"
                "\n"
                "Constraints:\n"
                "- Rank must include only provided hypothesis_ids (no new ones).\n"
                "- No duplicates.\n"
                "- Provide a short justification per ranked hypothesis.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "ranking": [\n'
                '    {{"hypothesis_id": string, "rank": number, "score": number, "why": string}}\n'
                "  ]\n"
                "}}\n"
                "\n"
                "Paper dossier JSON:\n"
                "{dossier_json}\n"
                "\n"
                "Candidate hypotheses JSON:\n"
                "{hypotheses_json}"
            ),
        },
        "test_plan_writer": {
            "system": (
                "You are a meticulous experiment designer. You will write a minimal test plan "
                "for a single hypothesis. Return ONLY valid JSON."
            ),
            "user": (
                "Given a paper dossier and a selected hypothesis, write a minimal test plan in YAML.\n"
                "\n"
                "Constraints:\n"
                "- Keep it minimal and actionable.\n"
                "- Include baselines/ablations if applicable.\n"
                "- Include explicit acceptance criteria and stop conditions.\n"
                "- Do NOT require external tools or internet access.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "test_plan_yaml": string\n'
                "}}\n"
                "\n"
                "Paper dossier JSON:\n"
                "{dossier_json}\n"
                "\n"
                "Selected hypothesis JSON:\n"
                "{hypothesis_json}"
            ),
        },
    }
}


def get_science_prompt(stage: str, version: str = "v2") -> dict:
    return SCIENCE_PROMPTS[version][stage]

"""Prompts v3 — transcribed from docs/pseudocode.md"""

PROMPTS = {
    "v3": {
        "config": {
            "context_limit": 20000,
            "excerpt_strategy": "section_aware_v2",
            "treat_recent_preprints_as_concurrent": True,
        },
        "extraction": {
            "system": (
                "You are a senior research assistant. Extract structured facts and generate "
                "literature search queries. Return ONLY valid JSON."
            ),
            "user": (
                "Given the paper text excerpt, do the following:\n"
                "1) Decide if it looks like an academic paper (boolean).\n"
                "2) Extract title (best effort), a 3-6 sentence summary, keywords (5-10), and 3-5 main "
                "contributions/claims.\n"
                "3) Extract up to 8 acknowledged limitations — scope boundaries, threats to validity, "
                "or future work items that the authors themselves declare (e.g. 'single provider', "
                "'English only', 'no human study'). Use short phrases, not full sentences.\n"
                "4) Generate up to 4 web search queries targeting arXiv results, with mixed "
                "specificity. Cover: (a) baselines/benchmarks, (b) similar problem papers, (c) similar "
                "techniques. Avoid near-duplicates.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "is_academic_paper": true|false,\n'
                '  "title": string,\n'
                '  "summary": string,\n'
                '  "keywords": [string],\n'
                '  "claims": [string],\n'
                '  "acknowledged_limitations": [string],\n'
                '  "search_queries": [\n'
                '     {{"query": string, "category": '
                '"baseline"|"benchmark"|"problem"|"technique"|"related", "rationale": string, '
                '"filter_keywords": [string] (optional)}}\n'
                "  ]\n"
                "}}\n"
                "\n"
                "Venue (optional): {venue}\n"
                "\n"
                "Paper text excerpt:\n"
                "{head_text}"
            ),
        },
        "reviewer_a": {
            "system": (
                "You are a peer reviewer focusing on Methods & Claims. You focus on problem "
                "formulation, assumptions, correctness, and claim support. Be constructive "
                "but critical. Avoid vague statements. Do not invent missing details; if "
                "uncertain, say so. Ground novelty/prior-work claims ONLY in the provided "
                "grounding digest; if grounding is thin, say so. Return ONLY valid JSON."
            ),
            "user": (
                "Write a structured peer review in Markdown focusing on methods/claims.\n"
                "Do NOT output numeric scores or an accept/reject decision in this step.\n"
                "\n"
                "IMPORTANT: Treat preprints (arXiv) published within the last 6 months as "
                "'concurrent work' rather than 'prior work' that invalidates novelty.\n"
                "\n"
                "IMPORTANT: Before listing something under Weaknesses, check "
                "`extraction.acknowledged_limitations`. If the issue is already explicitly "
                "declared by the authors as a scope boundary or threat to validity, do NOT "
                "list it as a weakness — it is a declared limitation. You may note it "
                "briefly under a 'Limitations Already Acknowledged' subsection if it "
                "affects your assessment, but it should not count against the paper.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "review_markdown": string\n'
                "}}\n"
                "\n"
                "Include sections: Summary, Strengths, Weaknesses, Questions.\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Paper text excerpt (for details; do NOT invent missing info):\n"
                "{head_text}"
            ),
        },
        "reviewer_b": {
            "system": (
                "You are a peer reviewer focusing on Experiments & Reproducibility. You "
                "focus on empirical validation, baselines, ablations, metrics, statistical "
                "rigor, and reproducibility. Be constructive but critical. Avoid vague "
                "statements. Do not invent missing details; if uncertain, say so. Ground "
                "novelty/prior-work claims ONLY in the provided grounding digest; if "
                "grounding is thin, say so. Return ONLY valid JSON."
            ),
            "user": (
                "Write a structured peer review in Markdown focusing on "
                "experiments/reproducibility.\n"
                "Do NOT output numeric scores or an accept/reject decision in this step.\n"
                "\n"
                "IMPORTANT: Treat preprints (arXiv) published within the last 6 months as "
                "'concurrent work' rather than 'prior work' that invalidates novelty.\n"
                "\n"
                "IMPORTANT: Before listing something under Weaknesses, check "
                "`extraction.acknowledged_limitations`. If the issue is already explicitly "
                "declared by the authors as a scope boundary or threat to validity, do NOT "
                "list it as a weakness — it is a declared limitation. You may note it "
                "briefly under a 'Limitations Already Acknowledged' subsection if it "
                "affects your assessment, but it should not count against the paper.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "review_markdown": string\n'
                "}}\n"
                "\n"
                "Include sections: Summary, Strengths, Weaknesses, Questions.\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Paper text excerpt (for details; do NOT invent missing info):\n"
                "{head_text}"
            ),
        },
        "reviewer_c": {
            "system": (
                "You are a peer reviewer focusing on Clarity & Impact. You focus on writing "
                "quality, structure, limitations, missing details, broader impacts, and "
                "ethics/safety considerations. Be constructive but critical. Avoid vague "
                "statements. Do not invent missing details; if uncertain, say so. Ground "
                "novelty/prior-work claims ONLY in the provided grounding digest; if "
                "grounding is thin, say so. Return ONLY valid JSON."
            ),
            "user": (
                "Write a structured peer review in Markdown focusing on clarity, limitations, "
                "and broader impact.\n"
                "Do NOT output numeric scores or an accept/reject decision in this step.\n"
                "\n"
                "IMPORTANT: Treat preprints (arXiv) published within the last 6 months as "
                "'concurrent work' rather than 'prior work' that invalidates novelty.\n"
                "\n"
                "IMPORTANT: Before listing something under Weaknesses, check "
                "`extraction.acknowledged_limitations`. If the issue is already explicitly "
                "declared by the authors as a scope boundary or threat to validity, do NOT "
                "list it as a weakness — it is a declared limitation. You may note it "
                "briefly under a 'Limitations Already Acknowledged' subsection if it "
                "affects your assessment, but it should not count against the paper.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "review_markdown": string\n'
                "}}\n"
                "\n"
                "Include sections: Summary, Strengths, Weaknesses, Questions.\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Paper text excerpt (for details; do NOT invent missing info):\n"
                "{head_text}"
            ),
        },
        "meta_write": {
            "system": (
                "You are an Area Chair (AC) for a top AI venue. You have received multiple "
                "independent reviews for a single paper. Your task is to synthesize them "
                "into a fair, evidence-based meta-review. Treat the reviews as arguments "
                "that may contain mistakes; arbitrate using the paper facts and grounding "
                "evidence. Return ONLY valid JSON."
            ),
            "user": (
                "You will write the meta-review text FIRST, without deciding numeric scores yet.\n"
                "\n"
                "Reviews (independent):\n"
                "\n"
                "Review (Methods & Claims):\n"
                "{review_a}\n"
                "\n"
                "Review (Experiments & Reproducibility):\n"
                "{review_b}\n"
                "\n"
                "Review (Clarity & Impact):\n"
                "{review_c}\n"
                "\n"
                "Meta-review protocol:\n"
                "1) List consensus points.\n"
                "2) List conflicts/disagreements.\n"
                "3) For each conflict, explain which side is better supported by evidence "
                "(paper facts + grounding).\n"
                "4) If evidence is insufficient, explicitly state what missing "
                "information/experiment would resolve it.\n"
                "5) Produce a final meta-review in Markdown that is constructive and actionable.\n"
                "\n"
                "IMPORTANT constraints:\n"
                "- Do NOT invent details not present in the paper excerpt or extracted facts.\n"
                "- Use the grounding digest for novelty/prior-work statements; if grounding is thin, say so.\n"
                "- Be tolerant of concurrent work (preprints < 6 months old). Do not reject solely "
                "based on recent arXiv overlap unless it is the exact same paper.\n"
                "- Do NOT output an accept/reject decision or numeric scores in this step.\n"
                "- DECLARED LIMITATIONS: Check `extraction.acknowledged_limitations`. Any weakness "
                "raised by a reviewer that matches a declared limitation is NOT a weakness — the "
                "authors already know and scoped it. In the final Weaknesses section, list only "
                "issues NOT already acknowledged. Reviewers who raised declared limitations as "
                "weaknesses should be noted as overreaching in your resolution_rationale.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "consensus_points": [string],\n'
                '  "conflicts": [string],\n'
                '  "resolution_rationale": string,\n'
                '  "final_review_markdown": string\n'
                "}}\n"
                "\n"
                "The markdown MUST include these sections:\n"
                "1) Summary of Contributions\n"
                "2) Strengths\n"
                "3) Weaknesses\n"
                "4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n"
                "5) Questions / Required Clarifications\n"
                "6) Actionable Next Steps (bulleted, prioritized)\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}"
            ),
        },
        "meta_score": {
            "system": (
                "You are an Area Chair (AC) making a final recommendation for a top AI "
                "venue. You will assign a decision, confidence, and scores AFTER reading "
                "the completed meta-review text. Return ONLY valid JSON."
            ),
            "user": (
                "Given the meta-review (text already written) and the underlying evidence, "
                "assign a final decision and rubric scores.\n"
                "\n"
                "Decision rubric (keep it simple and consistent):\n"
                "- Reject if there is a plausible fatal flaw invalidating core claims.\n"
                "- Weak Reject if evidence is insufficient for claims or key "
                "baselines/ablations are missing.\n"
                "- Borderline if the paper is promising but uncertain; specify what would "
                "change the decision.\n"
                "- Weak Accept/Accept/Strong Accept only if claims are supported and "
                "contribution is clear.\n"
                "\n"
                "IMPORTANT constraints:\n"
                "- Do not rewrite the meta-review text. Only output scores/decision/confidence.\n"
                "- If grounding evidence is thin, reflect that uncertainty in confidence/decision.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "final_decision": "Strong Accept"|"Accept"|"Weak Accept"|"Borderline"|"Weak Reject"|"Reject"|"Strong Reject",\n'
                '  "final_confidence": 1|2|3|4|5,\n'
                '  "final_scores": {{"originality": 1-10, "quality": 1-10, "clarity": 1-10, '
                '"significance": 1-10, "reproducibility": 1-10, "overall": 1-10}}\n'
                "}}\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Meta-review markdown (already written):\n"
                "{meta_review_md}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Reviewer (Methods) JSON: {review_a}\n"
                "\n"
                "Reviewer (Experiments) JSON: {review_b}\n"
                "\n"
                "Reviewer (Clarity & Impact) JSON: {review_c}"
            ),
        },
        "meta_combined": {
            "system": (
                "You are an Area Chair (AC) for a top AI venue. You have received "
                "multiple independent reviews for a single paper. Your task is to "
                "synthesize them into a fair, evidence-based meta-review AND assign "
                "final scores/decision in the same response. This is an ablation where "
                "write-then-score is disabled. Treat the reviews as arguments that may "
                "contain mistakes; arbitrate using the paper facts and grounding "
                "evidence. Return ONLY valid JSON."
            ),
            "user": (
                "You will write the meta-review AND assign final decision/scores in one step.\n"
                "\n"
                "Reviews (independent):\n"
                "\n"
                "Review (Methods & Claims):\n"
                "{review_a}\n"
                "\n"
                "Review (Experiments & Reproducibility):\n"
                "{review_b}\n"
                "\n"
                "Review (Clarity & Impact):\n"
                "{review_c}\n"
                "\n"
                "Meta-review protocol:\n"
                "1) List consensus points.\n"
                "2) List conflicts/disagreements.\n"
                "3) For each conflict, explain which side is better supported by evidence "
                "(paper facts + grounding).\n"
                "4) If evidence is insufficient, explicitly state what missing "
                "information/experiment would resolve it.\n"
                "5) Produce a final meta-review in Markdown that is constructive and actionable.\n"
                "\n"
                "IMPORTANT constraints:\n"
                "- Do NOT invent details not present in the paper excerpt or extracted facts.\n"
                "- Use the grounding digest for novelty/prior-work statements; if grounding is "
                "thin, say so.\n"
                "- Be tolerant of concurrent work (preprints < 6 months old). Do not "
                "reject solely based on recent arXiv overlap unless it is the exact same paper.\n"
                "- DECLARED LIMITATIONS: Check `extraction.acknowledged_limitations`. Any weakness "
                "that matches a declared limitation is NOT a weakness — the authors already scoped "
                "it. List only issues NOT already acknowledged under Weaknesses.\n"
                "\n"
                "Decision rubric (keep it simple and consistent):\n"
                "- Reject if there is a plausible fatal flaw invalidating core claims.\n"
                "- Weak Reject if evidence is insufficient for claims or key "
                "baselines/ablations are missing.\n"
                "- Borderline if the paper is promising but uncertain; specify what would "
                "change the decision.\n"
                "- Weak Accept/Accept/Strong Accept only if claims are supported and "
                "contribution is clear.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "consensus_points": [string],\n'
                '  "conflicts": [string],\n'
                '  "resolution_rationale": string,\n'
                '  "final_review_markdown": string,\n'
                '  "final_decision": "Strong Accept"|"Accept"|"Weak Accept"|"Borderline"|"Weak Reject"|"Reject"|"Strong Reject",\n'
                '  "final_confidence": 1|2|3|4|5,\n'
                '  "final_scores": {{"originality": 1-10, "quality": 1-10, "clarity": 1-10, '
                '"significance": 1-10, "reproducibility": 1-10, "overall": 1-10}}\n'
                "}}\n"
                "\n"
                "The markdown MUST include these sections:\n"
                "1) Summary of Contributions\n"
                "2) Strengths\n"
                "3) Weaknesses\n"
                "4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n"
                "5) Questions / Required Clarifications\n"
                "6) Actionable Next Steps (bulleted, prioritized)\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Reviewer (Methods) JSON: {review_a}\n"
                "\n"
                "Reviewer (Experiments) JSON: {review_b}\n"
                "\n"
                "Reviewer (Clarity & Impact) JSON: {review_c}"
            ),
        },
        "review": {
            "system": (
                "You are an expert peer reviewer. Your goal is to provide a balanced and fair review. Be "
                "specific about strengths and weaknesses; avoid vague statements. Do not invent missing "
                "details; if unsure, say so. Ground novelty/prior-work claims ONLY in the provided "
                "grounding digest; if grounding is thin, say so. Return ONLY valid JSON."
            ),
            "user": (
                "Write the peer review text in Markdown. Do NOT output numeric scores, confidence, or an "
                "accept/reject decision yet.\n"
                "\n"
                "IMPORTANT: Treat preprints (arXiv) published within the last 6 months as 'concurrent work' "
                "rather than 'prior work' that invalidates novelty.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "review_markdown": string\n'
                "}}\n"
                "\n"
                "The markdown MUST include these sections:\n"
                "1) Summary of Contributions\n"
                "2) Strengths\n"
                "3) Weaknesses\n"
                "4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n"
                "5) Questions / Required Clarifications\n"
                "6) Actionable Next Steps (bulleted, prioritized)\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}\n"
                "\n"
                "Paper text excerpt (for details; do NOT invent missing info):\n"
                "{head_text}"
            ),
        },
        "scoring": {
            "system": (
                "You are an expert peer reviewer assigning a final decision, confidence, and rubric "
                "scores AFTER reading the completed review text. Return ONLY valid JSON."
            ),
            "user": (
                "Given the review markdown and the underlying evidence, assign a final decision, "
                "confidence, and rubric scores.\n"
                "\n"
                "Decision rubric (keep it simple and consistent):\n"
                "- Reject if there is a plausible fatal flaw invalidating core claims.\n"
                "- Weak Reject if evidence is insufficient for claims or key baselines/ablations are missing.\n"
                "- Borderline if promising but uncertain; specify what would change the decision.\n"
                "- Weak Accept/Accept/Strong Accept only if claims are supported and contribution is clear.\n"
                "\n"
                "IMPORTANT constraints:\n"
                "- Do not rewrite the review text. Only output scores/decision/confidence.\n"
                "- If grounding evidence is thin, reflect that uncertainty in confidence/decision.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "decision": "Strong Accept"|"Accept"|"Weak Accept"|"Borderline"|"Weak Reject"|"Reject"|"Strong Reject",\n'
                '  "confidence": 1|2|3|4|5,\n'
                '  "scores": {{\n'
                '     "originality": 1-10,\n'
                '     "quality": 1-10,\n'
                '     "clarity": 1-10,\n'
                '     "significance": 1-10,\n'
                '     "reproducibility": 1-10,\n'
                '     "overall": 1-10\n'
                "  }}\n"
                "}}\n"
                "\n"
                "Target venue style (optional): {venue}\n"
                "\n"
                "Review markdown (already written):\n"
                "{review_md}\n"
                "\n"
                "Paper extracted facts (JSON): {extraction}\n"
                "\n"
                "Grounding digest (JSON): {grounding}"
            ),
        },
    }
}


def get_prompt(stage: str, version: str = "v3") -> dict:
    return PROMPTS[version][stage]

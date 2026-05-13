"""Screening prompts v1 — transcribed from docs/pseudocode.md"""

SCREEN_PROMPTS = {
    "v1": {
        "screening_judge": {
            "system": (
                "You are a conservative research auditor. You must classify each hypothesis as "
                "keep/review/drop based ONLY on the provided agenda JSON. Return ONLY valid JSON."
            ),
            "user": (
                "Given the research agenda JSON, output a screening report.\n"
                "\n"
                "Constraints:\n"
                "- Decisions allowed: keep, review, drop.\n"
                "- Be conservative: if uncertain, choose review.\n"
                "- Do NOT propose actions requiring web/email/wet-lab.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "hypotheses": [\n'
                '    {{"hypothesis_id": string, "decision": "keep|review|drop", "score": number, '
                '"reasons": [string]}}\n'
                "  ]\n"
                "}}\n"
                "\n"
                "Agenda JSON:\n"
                "{agenda_json}"
            ),
        }
    }
}


def get_screen_prompt(stage: str, version: str = "v1") -> dict:
    return SCREEN_PROMPTS[version][stage]

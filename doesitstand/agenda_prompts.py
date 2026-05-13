"""Agenda prompts v1 — transcribed from docs/pseudocode.md"""

AGENDA_PROMPTS = {
    "v1": {
        "agenda_summarizer": {
            "system": (
                "You are a research program lead. Your task is to summarize a multi-paper "
                "hypothesis agenda into a concise set of research directions and questions. "
                "You MUST stay grounded to the provided agenda JSON. Return ONLY valid JSON."
            ),
            "user": (
                "Given a research agenda (hypotheses grouped into clusters), provide a short "
                "program-level summary.\n"
                "\n"
                "Constraints:\n"
                "- Do NOT propose actions that require external tools (web browsing, emailing, wet-lab).\n"
                "- Keep it short and pragmatic.\n"
                "\n"
                "Output JSON schema:\n"
                "{{\n"
                '  "program_summary": string,\n'
                '  "research_questions": [string],\n'
                '  "top_clusters": [{{"cluster_id": string, "why": string}}]\n'
                "}}\n"
                "\n"
                "Agenda JSON:\n"
                "{agenda_json}"
            ),
        }
    }
}


def get_agenda_prompt(stage: str, version: str = "v1") -> dict:
    return AGENDA_PROMPTS[version][stage]

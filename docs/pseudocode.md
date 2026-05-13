# Pseudo-codigo de reconstrucao (sem reuso)
Este documento descreve **como reconstruir do zero** um sistema equivalente ao `paperreview_single.py`, **sem embutir nem reutilizar** o pacote original. A ideia aqui e reimplementar a logica e a arquitetura, criando novos modulos e um CLI proprio.
## Objetivo
- Processar um paper PDF em etapas: - Review (gera `review.md` + `evidence.json`) - Integrity checks (references, claims, hallucinations) - Science planning (dossie, hipoteses, ranking, test plan) - Agenda + Screening (opcional, para multiplos runs)- Entregar em um unico executavel (pode ser um script unico **ou** um pacote com CLI).
## Arquitetura (reconstrucao do zero)
### 1) Estrutura de pastas (sugestao)
```textpaperreview_new/ app/ __init__.py cli.py env.py logging_utils.py http_utils.py cache_utils.py pdf_extract.py llm_client.py prompts.py review_pipeline.py integrity/ reference_check.py hallucination_check.py claim_verification.py science/ dossier.py hypotheses.py ranking.py test_plan.py agenda/ agenda.py screening/ screen.py contracts/ evidence.v1.schema.json reference_check_report.v1.schema.json ... data/ tests/```
Dica: reconstrua como pacote, depois gere um single-file se precisar.
### 2) Contratos (schemas JSON)
Defina schemas JSON para todos os artefatos principais.
Pseudo-codigo:
```textpara cada artefato (evidence, reports, dossier, agenda, portfolio): criar schema JSON em contracts/ versionar com v1, v2, ...
funcao validate_artifact(path): carregar JSON detectar schema_id validar retornar ok + erros```
### 3) Extracao de PDF
Pseudo-codigo:
```text
funcao extract_pdf_text(pdf_path):
    abrir PDF, concatenar paginas em texto, retornar texto

funcao extract_sections(text):
    detectar headers via regex (\n\d+\.?\s+[A-Z]...)
    detectar Appendix X, References
    mapear posicoes -> nomear secoes
    retornar dict {secao: texto}

funcao get_reviewer_text(sections, full_text, reviewer_key, budget=8000):
    reviewer_a: secoes de method/framework/system
    reviewer_b: secoes de setup/results
    reviewer_c: secoes de intro/discussion/conclusion
    selecionar secoes relevantes, truncar ao budget
    fallback: sandwich excerpt
```
Dicas:
- manter opcao de extracao rica (layout) se existir biblioteca extra
- section-aware extraction alimenta cada reviewer com conteudo relevante ao seu foco
- fallback para sandwich quando section detection falha

### 4) Cliente LLM
Pseudo-codigo:
```text
funcao llm_json(system_prompt, user_prompt, model, temperature, seed):
    chamar API Gemini, rastrear uso de tokens (cost tracking)
    parsear JSON, retornar objeto

funcao llm_json_with_retry(system, user, stage, max_retries=3):
    para cada tentativa (0..max_retries-1):
        try: llm_json_inner(system, user)
        except LLMParseError: raise imediatamente
        except LLMAPIError:
            se erro nao-retryavel: raise
            delay = 2 * 2^tentativa  # backoff exponencial
            log warning, sleep(delay)
    raise "retries exhausted"

funcao get_cost_report():
    agregar tokens por estagio
    multiplicar por preco por token (Flash: $0.075/$0.30, Pro: $1.25/$10.00 por 1M)
    retornar {stages: {...}, total_usd: ...}
```
Dicas:
- validar JSON contra schemas, registrar prompts com hash
- retry apenas em erros transitórios (429, 500, 503, timeout)
- cost tracking permite budget planning e comparacao com avaliacao humana

### 5) Review pipeline
Pseudo-codigo:
```text
funcao run_review(pdf_path, outdir, venue, seed):
    text = extract_pdf_text(pdf_path)
    sections = extract_sections(text)
    head_text = get_head_excerpt(text)
    sandwich = get_sandwich_excerpt(text)
    extraction = llm_json_flash(extraction_prompt, sandwich)
    grounding = run_arxiv_grounding(extraction)

    # 3 reviewers em paralelo com section-aware text
    para cada reviewer (a, b, c) em paralelo:
        reviewer_text = get_reviewer_text(sections, text, reviewer_key)
        resultado = llm_json_pro(reviewer_prompt, reviewer_text)

    # Cross-reviewer agreement (Jaccard entre topicos extraidos)
    agreement = compute_reviewer_agreement(results)

    # Error isolation gate
    reviewer_errors = checar por [ERROR:...] em cada resultado

    # Meta-review (2 steps: write then score)
    meta_write = llm_json_pro(meta_write_prompt, 3 reviews)
    meta_score = llm_json_pro(meta_score_prompt, meta_review_text)

    # Cap confidence se reviewers falharam
    se reviewer_errors: final_confidence = min(meta_score.confidence, 3)

    # Bootstrap CIs: backlog (Sprint 4) — precisa calibration dataset n≥20
    # score_cis = compute_score_cis(reviews)

    evidence = {
        ...extraction, grounding, reviews, meta_review,
        reviewer_agreement, cost: get_cost_report(),
        # score_confidence_intervals: score_cis  # Sprint 4
    }
    validar evidence contra schema
    salvar evidence.json + review.md
```
### 6) Integrity checks
Pseudo-codigo:
```textfuncao run_reference_check(pdf_path): texto = extract_pdf_text(pdf_path) extrair referencias (arxiv, doi, urls) resolver metadados gerar reference_check_report.json
funcao run_hallucination_check(pdf_path, reference_report): usar evidence + referencias gerar hallucination_report.json
funcao run_claim_verification(pdf_path, reference_report, max_claims): extrair claims do texto validar claims com LLM ou NLI local gerar claim_verification_report.json```
### 7) Science planning
Pseudo-codigo:
```textfuncao build_dossier(evidence): consolidar resumo, metodo, resultados, claims gerar paper_dossier.json
funcao generate_hypotheses(dossier): chamar LLM validar saida gerar hypothesis_backlog.jsonl
funcao rank_hypotheses(dossier, hypotheses): chamar LLM gerar hypotheses_ranked.json
funcao generate_test_plan(dossier, top_hypothesis): chamar LLM gerar test_plan.yaml
funcao run_science(evidence_path): dossier = build_dossier(evidence) hypotheses = generate_hypotheses(dossier) ranking = rank_hypotheses(dossier, hypotheses) test_plan = generate_test_plan(dossier, hypotheses[0])```
### 8) Agenda + Screening
Pseudo-codigo:
```textfuncao run_agenda(list_of_runs): agregar hypothesis_backlog.jsonl clusterizar temas gerar research_agenda.json
funcao run_screening(agenda, llm_judge=False): aplicar regras deterministicas opcional: usar LLM para julgamento gerar portfolio.json + screening_report.json```
### 9) Orquestracao (end-to-end)
Pseudo-codigo:
```textfuncao run_single_paper(pdf_path, outdir, flags): review_md, evidence = run_review(...) salvar review.md e evidence.json
 if integrity: rodar reference_check, hallucination_check, claim_verification
 if science: run_science(evidence)```
### 10) CLI

Pseudo-codigo:

```text
subcomandos:
  review, integrity, science, agenda, screen, e2e

main():
  parse args
  chamar funcoes acima
  imprimir JSON com paths gerados
```

## Dicas importantes

- Nao dependa do pacote original; reimplemente os modulos listados.
- Sempre valide saidas com JSON schema.
- Registre hashes de prompts para rastreio.
- Use seeds para reprodutibilidade.
- Salve traces por etapa para auditoria.

## Prompts originais (melhores versoes)

Abaixo estao **apenas as versoes mais recentes** de cada conjunto de prompts do script original.

**`paperreview.prompts` (v3)**
```python
PROMPTS = {
{'v3': {'config': {'context_limit': 20000,
                   'excerpt_strategy': 'section_aware_v2',
                   'treat_recent_preprints_as_concurrent': True},
        'extraction': {'system': 'You are a senior research assistant. Extract structured facts and generate '
                                 'literature search queries. Return ONLY valid JSON.',
                       'user': 'Given the paper text excerpt, do the following:\n'
                               '1) Decide if it looks like an academic paper (boolean).\n'
                               '2) Extract title (best effort), a 3-6 sentence summary, keywords (5-10), and 3-5 main '
                               'contributions/claims.\n'
                               '3) Generate up to 4 web search queries targeting arXiv results, with mixed '
                               'specificity. Cover: (a) baselines/benchmarks, (b) similar problem papers, (c) similar '
                               'techniques. Avoid near-duplicates.\n'
                               '\n'
                               'Output JSON schema:\n'
                               '{{\n'
                               '  "is_academic_paper": true|false,\n'
                               '  "title": string,\n'
                               '  "summary": string,\n'
                               '  "keywords": [string],\n'
                               '  "claims": [string],\n'
                               '  "search_queries": [\n'
                               '     {{"query": string, "category": '
                               '"baseline"|"benchmark"|"problem"|"technique"|"related", "rationale": string, '
                               '"filter_keywords": [string] (optional)}}\n'
                               '  ]\n'
                               '}}\n'
                               '\n'
                               'Venue (optional): {venue}\n'
                               '\n'
                               'Paper text excerpt:\n'
                               '{head_text}'},
        'multi': {'meta_combined': {'system': 'You are an Area Chair (AC) for a top AI venue. You have received '
                                              'multiple independent reviews for a single paper. Your task is to '
                                              'synthesize them into a fair, evidence-based meta-review AND assign '
                                              'final scores/decision in the same response. This is an ablation where '
                                              'write-then-score is disabled. Treat the reviews as arguments that may '
                                              'contain mistakes; arbitrate using the paper facts and grounding '
                                              'evidence. Return ONLY valid JSON.',
                                    'user': 'You will write the meta-review AND assign final decision/scores in one '
                                            'step.\n'
                                            '\n'
                                            'Reviews (independent):\n'
                                            '\n'
                                            'Review (Methods & Claims):\n'
                                            '{review_a}\n'
                                            '\n'
                                            'Review (Experiments & Reproducibility):\n'
                                            '{review_b}\n'
                                            '\n'
                                            'Review (Clarity & Impact):\n'
                                            '{review_c}\n'
                                            '\n'
                                            'Meta-review protocol:\n'
                                            '1) List consensus points.\n'
                                            '2) List conflicts/disagreements.\n'
                                            '3) For each conflict, explain which side is better supported by evidence '
                                            '(paper facts + grounding).\n'
                                            '4) If evidence is insufficient, explicitly state what missing '
                                            'information/experiment would resolve it.\n'
                                            '5) Produce a final meta-review in Markdown that is constructive and '
                                            'actionable.\n'
                                            '\n'
                                            'IMPORTANT constraints:\n'
                                            '- Do NOT invent details not present in the paper excerpt or extracted '
                                            'facts.\n'
                                            '- Use the grounding digest for novelty/prior-work statements; if '
                                            'grounding is thin, say so.\n'
                                            '- Be tolerant of concurrent work (preprints < 6 months old). Do not '
                                            'reject solely based on recent arXiv overlap unless it is the exact same '
                                            'paper.\n'
                                            '\n'
                                            'Decision rubric (keep it simple and consistent):\n'
                                            '- Reject if there is a plausible fatal flaw invalidating core claims.\n'
                                            '- Weak Reject if evidence is insufficient for claims or key '
                                                                                        'baselines/ablations are missing.\n'
                                            '- Borderline if the paper is promising but uncertain; specify what would '
                                            'change the decision.\n'
                                            '- Weak Accept/Accept/Strong Accept only if claims are supported and '
                                            'contribution is clear.\n'
                                            '\n'
                                            'Output JSON schema:\n'
                                            '{{\n'
                                            '  "consensus_points": [string],\n'
                                            '  "conflicts": [string],\n'
                                            '  "resolution_rationale": string,\n'
                                            '  "final_review_markdown": string,\n'
                                            '  "final_decision": "Strong Accept"|"Accept"|"Weak '
                                            'Accept"|"Borderline"|"Weak Reject"|"Reject"|"Strong Reject",\n'
                                            '  "final_confidence": 1|2|3|4|5,\n'
                                            '  "final_scores": {{"originality": 1-10, "quality": 1-10, "clarity": '
                                            '1-10, "significance": 1-10, "reproducibility": 1-10, "overall": 1-10}}\n'
                                            '}}\n'
                                            '\n'
                                            'The markdown MUST include these sections:\n'
                                            '1) Summary of Contributions\n'
                                            '2) Strengths\n'
                                            '3) Weaknesses\n'
                                            '4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n'
                                            '5) Questions / Required Clarifications\n'
                                            '6) Actionable Next Steps (bulleted, prioritized)\n'
                                            '\n'
                                            'Target venue style (optional): {venue}\n'
                                            '\n'
                                            'Paper extracted facts (JSON): {extraction}\n'
                                            '\n'
                                            'Grounding digest (JSON): {grounding}\n'
                                            '\n'
                                            'Reviewer (Methods) JSON: {review_a}\n'
                                            '\n'
                                            'Reviewer (Experiments) JSON: {review_b}\n'
                                            '\n'
                                            'Reviewer (Clarity & Impact) JSON: {review_c}'},
                  'meta_score': {'system': 'You are an Area Chair (AC) making a final recommendation for a top AI '
                                           'venue. You will assign a decision, confidence, and scores AFTER reading '
                                           'the completed meta-review text. Return ONLY valid JSON.',
                                 'user': 'Given the meta-review (text already written) and the underlying evidence, '
                                         'assign a final decision and rubric scores.\n'
                                         '\n'
                                         'Decision rubric (keep it simple and consistent):\n'
                                         '- Reject if there is a plausible fatal flaw invalidating core claims.\n'
                                         '- Weak Reject if evidence is insufficient for claims or key '
                                         'baselines/ablations are missing.\n'
                                         '- Borderline if the paper is promising but uncertain; specify what would '
                                         'change the decision.\n'
                                         '- Weak Accept/Accept/Strong Accept only if claims are supported and '
                                         'contribution is clear.\n'
                                         '\n'
                                         'IMPORTANT constraints:\n'
                                         '- Do not rewrite the meta-review text. Only output '
                                         'scores/decision/confidence.\n'
                                         '- If grounding evidence is thin, reflect that uncertainty in '
                                         'confidence/decision.\n'
                                         '\n'
                                         'Output JSON schema:\n'
                                         '{{\n'
                                         '  "final_decision": "Strong Accept"|"Accept"|"Weak '
                                         'Accept"|"Borderline"|"Weak Reject"|"Reject"|"Strong Reject",\n'
                                         '  "final_confidence": 1|2|3|4|5,\n'
                                         '  "final_scores": {{"originality": 1-10, "quality": 1-10, "clarity": 1-10, '
                                         '"significance": 1-10, "reproducibility": 1-10, "overall": 1-10}}\n'
                                         '}}\n'
                                         '\n'
                                         'Target venue style (optional): {venue}\n'
                                         '\n'
                                         'Meta-review markdown (already written):\n'
                                         '{meta_review_md}\n'
                                         '\n'
                                         'Paper extracted facts (JSON): {extraction}\n'
                                         '\n'
                                         'Grounding digest (JSON): {grounding}\n'
                                         '\n'
                                         'Reviewer (Methods) JSON: {review_a}\n'
                                         '\n'
                                         'Reviewer (Experiments) JSON: {review_b}\n'
                                         '\n'
                                         'Reviewer (Clarity & Impact) JSON: {review_c}'},
                  'meta_write': {'system': 'You are an Area Chair (AC) for a top AI venue. You have received multiple '
                                           'independent reviews for a single paper. Your task is to synthesize them '
                                           'into a fair, evidence-based meta-review. Treat the reviews as arguments '
                                           'that may contain mistakes; arbitrate using the paper facts and grounding '
                                           'evidence. Return ONLY valid JSON.',
                                 'user': 'You will write the meta-review text FIRST, without deciding numeric scores '
                                         'yet.\n'
                                         '\n'
                                         'Reviews (independent):\n'
                                         '\n'
                                         'Review (Methods & Claims):\n'
                                         '{review_a}\n'
                                         '\n'
                                         'Review (Experiments & Reproducibility):\n'
                                         '{review_b}\n'
                                         '\n'
                                         'Review (Clarity & Impact):\n'
                                         '{review_c}\n' '\n' 'Meta-review protocol:\n' '1) List consensus points.\n' '2) List conflicts/disagreements.\n' '3) For each conflict, explain which side is better supported by evidence ' '(paper facts + grounding).\n' '4) If evidence is insufficient, explicitly state what missing ' 'information/experiment would resolve it.\n' '5) Produce a final meta-review in Markdown that is constructive and ' 'actionable.\n' '\n' 'IMPORTANT constraints:\n' '- Do NOT invent details not present in the paper excerpt or extracted ' 'facts.\n' '- Use the grounding digest for novelty/prior-work statements; if grounding ' 'is thin, say so.\n' '- Be tolerant of concurrent work (preprints < 6 months old). Do not reject ' 'solely based on recent arXiv overlap unless it is the exact same paper.\n' '- Do NOT output an accept/reject decision or numeric scores in this step.\n' '\n' 'Output JSON schema:\n' '{{\n' ' "consensus_points": [string],\n' ' "conflicts": [string],\n' ' "resolution_rationale": string,\n' ' "final_review_markdown": string\n' '}}\n' '\n' 'The markdown MUST include these sections:\n' '1) Summary of Contributions\n' '2) Strengths\n' '3) Weaknesses\n' '4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n' '5) Questions / Required Clarifications\n' '6) Actionable Next Steps (bulleted, prioritized)\n' '\n' 'Target venue style (optional): {venue}\n' '\n' 'Paper extracted facts (JSON): {extraction}\n' '\n' 'Grounding digest (JSON): {grounding}'}, 'reviewer_a': {'system': 'You are a peer reviewer focusing on Methods & Claims. You focus on problem ' 'formulation, assumptions, correctness, and claim support. Be constructive ' 'but critical. Avoid vague statements. Do not invent missing details; if ' 'uncertain, say so. Ground novelty/prior-work claims ONLY in the provided ' 'grounding digest; if grounding is thin, say so. Return ONLY valid JSON.', 'user': 'Write a structured peer review in Markdown focusing on methods/claims.\n' 'Do NOT output numeric scores or an accept/reject decision in this step.\n' '\n' 'IMPORTANT: Treat preprints (arXiv) published within the last 6 months as ' "'concurrent work' rather than 'prior work' that invalidates novelty.\n" '\n' 'Output JSON schema:\n' '{{\n' ' "review_markdown": string\n' '}}\n' '\n' 'Include sections: Summary, Strengths, Weaknesses, Questions.\n' '\n' 'Target venue style (optional): {venue}\n' '\n' 'Paper extracted facts (JSON): {extraction}\n' '\n' 'Grounding digest (JSON): {grounding}\n' '\n' 'Paper text excerpt (for details; do NOT invent missing info):\n' '{head_text}'}, 'reviewer_b': {'system': 'You are a peer reviewer focusing on Experiments & Reproducibility. You ' 'focus on empirical validation, baselines, ablations, metrics, statistical ' 'rigor, and reproducibility. Be constructive but critical. Avoid vague ' 'statements. Do not invent missing details; if uncertain, say so. Ground ' 'novelty/prior-work claims ONLY in the provided grounding digest; if ' 'grounding is thin, say so. Return ONLY valid JSON.', 'user': 'Write a structured peer review in Markdown focusing on ' 'experiments/reproducibility.\n' 'Do NOT output numeric scores or an accept/reject decision in this step.\n' '\n' 'IMPORTANT: Treat preprints (arXiv) published within the last 6 months as ' "'concurrent work' rather than 'prior work' that invalidates novelty.\n" '\n' 'Output JSON schema:\n' '{{\n' ' "review_markdown": string\n' '}}\n' '\n' 'Include sections: Summary, Strengths, Weaknesses, Questions.\n' '\n' 'Target venue style (optional): {venue}\n' '\n' 'Paper extracted facts (JSON): {extraction}\n' '\n' 'Grounding digest (JSON): {grounding}\n' '\n' 'Paper text excerpt (for details; do NOT invent missing info):\n' '{head_text}'}, 'reviewer_c': {'system': 'You are a peer reviewer focusing on Clarity & Impact. You focus on writing ' 'quality, structure, limitations, missing details, broader impacts, and ' 'ethics/safety considerations. Be constructive but critical. Avoid vague ' 'statements. Do not invent missing details; if uncertain, say so. Ground '
                                                                                    'novelty/prior-work claims ONLY in the provided grounding digest; if '
                                           'grounding is thin, say so. Return ONLY valid JSON.',
                                 'user': 'Write a structured peer review in Markdown focusing on clarity, limitations, '
                                         'and broader impact.\n'
                                         'Do NOT output numeric scores or an accept/reject decision in this step.\n'
                                         '\n'
                                         'IMPORTANT: Treat preprints (arXiv) published within the last 6 months as '
                                         "'concurrent work' rather than 'prior work' that invalidates novelty.\n"
                                         '\n'
                                         'Output JSON schema:\n'
                                         '{{\n'
                                         '  "review_markdown": string\n'
                                         '}}\n'
                                         '\n'
                                         'Include sections: Summary, Strengths, Weaknesses, Questions.\n'
                                         '\n'
                                         'Target venue style (optional): {venue}\n'
                                         '\n'
                                         'Paper extracted facts (JSON): {extraction}\n'
                                         '\n'
                                         'Grounding digest (JSON): {grounding}\n'
                                         '\n'
                                         'Paper text excerpt (for details; do NOT invent missing info):\n'
                                         '{head_text}'}},
        'review': {'system': 'You are an expert peer reviewer. Your goal is to provide a balanced and fair review. Be '
                             'specific about strengths and weaknesses; avoid vague statements. Do not invent missing '
                             'details; if unsure, say so. Ground novelty/prior-work claims ONLY in the provided '
                             'grounding digest; if grounding is thin, say so. Return ONLY valid JSON.',
                   'user': 'Write the peer review text in Markdown. Do NOT output numeric scores, confidence, or an '
                           'accept/reject decision yet.\n'
                           '\n'
                           "IMPORTANT: Treat preprints (arXiv) published within the last 6 months as 'concurrent work' "
                           "rather than 'prior work' that invalidates novelty.\n"
                           '\n'
                           'Output JSON schema:\n'
                           '{{\n'
                           '  "review_markdown": string\n'
                           '}}\n'
                           '\n'
                           'The markdown MUST include these sections:\n'
                           '1) Summary of Contributions\n'
                           '2) Strengths\n'
                           '3) Weaknesses\n'
                           '4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n'
                           '5) Questions / Required Clarifications\n'
                           '6) Actionable Next Steps (bulleted, prioritized)\n'
                           '\n'
                           'Target venue style (optional): {venue}\n'
                           '\n'
                           'Paper extracted facts (JSON): {extraction}\n'
                           '\n'
                           'Grounding digest (JSON): {grounding}\n'
                           '\n'
                           'Paper text excerpt (for details; do NOT invent missing info):\n'
                           '{head_text}'},
        'review_combined': {'system': 'You are an expert peer reviewer. Your goal is to provide a balanced and fair '
                                      'review. Be specific about strengths and weaknesses; avoid vague statements. Do '
                                      'not invent missing details; if unsure, say so. Ground novelty/prior-work claims '
                                      'ONLY in the provided grounding digest; if grounding is thin, say so. Return '
                                      'ONLY valid JSON.',
                            'user': 'Write the peer review text in Markdown AND assign scores/decision in the same '
                                    'response.\n'
                                    'This is an ablation where write-then-score is disabled.\n'
                                    '\n'
                                    'IMPORTANT: Treat preprints (arXiv) published within the last 6 months as '
                                    "'concurrent work' rather than 'prior work' that invalidates novelty.\n"
                                    '\n'
                                    'Output JSON schema:\n'
                                    '{{\n'
                                    '  "review_markdown": string,\n'
                                    '  "decision": "Strong Accept"|"Accept"|"Weak Accept"|"Borderline"|"Weak '
                                    'Reject"|"Reject"|"Strong Reject",\n'
                                    '  "confidence": 1|2|3|4|5,\n'
                                    '  "scores": {{\n'
                                    '     "originality": 1-10,\n'
                                    '     "quality": 1-10,\n'
                                    '     "clarity": 1-10,\n'
                                    '     "significance": 1-10,\n'
                                    '     "reproducibility": 1-10,\n'
                                    '     "overall": 1-10\n'
                                    '  }}\n'
                                    '}}\n'
                                    '\n'
                                    'The markdown MUST include these sections:\n'
                                    '1) Summary of Contributions\n'
                                    '2) Strengths\n'
                                    '3) Weaknesses\n'
                                    '4) Novelty / Prior Work (cite arXiv ids/links when relevant)\n'
                                    '5) Questions / Required Clarifications\n'
                                    '6) Actionable Next Steps (bulleted, prioritized)\n'
                                    '\n'
                                    'Target venue style (optional): {venue}\n'
                                    '\n'
                                    'Paper extracted facts (JSON): {extraction}\n'
                                    '\n'
                                    'Grounding digest (JSON): {grounding}\n'
                                    '\n'
                                    'Paper text excerpt (for details; do NOT invent missing info):\n'
                                    '{head_text}'},
        'scoring': {'system': 'You are an expert peer reviewer assigning a final decision, confidence, and rubric '
        'scores AFTER reading the completed review text. Return ONLY valid JSON.', 'user': 'Given the review markdown and the underlying evidence, assign a final decision, ' 'confidence, and rubric scores.\n' '\n' 'Decision rubric (keep it simple and consistent):\n' '- Reject if there is a plausible fatal flaw invalidating core claims.\n' '- Weak Reject if evidence is insufficient for claims or key baselines/ablations are ' 'missing.\n' '- Borderline if promising but uncertain; specify what would change the decision.\n' '- Weak Accept/Accept/Strong Accept only if claims are supported and contribution is ' 'clear.\n' '\n' 'IMPORTANT constraints:\n' '- Do not rewrite the review text. Only output scores/decision/confidence.\n' '- If grounding evidence is thin, reflect that uncertainty in confidence/decision.\n' '\n' 'Output JSON schema:\n' '{{\n' ' "decision": "Strong Accept"|"Accept"|"Weak Accept"|"Borderline"|"Weak ' 'Reject"|"Reject"|"Strong Reject",\n' ' "confidence": 1|2|3|4|5,\n' ' "scores": {{\n' ' "originality": 1-10,\n' ' "quality": 1-10,\n' ' "clarity": 1-10,\n' ' "significance": 1-10,\n' ' "reproducibility": 1-10,\n' ' "overall": 1-10\n' ' }}\n' '}}\n' '\n' 'Target venue style (optional): {venue}\n' '\n' 'Review markdown (already written):\n' '{review_md}\n' '\n' 'Paper extracted facts (JSON): {extraction}\n' '\n' 'Grounding digest (JSON): {grounding}'}}}}```
**`paperreview.science_prompts` (v2)**```pythonSCIENCE_PROMPTS = {{'v2': {'hypothesis_miner': {'system': 'You are a research planning assistant. Your goal is to propose falsifiable ' 'hypotheses and minimal tests. You MUST ground each hypothesis in the provided ' 'dossier (claims/citations). Return ONLY valid JSON.', 'user': 'Given the paper dossier (structured evidence), produce 5-10 candidate hypotheses ' 'for follow-up research.\n' '\n' 'Constraints:\n' '- Each hypothesis must be falsifiable and operationalized.\n' '- Include at least 2 evidence links per hypothesis, pointing to claim indices ' 'and/or cited arXiv ids.\n' '- Include explicit falsification tests (minimal experiments/analyses).\n' '- Include explicit measurable metrics (name + unit).\n' '- Do NOT propose actions that require external tools (web browsing, emailing ' 'authors, wet-lab experiments).\n' '\n' 'Output JSON schema (ALL fields required in each hypothesis):\n' '{{\n' ' "hypotheses": [\n' ' {{\n' ' "hypothesis_version": "v2",\n' ' "statement": string,\n' ' "rationale": string,\n' ' "predictions": [string],\n' ' "falsification_tests": [string],\n' ' "metrics": [{{"name": string, "unit": string, "direction": ' '"increase"|"decrease"|"no_change"|"unknown", "baseline": string|number|null}}],\n' ' "operationalization": string,\n' ' "minimal_test": string,\n' ' "falsifier": string,\n' ' "assumptions": [string],\n' ' "dataset_or_source": string,\n' ' "evidence_links": [\n' ' {{"kind": "claim", "index": number}} OR {{"kind": "citation", ' '"arxiv_id": string}}\n' ' ],\n' ' "novelty_flags": {{"likely_known": true|false, "related_arxiv_ids": ' '[string]}},\n' ' "feasibility": {{"estimated_days": number, "requirements": [string], ' '"risks": [string]}}\n' ' }}\n' ' ]\n' '}}\n' '\n' 'Paper dossier JSON:\n' '{dossier_json}'}, 'hypothesis_ranker': {'system': 'You are a pragmatic research lead. You will rank candidate hypotheses for ' 'follow-up work. Prioritize: (1) falsifiability, (2) feasibility under tight ' 'budget, (3) expected impact/insight, (4) novelty relative to provided ' 'citations, (5) auditability (clear measurable outcomes). Return ONLY valid ' 'JSON.', 'user': 'Given a paper dossier and a list of candidate hypotheses, produce a ranking.\n' '\n' 'Constraints:\n' '- Rank must include only provided hypothesis_ids (no new ones).\n' '- No duplicates.\n'
                                      '- Provide a short justification per ranked hypothesis.\n'
                                      '\n'
                                      'Output JSON schema:\n'
                                      '{{\n'
                                      '  "ranking": [\n'
                                      '    {{"hypothesis_id": string, "rank": number, "score": number, "why": '
                                      'string}}\n'
                                      '  ]\n'
                                      '}}\n'
                                      '\n'
                                      'Paper dossier JSON:\n'
                                      '{dossier_json}\n'
                                      '\n'
                                      'Candidate hypotheses JSON:\n'
                                      '{hypotheses_json}'},
        'test_plan_writer': {'system': 'You are a meticulous experiment designer. You will write a minimal test plan '
                                       'for a single hypothesis. Return ONLY valid JSON.',
                             'user': 'Given a paper dossier and a selected hypothesis, write a minimal test plan in '
                                     'YAML.\n'
                                     '\n'
                                     'Constraints:\n'
                                     '- Keep it minimal and actionable.\n'
                                     '- Include baselines/ablations if applicable.\n'
                                     '- Include explicit acceptance criteria and stop conditions.\n'
                                     '- Do NOT require external tools or internet access.\n'
                                     '\n'
                                     'Output JSON schema:\n'
                                     '{{\n'
                                     '  "test_plan_yaml": string\n'
                                     '}}\n'
                                     '\n'
                                     'Paper dossier JSON:\n'
                                     '{dossier_json}\n'
                                     '\n'
                                     'Selected hypothesis JSON:\n'
                                     '{hypothesis_json}'}}}
}
```

**`paperreview.agenda_prompts` (v1)**
```python
AGENDA_PROMPTS = {
{'v1': {'agenda_summarizer': {'system': 'You are a research program lead. Your task is to summarize a multi-paper '
                                        'hypothesis agenda into a concise set of research directions and questions. '
                                        'You MUST stay grounded to the provided agenda JSON. Return ONLY valid JSON.',
                              'user': 'Given a research agenda (hypotheses grouped into clusters), provide a short '
                                      'program-level summary.\n'
                                      '\n'
                                      'Constraints:\n'
                                      '- Do NOT propose actions that require external tools (web browsing, emailing, '
                                      'wet-lab).\n'
                                      '- Keep it short and pragmatic.\n'
                                      '\n'
                                      'Output JSON schema:\n'
                                      '{{\n'
                                      '  "program_summary": string,\n'
                                      '  "research_questions": [string],\n'
                                      '  "top_clusters": [{{"cluster_id": string, "why": string}}]\n'
                                      '}}\n'
                                      '\n'
                                      'Agenda JSON:\n'
                                      '{agenda_json}'}}}
}
```

**`paperreview.screen_prompts` (v1)**
```python
SCREEN_PROMPTS = {
{'v1': {'screening_judge': {'system': 'You are a conservative research auditor. You must classify each hypothesis as '
                                      'keep/review/drop based ONLY on the provided agenda JSON. Return ONLY valid '
                                      'JSON.',
                            'user': 'Given the research agenda JSON, output a screening report.\n'
                                    '\n'
                                    'Constraints:\n'
                                    '- Decisions allowed: keep, review, drop.\n'
                                    '- Be conservative: if uncertain, choose review.\n'
                                    '- Do NOT propose actions requiring web/email/wet-lab.\n'
                                    '\n'
                                    'Output JSON schema:\n'
                                    '{{\n'
                                    '  "hypotheses": [\n'
                                    '    {{"hypothesis_id": string, "decision": "keep|review|drop", "score": number, '
                                    '"reasons": [string]}}\n'
                                    '  ]\n'
                                    '}}\n'
                                    '\n'
                                    'Agenda JSON:\n'
                                    '{agenda_json}'}}}
}
```

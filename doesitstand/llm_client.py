import hashlib
import json
import logging
import time
from typing import Any

from google import genai
from google.genai import types

from doesitstand.env import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MODEL_FLASH,
    GEMINI_TEMPERATURE,
)

_client = genai.Client(api_key=GEMINI_API_KEY)

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 131072
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


class LLMParseError(Exception):
    pass


class LLMAPIError(Exception):
    pass


def _prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n---\n{user}".encode()).hexdigest()[:16]


def llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str = GEMINI_MODEL,
    temperature: float = GEMINI_TEMPERATURE,
    seed: int = 42,
    max_output_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    return _llm_json_inner(
        system_prompt, user_prompt,
        model=model, temperature=temperature, seed=seed,
        max_output_tokens=max_output_tokens,
    )


def _llm_json_inner(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    seed: int,
    max_output_tokens: int,
    stage: str = "",
) -> dict[str, Any]:
    ph = _prompt_hash(system_prompt, user_prompt)
    logger.debug("llm_json call prompt_hash=%s model=%s stage=%s", ph, model, stage)

    try:
        response = _client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=temperature,
                seed=seed,
                max_output_tokens=max_output_tokens,
            ),
        )
    except Exception as exc:
        raise LLMAPIError(f"Gemini API error: {exc}") from exc

    raw = response.text
    if raw is None:
        raise LLMAPIError("Gemini returned empty response")

    if hasattr(response, "usage_metadata"):
        _track_usage(stage or "default", model, response.usage_metadata)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON. prompt_hash=%s raw=%r", ph, raw[:500])
        raise LLMParseError(f"LLM returned invalid JSON (prompt_hash={ph})") from exc


def llm_json_flash(
    system_prompt: str,
    user_prompt: str,
    temperature: float = GEMINI_TEMPERATURE,
    seed: int = 42,
    max_output_tokens: int = 16384,
) -> dict[str, Any]:
    return llm_json(
        system_prompt,
        user_prompt,
        model=GEMINI_MODEL_FLASH,
        temperature=temperature,
        seed=seed,
        max_output_tokens=max_output_tokens,
    )


def llm_json_pro(
    system_prompt: str,
    user_prompt: str,
    temperature: float = GEMINI_TEMPERATURE,
    seed: int = 42,
    max_output_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    return llm_json(
        system_prompt,
        user_prompt,
        model=GEMINI_MODEL,
        temperature=temperature,
        seed=seed,
        max_output_tokens=max_output_tokens,
    )


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

_cost_tracker: dict[str, dict] = {}

# Gemini 2.5 pricing per 1M tokens (USD, approximate)
_PRICING = {
    GEMINI_MODEL_FLASH: {"input": 0.075, "output": 0.30},
    GEMINI_MODEL: {"input": 1.25, "output": 10.00},
}


def _track_usage(stage: str, model: str, usage) -> None:
    # Use stage+model as key to separate Flash vs Pro costs
    key = f"{stage}_{model}" if stage and stage != "default" else model
    if key not in _cost_tracker:
        _cost_tracker[key] = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": model,
        }
    _cost_tracker[key]["calls"] += 1
    _cost_tracker[key]["input_tokens"] += getattr(usage, "prompt_token_count", 0) or 0
    _cost_tracker[key]["output_tokens"] += getattr(usage, "candidates_token_count", 0) or 0


def get_cost_report() -> dict[str, Any]:
    stages = {}
    total_usd = 0.0
    for stage, data in _cost_tracker.items():
        model = data.get("model", GEMINI_MODEL)
        rates = _PRICING.get(model, _PRICING.get(GEMINI_MODEL, {}))
        cost = (
            data["input_tokens"] * rates.get("input", 0) / 1_000_000
            + data["output_tokens"] * rates.get("output", 0) / 1_000_000
        )
        stages[stage] = {**data, "estimated_cost_usd": round(cost, 4)}
        total_usd += cost
    return {"stages": stages, "total_usd": round(total_usd, 4)}


def reset_cost_tracker() -> None:
    _cost_tracker.clear()


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in ("429", "500", "503", "timeout", "connection", "resource exhausted"))


def llm_json_with_retry(
    system_prompt: str,
    user_prompt: str,
    model: str = GEMINI_MODEL,
    temperature: float = GEMINI_TEMPERATURE,
    seed: int = 42,
    max_output_tokens: int = DEFAULT_MAX_TOKENS,
    stage: str = "",
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _llm_json_inner(
                system_prompt, user_prompt,
                model=model, temperature=temperature, seed=seed,
                max_output_tokens=max_output_tokens, stage=stage,
            )
        except LLMParseError:
            raise
        except LLMAPIError as exc:
            if not _is_retryable(exc):
                raise
            last_exc = exc
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "LLM retry %d/%d after %.1fs (stage=%s): %s",
                attempt + 1, max_retries, delay, stage, exc,
            )
            time.sleep(delay)
    raise LLMAPIError(f"All {max_retries} retries exhausted (stage={stage})") from last_exc


def llm_json_pro_with_retry(
    system_prompt: str,
    user_prompt: str,
    stage: str = "",
    **kwargs,
) -> dict[str, Any]:
    return llm_json_with_retry(
        system_prompt, user_prompt,
        model=GEMINI_MODEL, stage=stage, **kwargs,
    )

"""
ai_matcher.py — LLM-powered ecoinvent process matching.

Supports two LLM providers:
  - Anthropic (Claude Sonnet) — default
  - Perplexity (Sonar Pro) — OpenAI-compatible API

Provider is set in .env (LLM_PROVIDER) and can be overridden in the UI via
st.session_state.llm_provider.
"""
import json
import re
import requests
import streamlit as st
from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    PERPLEXITY_API_KEY, PERPLEXITY_MODEL,
    LLM_PROVIDER,
)
from ecoinvent_cache import load_cache


# ══════════════════════════════════════════════════════════════════════════
# UNIFIED LLM CALLER
# ══════════════════════════════════════════════════════════════════════════

def _get_provider() -> str:
    """Get current LLM provider. UI override takes precedence over .env."""
    return st.session_state.get("llm_provider", LLM_PROVIDER)


def _call_llm(system: str, user: str, max_tokens: int = 1000) -> str:
    """
    Send a request to the active LLM provider.
    Returns text response or "API_ERROR: ..." string.
    """
    provider = _get_provider()

    if provider == "anthropic":
        return _call_anthropic(system, user, max_tokens)
    elif provider == "perplexity":
        return _call_perplexity(system, user, max_tokens)
    else:
        return f"API_ERROR: Unknown provider '{provider}'"


def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    """Call Anthropic Messages API."""
    if not ANTHROPIC_API_KEY or "YOUR" in ANTHROPIC_API_KEY:
        return "API_ERROR: No Anthropic API key. Add ANTHROPIC_API_KEY to .env"

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )
    except Exception as e:
        return f"API_ERROR: Anthropic — {e}"


def _call_perplexity(system: str, user: str, max_tokens: int) -> str:
    """Call Perplexity API (OpenAI-compatible chat completions)."""
    if not PERPLEXITY_API_KEY or "YOUR" in PERPLEXITY_API_KEY:
        return "API_ERROR: No Perplexity API key. Add PERPLEXITY_API_KEY to .env"

    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            },
            json={
                "model": PERPLEXITY_MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        # OpenAI-compatible format
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return "API_ERROR: Perplexity returned no choices"
    except Exception as e:
        return f"API_ERROR: Perplexity — {e}"


def get_provider_status() -> dict:
    """Check which providers have valid API keys configured."""
    return {
        "anthropic": {
            "configured": bool(ANTHROPIC_API_KEY and "YOUR" not in ANTHROPIC_API_KEY),
            "model": ANTHROPIC_MODEL,
        },
        "perplexity": {
            "configured": bool(PERPLEXITY_API_KEY and "YOUR" not in PERPLEXITY_API_KEY),
            "model": PERPLEXITY_MODEL,
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# STAGE 1: Quick scan — names + geography only
# ══════════════════════════════════════════════════════════════════════════

STAGE1_SYSTEM = """You are an LCA expert specializing in ecoinvent database matching.

Given a user's description of a material/process and a list of available ecoinvent processes,
identify the TOP 5 most relevant processes by UUID.

Consider:
- Exact material composition and alloy type
- Geography (prefer matching region, fallback to GLO)
- Production route (primary vs secondary, specific technology)
- Voltage level for electricity (medium voltage for industrial)

Respond ONLY with valid JSON, no markdown formatting:
{
  "top5": [
    {"uuid": "...", "name": "...", "reason": "brief explanation"},
    ...
  ]
}"""


def _stage1_scan(user_description: str, category: str) -> list[dict]:
    """Stage 1: Send compact process list, get top 5 candidates."""
    cache = load_cache()
    if not cache:
        return []

    processes = cache.get(category, [])
    if not processes:
        return []

    compact = []
    for p in processes:
        compact.append(f"[{p['uuid']}] {p['name']} | {p.get('geography', '')}")

    process_list = "\n".join(compact)

    user_prompt = f"""User needs: {user_description}

Category: {category}
Available processes ({len(processes)} total):

{process_list}

Pick the 5 best matches. Respond with JSON only."""

    text = _call_llm(STAGE1_SYSTEM, user_prompt, max_tokens=600)
    if not text or "API_ERROR" in text:
        return []

    try:
        text = re.sub(r"```json|```", "", text).strip()
        result = json.loads(text)
        return result.get("top5", [])
    except (json.JSONDecodeError, KeyError):
        return []


# ══════════════════════════════════════════════════════════════════════════
# STAGE 2: Deep analysis — full exchange data for top candidates
# ══════════════════════════════════════════════════════════════════════════

STAGE2_SYSTEM = """You are an LCA expert. You are given a user's process description and 
detailed information about candidate ecoinvent processes including their input/output exchanges.

Select the SINGLE BEST match and explain why. Consider:
- Do the input flows match the expected material composition?
- Is the production route appropriate (e.g. Kroll process for titanium)?
- Does the geography match the user's location?
- Is the reference unit correct?

Respond ONLY with valid JSON, no markdown formatting:
{
  "best_match": {
    "uuid": "...",
    "name": "...",
    "confidence": 85,
    "reason": "detailed explanation"
  },
  "alternatives": [
    {"uuid": "...", "name": "...", "reason": "why this could also work"}
  ],
  "warnings": "any caveats"
}"""


def _stage2_confirm(user_description: str, candidates: list[dict], category: str) -> dict:
    """Stage 2: Send full exchange data for top candidates, get best match."""
    cache = load_cache()
    if not cache:
        return {}

    processes = cache.get(category, [])
    candidate_uuids = {c["uuid"] for c in candidates}

    details = []
    for p in processes:
        if p["uuid"] in candidate_uuids:
            detail = f"[UUID: {p['uuid']}] {p['name']}"
            detail += f"\nGeography: {p.get('geography', 'unknown')}"
            if p.get("description"):
                detail += f"\nDescription: {p['description'][:300]}"

            exchanges = p.get("exchanges", {})
            inputs = exchanges.get("inputs", [])
            outputs = exchanges.get("outputs", [])

            if inputs:
                detail += "\nINPUTS:"
                for e in sorted(inputs, key=lambda x: abs(x.get("amount", 0)), reverse=True)[:15]:
                    detail += f"\n  - {e['flow']}: {e['amount']:.4g} {e['unit']}"
            if outputs:
                detail += "\nOUTPUTS:"
                for e in sorted(outputs, key=lambda x: abs(x.get("amount", 0)), reverse=True)[:10]:
                    detail += f"\n  - {e['flow']}: {e['amount']:.4g} {e['unit']}"

            details.append(detail)

    candidates_text = "\n\n---\n\n".join(details)

    user_prompt = f"""User needs: {user_description}

Candidate processes:

{candidates_text}

Select the single best match. Respond with JSON only."""

    text = _call_llm(STAGE2_SYSTEM, user_prompt, max_tokens=800)
    if not text or "API_ERROR" in text:
        return {"error": text}

    try:
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except (json.JSONDecodeError, KeyError):
        return {"error": f"Failed to parse LLM response: {text[:200]}"}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def match_process(user_description: str, category: str) -> dict:
    """
    Full two-stage LLM matching against cached ecoinvent subset.

    Args:
        user_description: Natural language description of the process needed
        category: one of 'electricity', 'metals', 'inert_gases', 'waste_treatment'

    Returns:
        dict with 'best_match', 'alternatives', 'warnings', 'stage1_candidates'
    """
    cache = load_cache()
    if not cache:
        return {"error": "No ecoinvent cache. Build it on the Connection page first."}

    if not cache.get(category):
        return {"error": f"No processes cached for '{category}'."}

    provider = _get_provider()
    status = get_provider_status()
    if not status.get(provider, {}).get("configured"):
        return {"error": f"No API key for '{provider}'. Add it to your .env file."}

    # Stage 1
    candidates = _stage1_scan(user_description, category)
    if not candidates:
        return {"error": f"Stage 1 failed (provider: {provider}). Check API key.",
                "stage1_candidates": []}

    # Stage 2
    result = _stage2_confirm(user_description, candidates, category)
    result["stage1_candidates"] = candidates
    result["provider"] = provider

    return result
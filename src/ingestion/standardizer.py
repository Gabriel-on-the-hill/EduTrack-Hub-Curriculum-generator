# src/ingestion/standardizer.py
import json
import logging
from typing import List, Dict, Any, Tuple
from hashlib import sha256
from time import time
import os

from .llm_client import get_llm_provider, LLMResponse
from .schemas import StandardizedCompetency
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Config
BATCH_SIZE = int(os.environ.get("STD_BATCH_SIZE", "6"))
LLM_CONFIG = {"provider": os.environ.get("LITELL_PROVIDER", "dummy")}
CACHE_TTL = int(os.environ.get("STD_CACHE_TTL", "86400"))  # 24h

# Simple in-memory cache (process-local). For multi-worker, use Redis-backed cache.
std_cache = TTLCache(maxsize=10000, ttl=CACHE_TTL)

def _prompt_for_standardization(items: List[str]) -> str:
    """
    System + user prompt that asks the LLM to output strict JSON:
    {"items": [{"original_text":"...", "standardized_text":"...", "action_verb":"...", "content":"...", "context":"", "bloom_level":"", "complexity_level":"Low/Med/High", "source_chunk_id":"", "extraction_confidence":0.0 }]}
    """
    system = (
        "You are an assistant that rewrites curriculum competencies into a canonical learning-objective structure. "
        "For each input line, output JSON objects with fields: original_text, standardized_text, action_verb, content, context, bloom_level, complexity_level, source_chunk_id, extraction_confidence. "
        "Output must be valid JSON with a top-level key 'items' containing a list. Use simple text; do not include extra commentary."
    )
    body = system + "\n\nInputs:\n"
    for line in items:
        body += f"- {line}\n"
    body += "\nReturn JSON only."
    return body

def _hash_items(items: List[str]) -> str:
    concat = "\n".join(items)
    return sha256(concat.encode("utf-8")).hexdigest()

def standardize_batch(raw_items: List[Dict[str, Any]], llm_provider=None) -> List[StandardizedCompetency]:
    """
    raw_items: list of dicts with at least 'text' and 'source_chunk_id' keys.
    Returns list of StandardizedCompetency validated by Pydantic.
    """
    llm_provider = llm_provider or get_llm_provider(LLM_CONFIG)
    outputs: List[StandardizedCompetency] = []

    # Prepare strings for LLM from the raw items (preserve chunk ids mapping)
    texts = [f"{it['text']} ||| source_chunk:{it.get('source_chunk_id','')}" for it in raw_items]
    if not texts:
        return []

    key = _hash_items(texts)
    if key in std_cache:
        return std_cache[key]

    # Batch processing
    batches = [texts[i:i+BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    for batch in batches:
        prompt = _prompt_for_standardization(batch)
        resp: LLMResponse = llm_provider.call(prompt, max_tokens=1024)
        if not resp.ok:
            logger.warning("LLM failed for standardization batch; skipping batch.")
            continue
        # Try to parse JSON
        try:
            parsed = resp.parsed if resp.parsed is not None else json.loads(resp.text)
        except Exception as e:
            # attempt to extract JSON substring
            txt = resp.text
            start = txt.find("{")
            end = txt.rfind("}") + 1
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(txt[start:end])
                except:
                    parsed = {}
            else:
                logger.exception("Cannot parse LLM output for standardization: %s", e)
                parsed = {}

        items = parsed.get("items", []) if isinstance(parsed, dict) else []
        for it in items:
            try:
                # Basic cleanup of ID if LLM messed it up
                chunk_id = it.get("source_chunk_id")
                # If dummy returned "chunk-0" but we passed "real-id", we might need logic to map back.
                # However, for now we rely on the LLM copying the source_chunk string we gave it.
                # In robust impl, we map by index.
                
                sc = StandardizedCompetency(
                    original_text=it.get("original_text") or "",
                    standardized_text=it.get("standardized_text") or "",
                    action_verb=it.get("action_verb"),
                    content=it.get("content"),
                    context=it.get("context"),
                    bloom_level=it.get("bloom_level"),
                    complexity_level=it.get("complexity_level"),
                    source_chunk_id=chunk_id,
                    extraction_confidence=float(it.get("extraction_confidence", 0.0)),
                    llm_provenance={"provider_meta": resp.provider_meta, "prompt_hash": sha256(prompt.encode("utf-8")).hexdigest(), "raw": resp.text}
                )
                # enforce grounding: must have source_chunk_id
                if not sc.source_chunk_id:
                    logger.warning("Dropping standardized competency without source_chunk_id: %s", sc)
                    continue
                outputs.append(sc)
            except Exception as e:
                logger.warning("Failed to validate standardized object: %s", e)
                continue

    # Cache and return
    std_cache[key] = outputs
    return outputs

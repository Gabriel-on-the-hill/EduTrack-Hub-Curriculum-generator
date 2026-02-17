# src/ingestion/tagger.py
import json
import logging
from typing import Tuple, Dict, Any
from .llm_client import get_llm_provider, LLMResponse
from .schemas import CompetencyMetadata
from hashlib import sha256
import os

logger = logging.getLogger(__name__)
LLM_CONFIG = {"provider": os.environ.get("LITELL_PROVIDER", "dummy")}
TAG_BATCH_SIZE = int(os.environ.get("TAG_BATCH_SIZE", "12"))

def _prompt_for_tagging(item_texts: list) -> str:
    system = (
        "You are a strict classifier. For each competency text provided, output a JSON object with fields: "
        "subject (one of: Mathematics, Science, English, History, Geography, Computer Science, Other), "
        "grade_level (e.g. Year 4, Grade 6, University Year 1 if applicable or Unknown), "
        "domain (e.g., Algebra, Genetics), "
        "confidence_score (0.0-1.0), "
        "tags: list of short tags"
        ". Output must be valid JSON with top-level `items` array."
    )
    body = system + "\n\nInputs:\n"
    for t in item_texts:
        body += f"- {t}\n"
    body += "\nReturn JSON only."
    return body

def predict_metadata(standardized_items, llm_provider=None) -> Dict[str, CompetencyMetadata]:
    """
    standardized_items: list of StandardizedCompetency objects (Pydantic)
    returns mapping standardized_id -> CompetencyMetadata
    """
    llm_provider = llm_provider or get_llm_provider(LLM_CONFIG)
    results = {}
    
    if not standardized_items:
        return results
        
    # Prepare batch texts
    texts = [f"{it.standardized_text} ||| original:{it.original_text}" for it in standardized_items]
    prompt = _prompt_for_tagging(texts)
    resp: LLMResponse = llm_provider.call(prompt, max_tokens=1024)
    if not resp.ok:
        logger.warning("LLM tagging failed")
        return results
    try:
        parsed = resp.parsed if resp.parsed is not None else json.loads(resp.text)
    except Exception as e:
        txt = resp.text
        start = txt.find("{")
        end = txt.rfind("}") + 1
        parsed = json.loads(txt[start:end]) if start!=-1 and end!=-1 else {}
        
    items = parsed.get("items", [])
    # Items mapped in same order as input
    # Note: In a real world scenario, robust mapping by ID is better, 
    # but for this batch implementation we rely on order or heuristics.
    # Since Dummy provider echoes back, we need to be careful.
    
    for i, it in enumerate(items):
        if i >= len(standardized_items):
            break
            
        try:
            meta = CompetencyMetadata(
                standardized_id=standardized_items[i].standardized_id,
                subject=it.get("subject"),
                grade_level=it.get("grade_level"),
                domain=it.get("domain"),
                confidence_score=float(it.get("confidence_score", 0.0)),
                tags=it.get("tags", []),
                llm_provenance={"provider_meta": resp.provider_meta, "prompt_hash": sha256(prompt.encode("utf-8")).hexdigest()}
            )
            results[meta.standardized_id] = meta
        except Exception as e:
            logger.warning("Failed to validate metadata: %s", e)
    return results

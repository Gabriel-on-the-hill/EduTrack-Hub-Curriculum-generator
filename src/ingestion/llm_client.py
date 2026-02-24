# src/ingestion/llm_client.py
import os, time, json, logging, hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)
LITELL_PROVIDER = os.environ.get("LITELL_PROVIDER", "dummy")
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.environ.get("LLM_RETRY_BACKOFF", "1.5"))

@dataclass
class LLMResponse:
    ok: bool
    text: str
    parsed: Optional[Any] = None
    provider_meta: Optional[Dict] = None

class LLMProviderInterface:
    def call(self, prompt: str, max_tokens: int = 512, **kwargs) -> LLMResponse:
        raise NotImplementedError()

# Dummy provider (deterministic for tests)
class DummyLLMProvider(LLMProviderInterface):
    def __init__(self, seed: int = 42):
        self.model_name = "dummy-local"

    def call(self, prompt: str, max_tokens: int = 512, **kwargs):
        # deterministic basic JSON response for testing
        items = []
        lines = [l for l in prompt.splitlines() if l.strip().startswith("- ")]
        if not lines:
             lines = [l.strip() for l in prompt.splitlines() if len(l) > 10][:5]
             
        for i, line in enumerate(lines[:8]):
            clean = line.lstrip("- ")
            items.append({
                "original_text": clean[:400],
                "standardized_text": f"Standardized: {clean[:200]}",
                "action_verb": "Identify",
                "content": " ".join(clean.split()[:4]),
                "context": "",
                "bloom_level": "Understand",
                "complexity_level": "Low",
                "source_chunk_id": f"chunk-{i}",
                "extraction_confidence": 0.95,
                
                # Tagging fields
                "subject": "Mathematics",
                "grade_level": "Year 4",
                "domain": "Algebra",
                "confidence_score": 0.95,
                "tags": ["math"]
            })
            
        return LLMResponse(ok=True, text=json.dumps({"items": items}), parsed={"items": items}, provider_meta={"model":self.model_name})

# OpenAI wrapper
class OpenAIProvider(LLMProviderInterface):
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        try:
            import openai
        except Exception as e:
            raise RuntimeError("openai SDK not installed") from e
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.model_name = f"openai:{model}"

    def call(self, prompt: str, max_tokens: int = 512, **kwargs):
        import openai
        # Use v1.x client
        client = openai.OpenAI(api_key=self.api_key)
        for attempt in range(LLM_MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role":"system","content":"You are a curriculum standardization assistant."},{"role":"user","content":prompt}],
                    max_tokens=max_tokens,
                    temperature=0.0
                )
                text = resp.choices[0].message.content
                return LLMResponse(ok=True, text=text, parsed=None, provider_meta={"model":self.model})
            except Exception as e:
                logger.warning("OpenAI call failed: %s. Retry %s", e, attempt)
                time.sleep(LLM_RETRY_BACKOFF ** attempt)
        return LLMResponse(ok=False, text="", parsed=None, provider_meta={})

# Gemini provider via litellm (if litellm installed)
class GeminiProvider(LLMProviderInterface):
    def __init__(self, model: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        try:
            import litellm
        except Exception:
            raise RuntimeError("litellm is not installed")
        self.model = model
        self.client = litellm # litellm module acts as client
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            os.environ["GEMINI_API_KEY"] = self.api_key
        self.model_name = f"gemini:{model}"

    def call(self, prompt: str, max_tokens: int = 512, **kwargs):
        import litellm
        for attempt in range(LLM_MAX_RETRIES):
            try:
                # Litellm completion
                resp = litellm.completion(
                    model=self.model, 
                    messages=[{"role":"user","content":prompt}], 
                    max_tokens=max_tokens
                )
                text = resp.choices[0].message.content
                return LLMResponse(ok=True, text=text, parsed=None, provider_meta={"model":self.model})
            except Exception as e:
                logger.warning("Gemini call failed attempt %s: %s", attempt, e)
                time.sleep(LLM_RETRY_BACKOFF ** attempt)
        return LLMResponse(ok=False, text="", parsed=None, provider_meta={})

# Factory
def get_llm_provider(config: Optional[Dict[str,Any]] = None) -> LLMProviderInterface:
    provider = (config or {}).get("provider") or os.environ.get("LITELL_PROVIDER", "dummy")
    if provider == "dummy":
        return DummyLLMProvider()
    if provider == "openai":
        return OpenAIProvider(api_key=(config or {}).get("api_key"))
    if provider == "gemini":
        return GeminiProvider(model=(config or {}).get("model", "gemini-1.5-flash"), api_key=(config or {}).get("api_key"))
    # fallback
    return DummyLLMProvider()

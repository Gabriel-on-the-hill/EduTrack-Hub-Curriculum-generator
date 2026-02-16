"""
AI Client (Blueprint Section 15.1)

This module provides a robust wrapper around AI providers with:
- Rate limiting (respects free tier limits)
- Structured output enforcement
- Retry logic with exponential backoff
- Cost tracking

Supported Providers (via AI_PROVIDER env var):
- "gemini"      (default) — Google Gemini API
- "openrouter"  — OpenRouter.ai (free models available)

Blueprint Section 15.1 Configuration:
- Primary: Gemini 2.0 Flash (low/medium tasks)
- Escalation: Gemini 1.5 Pro (high/critical tasks)
- Response format: application/json with schema
"""

import asyncio
import json
import logging
import os
import time
from enum import Enum
from typing import Any, TypeVar
from uuid import uuid4

# Import Model Router for smart selection
from src.utils.model_router import ModelRouter, TaskType

from pydantic import BaseModel

from src.schemas.base import FallbackTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiModel(str, Enum):
    """Available Gemini models per Blueprint Section 15.1."""
    FLASH = "gemini-2.0-flash"  # Primary: Low/Medium tasks
    PRO = "gemini-1.5-pro"      # Escalation: High/Critical tasks


# Ordered fallback chain of free OpenRouter models
OPENROUTER_FREE_MODELS: list[str] = [
    "openrouter/free",                              # Auto-router: picks best available free model
    "meta-llama/llama-4-maverick:free",              # Llama 4 Maverick
    "deepseek/deepseek-chat-v3-0324:free",           # DeepSeek V3
    "meta-llama/llama-3.3-70b-instruct:free",        # Llama 3.3 70B
    "google/gemma-3-27b-it:free",                    # Gemma 3 27B
    "mistralai/mistral-small-3.1-24b-instruct:free", # Mistral Small
]


class RateLimitConfig:
    """
    Rate limits for Gemini free tier.
    
    Blueprint Section 15.1:
    - Gemini 2.0 Flash: 15 RPM, 1M TPM, 1,500 daily
    - Gemini 1.5 Pro: 2 RPM, 32K TPM, 50 daily
    """
    FLASH_RPM = 15
    FLASH_TPM = 1_000_000
    FLASH_DAILY = 1_500
    
    PRO_RPM = 2
    PRO_TPM = 32_000
    PRO_DAILY = 50


class TokenBucket:
    """
    Token bucket rate limiter.
    
    Ensures we don't exceed API rate limits.
    """
    
    def __init__(self, rate: float, capacity: float) -> None:
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens per second to add
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Wait until enough tokens are available."""
        while True:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            
            # Wait for tokens to refill
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


# =============================================================================
# OPENROUTER BACKEND
# =============================================================================

class OpenRouterClient:
    """
    OpenRouter.ai client — drop-in alternative to Gemini.
    
    Uses requests (already installed) to call OpenRouter's REST API.
    Automatically falls back through multiple free models if one is unavailable.
    Sign up at https://openrouter.ai to get a free API key.
    """
    
    def __init__(self) -> None:
        import requests as _requests
        self._requests = _requests
        
        api_key = None
        
        # Try Streamlit secrets
        try:
            import streamlit as st
            api_key = st.secrets.get("OPENROUTER_API_KEY")
        except Exception:
            pass
        
        # Fallback to env
        if not api_key:
            api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Get a free key at https://openrouter.ai/keys"
            )
        
        self._api_key = api_key
        self._base_url = "https://openrouter.ai/api/v1/chat/completions"
        self._configured = True
        self._daily_calls: dict[str, int] = {
            GeminiModel.FLASH: 0,
            GeminiModel.PRO: 0,
        }
        self._total_tokens = 0
        self._estimated_cost = 0.0
        
        # Initialize Smart Model Router
        self._router = ModelRouter()
    
    def _call_api(self, messages: list[dict], models: list[str], temperature: float) -> str:
        """
        Make a synchronous HTTP call to OpenRouter.
        
        Iterates through the provided list of models until one succeeds.
        Handles 404 (model not found) and 429 (rate limit) errors.
        """
        import time as _time
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Gabriel-on-the-hill/EduTrack-Curriculum-generator",
        }
        
        # Use provided model list; if empty, fallback to default router list
        models_to_try = models if models else self._router.get_candidate_models(TaskType.STANDARD)
        
        last_error = None
        for try_model in models_to_try:
            payload = {
                "model": try_model,
                "messages": messages,
                "temperature": temperature,
            }
            
            try:
                resp = self._requests.post(
                    self._base_url, headers=headers, json=payload, timeout=120
                )
                
                if resp.status_code == 404:
                    logger.warning(f"Model {try_model} not found, trying next...")
                    continue
                
                if resp.status_code == 429:
                    wait = min(int(resp.headers.get("Retry-After", 10)), 30)
                    logger.warning(f"Model {try_model} rate-limited, trying next after {wait}s...")
                    _time.sleep(wait)
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                
                # Log if we fell back to a secondary model
                if try_model != models_to_try[0]:
                    logger.info(f"Fallback: used {try_model} instead of {models_to_try[0]}")
                
                return data["choices"][0]["message"]["content"] or ""
                
            except Exception as e:
                last_error = e
                logger.warning(f"Error with {try_model}: {e}")
                continue
        
        raise ValueError(
            f"All free models exhausted. Last error: {last_error}"
        )
    
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        model: GeminiModel = GeminiModel.FLASH,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        # Use Router: Formatting models are best for JSON structure
        effective_task = TaskType.FORMATTING
        if model == GeminiModel.PRO:
            effective_task = TaskType.REASONING
            
        candidates = self._router.get_candidate_models(effective_task)
        
        json_schema = response_schema.model_json_schema()
        
        system_msg = (
            "You are a precise curriculum generation assistant. "
            "You MUST respond with valid JSON matching this schema:\n"
            f"{json.dumps(json_schema, indent=2)}\n"
            "Respond ONLY with the JSON object, no markdown fences, no extra text."
        )
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]
        
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                text = await asyncio.to_thread(self._call_api, messages, candidates, temperature)
                
                self._daily_calls[model] += 1
                # Strip markdown code fences if present
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                
                data = json.loads(text)
                return response_schema.model_validate(data)
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"OpenRouter API error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                await asyncio.sleep(2 ** attempt)
        
        raise ValueError(
            f"Failed to generate structured output after {max_retries} attempts: "
            f"{last_error}"
        )
    
    async def generate_text(
        self,
        prompt: str,
        model: GeminiModel = GeminiModel.FLASH,
        temperature: float = 0.7,
        task_type: TaskType = TaskType.STANDARD,
    ) -> str:
        """Generate plain text output."""
        
        # Determine candidate models
        if model not in [GeminiModel.FLASH, GeminiModel.PRO]:
            # Specific model requested (e.g. from config)
            candidates = [model]
        else:
            # Use Router with task type
            effective_task = task_type
            if model == GeminiModel.PRO:
                effective_task = TaskType.REASONING
            candidates = self._router.get_candidate_models(effective_task)
            
        system_msg = "You are a helpful curriculum assistant."
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]
        
        return await asyncio.to_thread(self._call_api, messages, candidates, temperature)
    
    def select_model_for_tier(self, tier: FallbackTier) -> GeminiModel:
        if tier == FallbackTier.TIER_0:
            return GeminiModel.FLASH
        return GeminiModel.PRO
    
    def get_usage_stats(self) -> dict[str, Any]:
        return {
            "daily_calls": dict(self._daily_calls),
            "total_tokens": self._total_tokens,
            "estimated_cost_usd": self._estimated_cost,
            "provider": "openrouter",
        }


# =============================================================================
# GEMINI BACKEND (original)
# =============================================================================

class GeminiClient:
    """
    Robust Gemini API client with rate limiting and structured output.
    
    Usage:
        client = GeminiClient()
        result = await client.generate_structured(
            prompt="Extract competencies from this text...",
            response_schema=CompetencyList,
            model=GeminiModel.FLASH
        )
    """
    
    def __init__(self) -> None:
        """Initialize client with API key from environment or Streamlit secrets."""
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig
        self._genai = genai
        self._GenerationConfig = GenerationConfig
        
        # Try to get API key from multiple sources
        api_key = None
        
        # 1. Try Streamlit secrets first (for Streamlit Cloud)
        try:
            import streamlit as st
            api_key = st.secrets.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_AI_API_KEY")
        except Exception:
            pass  # Not running in Streamlit context
        
        # 2. Fallback to environment variables
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
        
        if not api_key:
            logger.warning(
                "GOOGLE_API_KEY not set. "
                "Gemini API calls will fail in production."
            )
            self._configured = False
        else:
            genai.configure(api_key=api_key)
            self._configured = True
        
        # Rate limiters per model
        self._flash_limiter = TokenBucket(
            rate=RateLimitConfig.FLASH_RPM / 60,  # Per second
            capacity=RateLimitConfig.FLASH_RPM
        )
        self._pro_limiter = TokenBucket(
            rate=RateLimitConfig.PRO_RPM / 60,
            capacity=RateLimitConfig.PRO_RPM
        )
        
        # Daily call tracking
        self._daily_calls: dict[str, int] = {
            GeminiModel.FLASH: 0,
            GeminiModel.PRO: 0,
        }
        
        # Cost tracking
        self._total_tokens = 0
        self._estimated_cost = 0.0
    
    def _get_limiter(self, model: GeminiModel) -> TokenBucket:
        """Get rate limiter for a model."""
        if model == GeminiModel.FLASH:
            return self._flash_limiter
        return self._pro_limiter
    
    def _get_daily_limit(self, model: GeminiModel) -> int:
        """Get daily limit for a model."""
        if model == GeminiModel.FLASH:
            return RateLimitConfig.FLASH_DAILY
        return RateLimitConfig.PRO_DAILY
    
    def _check_daily_limit(self, model: GeminiModel) -> bool:
        """Check if we're within daily limit."""
        return self._daily_calls[model] < self._get_daily_limit(model)
    
    def select_model_for_tier(self, tier: FallbackTier) -> GeminiModel:
        """
        Select model based on fallback tier.
        
        Blueprint Section 21.4:
        - Tier 0: Cost-optimized (Flash)
        - Tier 1: Accuracy escalation (Pro)
        - Tier 2: Deterministic (falls back to rules)
        """
        if tier == FallbackTier.TIER_0:
            return GeminiModel.FLASH
        return GeminiModel.PRO
    
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        model: GeminiModel = GeminiModel.FLASH,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> T:
        """
        Generate structured output validated against a Pydantic schema.
        
        Blueprint Section 15.1:
        - response_mime_type: application/json
        - response_schema: Pydantic model schema
        
        Args:
            prompt: The prompt to send
            response_schema: Pydantic model class for validation
            model: Which Gemini model to use
            temperature: Sampling temperature (lower = more deterministic)
            max_retries: Number of retries on failure
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            ValueError: If generation fails after retries
        """
        if not self._configured:
            # Return mock data for testing without API key
            logger.warning("Gemini not configured, returning mock response")
            return self._mock_response(response_schema)
        
        # Check daily limit
        if not self._check_daily_limit(model):
            logger.warning(
                f"Daily limit reached for {model.value}, "
                f"switching to alternate model"
            )
            model = GeminiModel.PRO if model == GeminiModel.FLASH else GeminiModel.FLASH
        
        # Rate limit
        await self._get_limiter(model).acquire()
        
        # Build schema for Gemini
        json_schema = response_schema.model_json_schema()
        
        # Generation config with structured output
        generation_config = self._GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=json_schema,
        )
        
        # Create model instance
        gemini_model = self._genai.GenerativeModel(
            model_name=model.value,
            generation_config=generation_config,
        )
        
        # Retry loop
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    gemini_model.generate_content, prompt
                )
                
                # Track usage
                self._daily_calls[model] += 1
                
                # Parse and validate response
                if response.text:
                    data = json.loads(response.text)
                    return response_schema.model_validate(data)
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
        
        raise ValueError(
            f"Failed to generate structured output after {max_retries} attempts: "
            f"{last_error}"
        )
    
    async def generate_text(
        self,
        prompt: str,
        model: GeminiModel = GeminiModel.FLASH,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate plain text output.
        
        For tasks that don't need structured output.
        """
        if not self._configured:
            return "Mock response - API not configured"
        
        await self._get_limiter(model).acquire()
        
        gemini_model = self._genai.GenerativeModel(
            model_name=model.value,
            generation_config=self._GenerationConfig(temperature=temperature),
        )
        
        response = await asyncio.to_thread(
            gemini_model.generate_content, prompt
        )
        
        self._daily_calls[model] += 1
        return response.text or ""
    
    def _mock_response(self, schema: type[T]) -> T:
        """Generate mock response for testing without API."""
        # Create minimal valid instance
        # This uses Pydantic's model_construct to skip validation
        # In tests, we'll provide proper mock data
        raise ValueError(
            "Cannot mock complex schema. "
            "Set GOOGLE_AI_API_KEY or provide test fixtures."
        )
    
    def get_usage_stats(self) -> dict[str, Any]:
        """Get current usage statistics."""
        return {
            "daily_calls": dict(self._daily_calls),
            "total_tokens": self._total_tokens,
            "estimated_cost_usd": self._estimated_cost,
            "provider": "gemini",
        }


# =============================================================================
# CLIENT FACTORY
# =============================================================================

# Global client instance
_client: GeminiClient | OpenRouterClient | None = None


def get_gemini_client() -> GeminiClient | OpenRouterClient:
    """
    Get or create the global AI client.
    
    Selects provider based on AI_PROVIDER setting:
    - "openrouter" → OpenRouterClient (free models via openrouter.ai)
    - "gemini" (default) → GeminiClient (Google Gemini API)
    
    Checks Streamlit secrets first, then env vars.
    """
    global _client
    if _client is None:
        provider = None
        
        # Check Streamlit secrets first
        try:
            import streamlit as st
            provider = st.secrets.get("AI_PROVIDER")
        except Exception:
            pass
        
        # Fallback to env var
        if not provider:
            provider = os.getenv("AI_PROVIDER", "gemini")
        
        provider = provider.lower().strip()
        
        if provider == "openrouter":
            logger.info("Using OpenRouter AI provider")
            _client = OpenRouterClient()
        else:
            logger.info("Using Gemini AI provider")
            _client = GeminiClient()
    return _client

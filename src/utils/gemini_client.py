"""
Gemini API Client (Blueprint Section 15.1)

This module provides a robust wrapper around the Gemini API with:
- Rate limiting (respects free tier limits)
- Structured output enforcement
- Retry logic with exponential backoff
- Cost tracking

Blueprint Section 15.1 Configuration:
- Primary: Gemini 2.0 Flash (low/medium tasks)
- Escalation: Gemini 1.5 Pro (high/critical tasks)
- Response format: application/json with schema
"""

import asyncio
import logging
import os
import time
from enum import Enum
from typing import Any, TypeVar

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import BaseModel

from src.schemas.base import FallbackTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiModel(str, Enum):
    """Available Gemini models per Blueprint Section 15.1."""
    FLASH = "gemini-2.0-flash"  # Primary: Low/Medium tasks
    PRO = "gemini-1.5-pro"      # Escalation: High/Critical tasks


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
        generation_config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=json_schema,
        )
        
        # Create model instance
        gemini_model = genai.GenerativeModel(
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
                    import json
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
        
        gemini_model = genai.GenerativeModel(
            model_name=model.value,
            generation_config=GenerationConfig(temperature=temperature),
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
        }


# Global client instance
_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Get or create the global Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client

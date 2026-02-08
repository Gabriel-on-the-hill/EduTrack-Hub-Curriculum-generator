"""
Embedding Provider Interface (Phase 4 Fix #1)

Defines the contract for embedding providers and implements:
- LocalSentenceTransformerProvider (MANDATORY for Phase 4)
- GeminiEmbeddingProvider (OPTIONAL fallback for production only)

BINDING RULES:
- Phase 4 validation MUST use local provider
- Never mix embeddings across providers in same vector space
- Never compare Gemini vectors to local vectors
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np


class EmbeddingContext(str, Enum):
    """Context in which embeddings are being used."""
    SYNTHETIC_VALIDATION = "synthetic_validation"  # Phase 4 - local only
    PRODUCTION = "production"  # Phase 5+ - local primary, Gemini fallback


# =============================================================================
# THRESHOLDS (Named Constants - No Magic Numbers)
# =============================================================================

class MatcherThresholds:
    """
    Named constants for matching thresholds.
    
    Per user specification:
    - FOUNDATIONAL: ≥ 0.85 (strict, require embedding match)
    - STANDARD: ≥ 0.75
    - PERIPHERAL: ≥ 0.70
    - Jaccard: ≥ 0.60 for token match
    """
    # Jaccard (token-based)
    JACCARD_EXACT: float = 1.0
    JACCARD_THRESHOLD: float = 0.60
    
    # Cosine similarity (embedding-based) - by topic weight
    COSINE_FOUNDATIONAL: float = 0.85
    COSINE_STANDARD: float = 0.75
    COSINE_PERIPHERAL: float = 0.70
    
    @classmethod
    def get_cosine_threshold(cls, weight: str) -> float:
        """Get cosine threshold for topic weight."""
        thresholds = {
            "foundational": cls.COSINE_FOUNDATIONAL,
            "standard": cls.COSINE_STANDARD,
            "peripheral": cls.COSINE_PERIPHERAL,
        }
        return thresholds.get(weight.lower(), cls.COSINE_STANDARD)


# =============================================================================
# EMBEDDING PROVIDER INTERFACE
# =============================================================================

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        ...
    
    def name(self) -> str:
        """Return provider name for logging/auditing."""
        ...


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers."""
    
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts into vectors."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Return provider name."""
        pass
    
    def embed_single(self, text: str) -> list[float]:
        """Convenience method for single text."""
        return self.embed([text])[0]
    
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))


# =============================================================================
# LOCAL SENTENCE TRANSFORMER PROVIDER (MANDATORY FOR PHASE 4)
# =============================================================================

# Check if sentence-transformers is available
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore


def is_embeddings_available() -> bool:
    """Check if semantic embeddings are available."""
    return SENTENCE_TRANSFORMERS_AVAILABLE


class LocalSentenceTransformerProvider(BaseEmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.
    
    MANDATORY for Phase 4 (synthetic validation).
    Provides deterministic, reproducible embeddings.
    
    Recommended models:
    - all-MiniLM-L6-v2: 384 dims, fast, excellent for topic matching
    - all-mpnet-base-v2: 768 dims, higher accuracy, slower
    """
    
    # Default model - balanced performance
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    
    def __init__(self, model_name: str | None = None):
        """
        Initialize with specified model.
        
        Args:
            model_name: HuggingFace model name. Defaults to all-MiniLM-L6-v2.
        """
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None  # Lazy load
    
    def _load_model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError(
                    "sentence-transformers is required for semantic embeddings. "
                    "Install with: pip install sentence-transformers\n"
                    "Or use JaccardOnlyProvider for token-based matching only."
                )
            self._model = SentenceTransformer(self._model_name)
        return self._model
    
    def _get_model_details(self) -> dict[str, str]:
        """Get model version details for reproducibility."""
        # Note: sentence-transformers doesn't always expose exact version hash easily
        # without loading, so we do best effort or rely on library version + model name
        import sentence_transformers
        return {
            "library_version": sentence_transformers.__version__,
            "model_name": self._model_name,
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using local model."""
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def name(self) -> str:
        """Return provider name with version info for logging."""
        details = self._get_model_details()
        return f"local:{details['model_name']}@st-{details['library_version']}"


class JaccardOnlyProvider(BaseEmbeddingProvider):
    """
    Fallback provider when sentence-transformers unavailable.
    
    Uses simple word-vector representation (bag of words) for
    basic similarity, allowing Phase 4 to run without heavy deps.
    
    NOTE: Less accurate than semantic embeddings, but works everywhere.
    """
    
    def __init__(self):
        """Initialize the Jaccard-only provider."""
        self._vocab: dict[str, int] = {}
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Create simple word-frequency vectors.
        
        This is NOT semantic embedding - it's a fallback for
        environments where sentence-transformers can't be installed.
        """
        # Build vocabulary from all texts
        all_words: set[str] = set()
        tokenized = []
        for text in texts:
            words = set(text.lower().split())
            all_words.update(words)
            tokenized.append(words)
        
        # Create word-to-index mapping
        vocab = {word: i for i, word in enumerate(sorted(all_words))}
        
        # Create vectors
        embeddings = []
        for words in tokenized:
            vec = [0.0] * len(vocab)
            for word in words:
                if word in vocab:
                    vec[vocab[word]] = 1.0
            # Normalize
            norm = sum(v*v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            embeddings.append(vec)
        
        return embeddings
    
    def name(self) -> str:
        return "jaccard-only:fallback"


# =============================================================================
# GEMINI EMBEDDING PROVIDER (OPTIONAL FALLBACK - PRODUCTION ONLY)
# =============================================================================

class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Gemini API embedding provider.
    
    OPTIONAL fallback for production (Phase 5+).
    NOT allowed for Phase 4 synthetic validation.
    
    Use only when:
    - Local model unavailable
    - Hardware constrained
    - Explicitly cost-approved
    - Output is NOT used for storage or truth gating
    """
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize with API key.
        
        Args:
            api_key: Gemini API key. Falls back to env var if not provided.
        """
        self._api_key = api_key
        self._model = None
    
    def _get_client(self):
        """Get or create Gemini client."""
        if self._model is None:
            import os
            try:
                import google.generativeai as genai
                api_key = self._api_key or os.environ.get("GOOGLE_AI_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_AI_API_KEY required for Gemini embeddings")
                genai.configure(api_key=api_key)
                self._model = genai
            except ImportError:
                raise ImportError(
                    "google-generativeai is required for Gemini embeddings."
                )
        return self._model
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using Gemini API."""
        genai = self._get_client()
        
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="semantic_similarity",
            )
            embeddings.append(result["embedding"])
        
        return embeddings
    
    def name(self) -> str:
        return "gemini:embedding-001"


# =============================================================================
# PROVIDER FACTORY WITH CONTEXT ENFORCEMENT
# =============================================================================

class EmbeddingProviderFactory:
    """
    Factory for creating embedding providers with context enforcement.
    
    BINDING RULE: synthetic_validation context MUST use local provider.
    Falls back to JaccardOnlyProvider if sentence-transformers unavailable.
    """
    
    _local_provider: LocalSentenceTransformerProvider | JaccardOnlyProvider | None = None
    _gemini_provider: GeminiEmbeddingProvider | None = None
    
    @classmethod
    def get_provider(
        cls,
        context: EmbeddingContext,
        prefer_gemini: bool = False,
    ) -> BaseEmbeddingProvider:
        """
        Get appropriate provider for context.
        
        Args:
            context: The context in which embeddings are used
            prefer_gemini: If True and context allows, use Gemini
            
        Returns:
            Appropriate embedding provider
            
        Raises:
            AssertionError: If trying to use Gemini for synthetic validation
        """
        # BINDING RULE: Phase 4 synthetic validation MUST use local
        if context == EmbeddingContext.SYNTHETIC_VALIDATION:
            assert not prefer_gemini, (
                "Gemini embeddings are NOT allowed for synthetic validation. "
                "Phase 4 requires deterministic local embeddings for reproducibility."
            )
            return cls._get_local_provider()
        
        # Production: local by default, Gemini as optional fallback
        if prefer_gemini:
            return cls._get_gemini_provider()
        return cls._get_local_provider()
    
    @classmethod
    def _get_local_provider(cls) -> BaseEmbeddingProvider:
        """
        Get or create local provider (singleton).
        
        Falls back to JaccardOnlyProvider if sentence-transformers unavailable.
        """
        if cls._local_provider is None:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                cls._local_provider = LocalSentenceTransformerProvider()
            else:
                # Fallback: Jaccard-only matching (no semantic embeddings)
                cls._local_provider = JaccardOnlyProvider()
        return cls._local_provider
    
    @classmethod
    def _get_gemini_provider(cls) -> GeminiEmbeddingProvider:
        """Get or create Gemini provider (singleton)."""
        if cls._gemini_provider is None:
            cls._gemini_provider = GeminiEmbeddingProvider()
        return cls._gemini_provider
    
    @classmethod
    def reset(cls):
        """Reset singleton providers (for testing)."""
        cls._local_provider = None
        cls._gemini_provider = None


def get_embedding_provider(context: EmbeddingContext = EmbeddingContext.SYNTHETIC_VALIDATION) -> BaseEmbeddingProvider:
    """
    Convenience function to get embedding provider.
    
    For Phase 4, always returns local provider.
    """
    return EmbeddingProviderFactory.get_provider(context)

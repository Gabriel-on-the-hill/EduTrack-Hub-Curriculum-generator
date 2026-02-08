"""
Embedding Provider (Phase 5)

Real content delta computation using sentence-transformers.
Local, deterministic embeddings.
"""

import numpy as np
from typing import List, Protocol


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts into vectors."""
        ...
    
    @property
    def model_name(self) -> str:
        """Return model identifier."""
        ...


class SentenceTransformerProvider:
    """
    Real embedding provider using sentence-transformers.
    
    Model: all-MiniLM-L6-v2 (local, deterministic)
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self._model_name = model_name
        except ImportError:
            raise ImportError(
                "sentence-transformers required for embeddings. "
                "Install with: pip install sentence-transformers"
            )
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts into vectors."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def cosine_distance(self, a: str, b: str) -> float:
        """
        Compute cosine distance (1 - similarity) between two texts.
        
        Returns:
            0.0 = identical
            1.0 = orthogonal
            2.0 = opposite
        """
        va, vb = self.model.encode([a, b])
        sim = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb))
        return 1.0 - float(sim)


class MockEmbeddingProvider:
    """
    Mock provider for testing without sentence-transformers.
    """
    
    def __init__(self, model_name: str = "mock-embeddings"):
        self._model_name = model_name
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return hash-based pseudo-embeddings for testing."""
        embeddings = []
        for text in texts:
            # Create deterministic pseudo-embedding from text hash
            h = hash(text) % (10**8)
            vec = [(h >> i) & 1 for i in range(128)]
            embeddings.append(vec)
        return embeddings
    
    def cosine_distance(self, a: str, b: str) -> float:
        """Simple distance: 0 if same, 1 if different."""
        return 0.0 if a == b else 0.5

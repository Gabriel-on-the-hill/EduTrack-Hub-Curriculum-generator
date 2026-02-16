"""
Grounding Verifier (Phase 5 Blocker)

Anti-Hallucination mechanism that strictly enforces content grounding.
Every sentence in the generated output must be grounded in the source competencies.

Invariants:
- K-12: 100% of sentences must be grounded.
- University: >= 95% of sentences must be grounded (ungrounded are flagged).
"""

from dataclasses import dataclass, field
from typing import Literal

from src.synthetic.embeddings import get_embedding_provider
from src.synthetic.schemas import TopicWeight  # Reusing similar concept if needed, or just str


@dataclass
class GroundingCheckResult:
    """Result of a grounding check for a single sentence."""
    sentence: str
    is_grounded: bool
    source_competency_id: str | None
    confidence_score: float
    method: Literal["semantic", "citation", "none"]


@dataclass
class ArtifactGroundingReport:
    """Grounding report for a full artifact."""
    total_sentences: int
    grounded_count: int
    ungrounded_count: int
    grounding_rate: float
    ungrounded_sentences: list[str]
    verdict: Literal["PASS", "FAIL"]
    
    @property
    def is_clean(self) -> bool:
        return self.ungrounded_count == 0


class GroundingVerifier:
    """
    Verifies that generated text is grounded in atomic competencies.
    """
    
    def __init__(self, embedding_provider=None, similarity_threshold: float = 0.80):
        """
        Initialize the verifier.
        
        Args:
            embedding_provider: Provider for semantic matching
            similarity_threshold: Min cosine similarity to consider grounded
        """
        self.embedding_provider = embedding_provider or get_embedding_provider()
        
        # Adjust threshold for Jaccard/BoW fallback
        # 0.8 is too high for bag-of-words (requires near-duplicate text)
        if "jaccard-only" in self.embedding_provider.name():
            self.similarity_threshold = 0.3
        else:
            self.similarity_threshold = similarity_threshold
    
    def verify_artifact(
        self,
        artifact_text: str,
        competencies: list[dict],  # list of {'id': str, 'text': str}
        mode: Literal["k12", "university"] = "k12",
    ) -> ArtifactGroundingReport:
        """
        Verify grounding for an entire artifact.
        
        Args:
            artifact_text: Generated content
            competencies: Source competencies to validate against
            mode: Validation strictness mode
        
        Returns:
            Detailed grounding report
        """
        sentences = self._split_sentences(artifact_text)
        if not sentences:
            return ArtifactGroundingReport(0, 0, 0, 0.0, [], "PASS")
            
        results = []
        
        # Embed competencies and sentences TOGETHER to ensure
        # consistent vector dimensions (critical for JaccardOnlyProvider
        # which builds vocabulary per call)
        comp_texts = [c['text'] for c in competencies]
        all_texts = comp_texts + sentences
        all_embeddings = self.embedding_provider.embed(all_texts)
        
        comp_embeddings = all_embeddings[:len(comp_texts)]
        sent_embeddings = all_embeddings[len(comp_texts):]
        
        for i, sentence in enumerate(sentences):
            # 1. Check for specific Citation IDs (Fast path)
            # if self._has_citation(sentence, competencies): ...
            
            # 2. Check Semantic Match
            best_match = self._find_best_match(
                sent_embeddings[i], 
                comp_embeddings, 
                competencies
            )
            
            is_grounded = best_match['score'] >= self.similarity_threshold
            
            results.append(GroundingCheckResult(
                sentence=sentence,
                is_grounded=is_grounded,
                source_competency_id=best_match['id'] if is_grounded else None,
                confidence_score=best_match['score'],
                method="semantic" if is_grounded else "none"
            ))
            
        # Calculate stats
        grounded_count = sum(1 for r in results if r.is_grounded)
        total = len(sentences)
        rate = grounded_count / total if total > 0 else 0.0
        
        ungrounded = [r.sentence for r in results if not r.is_grounded]
        
        # Verdict logic
        if mode == "k12":
            verdict = "PASS" if len(ungrounded) == 0 else "FAIL"
        else:
            verdict = "PASS" if rate >= 0.95 else "FAIL"
        
        return ArtifactGroundingReport(
            total_sentences=total,
            grounded_count=grounded_count,
            ungrounded_count=len(ungrounded),
            grounding_rate=rate,
            ungrounded_sentences=ungrounded,
            verdict=verdict
        )
    
    def _split_sentences(self, text: str) -> list[str]:
        """Simple sentence splitter."""
        # TODO: Use specific NLP splitter in production
        import re
        # Basic split by .!? followed by space or end of line
        raw = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in raw if len(s.strip()) > 10]  # Ignore tiny fragments
    
    def _find_best_match(self, sent_emb: list[float], comp_embs: list[list[float]], competencies: list[dict]) -> dict:
        """Find best semantic match using pre-computed embeddings."""
        import numpy as np
        
        best_score = -1.0
        best_comp = None
        
        # Basic cosine similarity
        sent_vec = np.array(sent_emb)
        norm_sent = np.linalg.norm(sent_vec)
        
        if norm_sent == 0:
            return {'id': None, 'score': 0.0}
            
        for idx, comp_emb in enumerate(comp_embs):
            comp_vec = np.array(comp_emb)
            norm_comp = np.linalg.norm(comp_vec)
            
            if norm_comp == 0:
                continue
                
            score = np.dot(sent_vec, comp_vec) / (norm_sent * norm_comp)
            
            if score > best_score:
                best_score = float(score)
                best_comp = competencies[idx]
                
        return {'id': best_comp['id'] if best_comp else None, 'score': best_score}


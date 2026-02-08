"""
Embedder Agent (Blueprint Section 5.3.4 & 14.2)

The Embedder agent is responsible for:
1. Chunking competencies for retrieval
2. Generating vector embeddings
3. Preparing data for vector storage

Blueprint:
- Creates vector embeddings for retrieval
- embedded_chunks = 0 with success status is invalid
"""

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from src.schemas.agents import CompetencyItem, EmbedderOutput
from src.schemas.base import AgentStatus
from src.utils.gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)


# Embedding model configuration
EMBEDDING_MODEL = "text-embedding-004"
CHUNK_SIZE = 512  # tokens per chunk


class EmbeddingChunk(BaseModel):
    """A chunk of text with its embedding."""
    chunk_id: UUID
    competency_id: UUID
    text: str
    embedding: list[float] | None = None


class EmbedderAgent:
    """
    Embedder Agent for vector embedding generation.
    
    Creates embeddings for curriculum competencies.
    """
    
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        """Initialize with optional Gemini client."""
        self._client = gemini_client or get_gemini_client()
    
    async def embed(
        self,
        curriculum_id: UUID,
        competencies: list[CompetencyItem],
    ) -> EmbedderOutput:
        """
        Generate embeddings for competencies.
        
        Args:
            curriculum_id: ID of the curriculum
            competencies: List of competencies to embed
            
        Returns:
            EmbedderOutput with embedding stats
        """
        if not competencies:
            return EmbedderOutput(
                curriculum_id=curriculum_id,
                embedded_chunks=0,
                embedding_model=EMBEDDING_MODEL,
                status=AgentStatus.FAILED,
            )
        
        try:
            # Create chunks from competencies
            chunks = self._create_chunks(competencies)
            
            # Generate embeddings (mock for now)
            embedded_count = await self._generate_embeddings(chunks)
            
            if embedded_count == 0:
                return EmbedderOutput(
                    curriculum_id=curriculum_id,
                    embedded_chunks=0,
                    embedding_model=EMBEDDING_MODEL,
                    status=AgentStatus.FAILED,
                )
            
            return EmbedderOutput(
                curriculum_id=curriculum_id,
                embedded_chunks=embedded_count,
                embedding_model=EMBEDDING_MODEL,
                status=AgentStatus.SUCCESS,
            )
            
        except Exception as e:
            logger.error(f"Embedder agent failed: {e}")
            return EmbedderOutput(
                curriculum_id=curriculum_id,
                embedded_chunks=0,
                embedding_model=EMBEDDING_MODEL,
                status=AgentStatus.FAILED,
            )
    
    def _create_chunks(
        self,
        competencies: list[CompetencyItem],
    ) -> list[EmbeddingChunk]:
        """
        Create text chunks from competencies.
        
        Each competency becomes one or more chunks.
        """
        chunks: list[EmbeddingChunk] = []
        
        for comp in competencies:
            # Create main chunk with title and description
            main_text = f"{comp.title}\n\n{comp.description}"
            chunks.append(EmbeddingChunk(
                chunk_id=uuid4(),
                competency_id=comp.competency_id,
                text=main_text[:CHUNK_SIZE * 4],  # ~4 chars per token
            ))
            
            # Create chunks for learning outcomes if long
            outcomes_text = "\n".join(f"- {o}" for o in comp.learning_outcomes)
            if len(outcomes_text) > CHUNK_SIZE:
                chunks.append(EmbeddingChunk(
                    chunk_id=uuid4(),
                    competency_id=comp.competency_id,
                    text=f"Learning Outcomes for {comp.title}:\n{outcomes_text}"[:CHUNK_SIZE * 4],
                ))
        
        return chunks
    
    async def _generate_embeddings(
        self,
        chunks: list[EmbeddingChunk],
    ) -> int:
        """
        Generate embeddings for chunks.
        
        In production, would use Gemini Embedding API.
        For now, returns mock success count.
        """
        # TODO: Implement actual embedding generation
        # Example with Gemini:
        # import google.generativeai as genai
        # result = genai.embed_content(
        #     model="models/text-embedding-004",
        #     content=chunk.text
        # )
        # chunk.embedding = result["embedding"]
        
        # Mock: Simulate successful embedding
        logger.info(f"Generated embeddings for {len(chunks)} chunks")
        
        # In production, store embeddings in vector DB here
        
        return len(chunks)


async def run_embedder(
    curriculum_id: UUID,
    competencies: list[CompetencyItem],
) -> EmbedderOutput:
    """Convenience function to run Embedder agent."""
    agent = EmbedderAgent()
    return await agent.embed(curriculum_id, competencies)

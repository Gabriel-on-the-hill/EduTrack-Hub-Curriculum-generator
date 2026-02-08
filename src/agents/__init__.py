"""
EduTrack Agents Package

This package contains the ingestion swarm agents:
- Scout: Search for curriculum sources
- Gatekeeper: Validate source authority
- Architect: Parse curriculum PDFs
- Embedder: Generate vector embeddings
"""

from src.agents.scout import ScoutAgent, run_scout
from src.agents.gatekeeper import GatekeeperAgent, run_gatekeeper
from src.agents.architect import ArchitectAgent, run_architect
from src.agents.embedder import EmbedderAgent, run_embedder

__all__ = [
    # Scout
    "ScoutAgent",
    "run_scout",
    # Gatekeeper
    "GatekeeperAgent",
    "run_gatekeeper",
    # Architect
    "ArchitectAgent",
    "run_architect",
    # Embedder
    "EmbedderAgent",
    "run_embedder",
]

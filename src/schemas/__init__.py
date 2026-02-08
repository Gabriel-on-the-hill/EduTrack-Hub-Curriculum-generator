"""
EduTrack Schemas Package

Contains all Pydantic models as defined in Section 13 of the Blueprint.
These schemas are the authoritative data contracts for all agent I/O.

Schemas are law. If data does not match these schemas, the agent must fail fast.
"""

from src.schemas.request import NormalizedRequest
from src.schemas.jurisdiction import JurisdictionResolution
from src.schemas.vault import VaultLookupResult
from src.schemas.agents import (
    ScoutOutput,
    GatekeeperOutput,
    ArchitectOutput,
    EmbedderOutput,
)
from src.schemas.generation import GenerationRequest, GenerationOutput
from src.schemas.curriculum import Curriculum, Competency

__all__ = [
    "NormalizedRequest",
    "JurisdictionResolution",
    "VaultLookupResult",
    "ScoutOutput",
    "GatekeeperOutput",
    "ArchitectOutput",
    "EmbedderOutput",
    "GenerationRequest",
    "GenerationOutput",
    "Curriculum",
    "Competency",
]

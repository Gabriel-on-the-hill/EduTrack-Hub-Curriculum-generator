import re
from typing import List
from .schemas import ExtractedCompetency


def heuristic_extract(text: str) -> List[ExtractedCompetency]:
    lines = text.split("\n")
    competencies = []

    for idx, line in enumerate(lines):
        if re.match(r"^\d+\.", line.strip()) or line.strip().startswith("-"):
            competencies.append(
                ExtractedCompetency(
                    title=line.strip(),
                    description="",
                    learning_outcomes=[],
                    source_chunk_id=f"chunk_{idx}",
                )
            )
    return competencies

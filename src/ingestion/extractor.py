import re
from typing import List
from .schemas import ExtractedCompetency


def heuristic_extract(text: str) -> List[ExtractedCompetency]:
    lines = text.split("\n")
    competencies = []

    for idx, line in enumerate(lines):
        # Support for numbers, bullets, letters (a), (i), and Section headers
        if (re.match(r"^\d+\.", line.strip()) or 
            line.strip().startswith("-") or
            re.match(r"^[a-zA-Z]\)", line.strip()) or
            re.match(r"^[ivxlcdmIVXLCDM]+\)", line.strip()) or
            re.match(r"^(Section|Unit|Chapter|Module)\s+\w+", line.strip(), re.I)):
            competencies.append(
                ExtractedCompetency(
                    title=line.strip(),
                    description="",
                    learning_outcomes=[],
                    source_chunk_id=f"chunk_{idx}",
                )
            )
    return competencies

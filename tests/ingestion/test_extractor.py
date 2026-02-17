# tests/ingestion/test_extractor.py
from src.ingestion.extractor import heuristic_extract
from src.ingestion.schemas import ExtractedCompetency

def test_heuristic_extract_simple():
    text = "1. Introduction\n- Topic A\n2. Advanced\n- Topic B"
    comps = heuristic_extract(text)
    assert len(comps) >= 4
    assert comps[0].title == "1. Introduction"
    assert comps[2].title == "2. Advanced"
    assert isinstance(comps[0], ExtractedCompetency)

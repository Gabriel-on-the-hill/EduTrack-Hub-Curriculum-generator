# tests/ingestion/test_standardizer.py
from src.ingestion.standardizer import standardize_batch
from src.ingestion.llm_client import DummyLLMProvider
from src.ingestion.schemas import StandardizedCompetency

def test_standardize_batch_dummy():
    raw = [
        {"text":"- 1. Describe mitosis and meiosis", "source_chunk_id":"chunk-1"},
        {"text":"- 2. Understand photosynthesis", "source_chunk_id":"chunk-2"}
    ]
    provider = DummyLLMProvider()
    out = standardize_batch(raw, llm_provider=provider)
    assert isinstance(out, list)
    assert len(out) >= 1
    assert all(isinstance(i, StandardizedCompetency) for i in out)
    # The dummy provider echoes back and assigns source_chunk_id based on index, 
    # OR it tries to parse what we sent. 
    # Our updated DummyLLMProvider splits lines and assigns chunk-{i}.
    # Given the input format to dummy is prompt string, we check the result structure.
    
    item = out[0]
    assert item.action_verb in ["Describe", "Identify"]
    assert item.extraction_confidence > 0.0

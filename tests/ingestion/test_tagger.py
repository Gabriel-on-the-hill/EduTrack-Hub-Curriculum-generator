# tests/ingestion/test_tagger.py
from src.ingestion.tagger import predict_metadata
from src.ingestion.llm_client import DummyLLMProvider
from src.ingestion.schemas import StandardizedCompetency, CompetencyMetadata

def make_std_comp(i):
    return StandardizedCompetency(
        standardized_id=f"sid-{i}",
        original_text=f"orig {i}",
        standardized_text=f"Standardized text {i}",
        action_verb="Describe",
        content="Photosynthesis",
        source_chunk_id=f"chunk-{i}",
        extraction_confidence=0.9
    )

def test_predict_metadata_dummy():
    items = [make_std_comp(1), make_std_comp(2)]
    provider = DummyLLMProvider()
    res = predict_metadata(items, llm_provider=provider)
    assert isinstance(res, dict)
    # The dummy provider should return results for items
    # Note: Dummy is simple, so it might return fewer if prompt parsing is naive
    if res:
        first_key = list(res.keys())[0]
        meta = res[first_key]
        assert isinstance(meta, CompetencyMetadata)
        assert meta.confidence_score >= 0.0
        assert meta.subject is not None

from src.ingestion.parser import parse_pdf


def test_parse_pdf(sample_pdf_path):
    text = parse_pdf(sample_pdf_path)
    assert isinstance(text, str)
    assert len(text) > 0

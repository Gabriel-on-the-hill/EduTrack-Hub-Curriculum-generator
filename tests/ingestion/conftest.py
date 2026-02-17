import pytest
import os


@pytest.fixture
def sample_pdf_path():
    return os.path.join("tests", "fixtures", "sample_curriculum.pdf")

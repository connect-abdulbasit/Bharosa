import pytest


@pytest.fixture(autouse=True)
def _no_llm_by_default(monkeypatch):
    """No test may reach the network or need a key, even when the developer's shell has LLM_API_KEY and LLM_MODEL set.
    Tests that exercise the LLM path set the environment or monkeypatch bharosa_ai.llm themselves."""
    monkeypatch.setenv("AI_USE_LLM", "0")
    monkeypatch.setenv("AI_USE_ML", "0")  # the rule tests test the rules; the hybrid has its own tests (test_classify_ml.py)
    monkeypatch.setenv("AI_USE_OCR", "0")  # the quality-gate tests must not depend on an OCR engine being installed (test_ocr.py, test_document_ocr.py)

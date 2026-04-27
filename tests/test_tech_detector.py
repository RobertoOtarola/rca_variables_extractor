"""
test_tech_detector.py — Tests unitarios para tech_detector.py.

Valida la detección de tecnología con respuestas válidas, inválidas,
con whitespace y excepciones de API.
"""

import pytest
from unittest.mock import MagicMock
from rca_extractor.utils.tech_detector import detect_technology, TECH_VALUES


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.upload_pdf.return_value = MagicMock()
    client.delete_file.return_value = None
    return client


@pytest.mark.parametrize("response,expected", [
    ("Fotovoltaica", "Fotovoltaica"),
    ("Eólica", "Eólica"),
    ("CSP", "CSP"),
    ("Eólica + Fotovoltaica", "Eólica + Fotovoltaica"),
    ("Fotovoltaica + CSP", "Fotovoltaica + CSP"),
    ("  Fotovoltaica  ", "Fotovoltaica"),   # whitespace
    ("Solar", "Desconocido"),               # respuesta inválida
    ("", "Desconocido"),                    # vacío
])
def test_detect_technology_responses(mock_client, tmp_path, response, expected):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_client.generate.return_value = response
    result = detect_technology(pdf, mock_client)
    assert result == expected


def test_detect_technology_exception_returns_desconocido(mock_client, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_client.generate.side_effect = Exception("API error")
    result = detect_technology(pdf, mock_client)
    assert result == "Desconocido"


def test_detect_technology_cleanup_on_success(mock_client, tmp_path):
    """Verifica que delete_file se llama siempre, incluso si generate tiene éxito."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_client.generate.return_value = "Eólica"
    detect_technology(pdf, mock_client)
    mock_client.delete_file.assert_called_once()


def test_detect_technology_cleanup_on_generate_error(mock_client, tmp_path):
    """Verifica que delete_file se llama incluso si generate falla."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_client.generate.side_effect = RuntimeError("Gemini error")
    detect_technology(pdf, mock_client)
    mock_client.delete_file.assert_called_once()


def test_tech_values_completeness():
    """Verifica que TECH_VALUES contiene las 5 tecnologías esperadas."""
    assert len(TECH_VALUES) == 5
    assert "Fotovoltaica" in TECH_VALUES
    assert "Eólica" in TECH_VALUES
    assert "CSP" in TECH_VALUES

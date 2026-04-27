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
def test_detect_technology_responses(mock_client, response, expected):
    mock_client.generate.return_value = response
    result = detect_technology(mock_client, "test.pdf", file_ref="dummy_ref")
    assert result == expected


def test_detect_technology_images(mock_client):
    mock_client.generate_from_images.return_value = "Eólica"
    result = detect_technology(mock_client, "test.pdf", images=[b"dummy_image"])
    assert result == "Eólica"
    mock_client.generate_from_images.assert_called_once()


def test_detect_technology_exception_returns_desconocido(mock_client):
    mock_client.generate.side_effect = Exception("API error")
    result = detect_technology(mock_client, "test.pdf", file_ref="dummy_ref")
    assert result == "Desconocido"


def test_detect_technology_missing_args(mock_client):
    result = detect_technology(mock_client, "test.pdf")
    assert result == "Desconocido"


def test_tech_values_completeness():
    """Verifica que TECH_VALUES contiene las 5 tecnologías esperadas."""
    assert len(TECH_VALUES) == 5
    assert "Fotovoltaica" in TECH_VALUES
    assert "Eólica" in TECH_VALUES
    assert "CSP" in TECH_VALUES

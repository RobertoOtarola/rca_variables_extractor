import pytest
from unittest.mock import MagicMock, patch

from rca_extractor.tools.snippet_api_key import main as snippet_main
from rca_extractor.tools.list_models import main as list_models_main

@patch("rca_extractor.tools.snippet_api_key.client")
def test_snippet_api_key_main(mock_client):
    # Setup mock
    mock_model = MagicMock()
    mock_model.name = "gemini-2.5-flash"
    mock_model.display_name = "Gemini 2.5 Flash"
    mock_client.models.get.return_value = mock_model
    
    mock_response = MagicMock()
    mock_response.text = "Conexión exitosa"
    mock_client.models.generate_content.return_value = mock_response
    
    # Run main
    snippet_main()
    
    # Verify
    mock_client.models.get.assert_called_once()
    mock_client.models.generate_content.assert_called_once()

@patch("rca_extractor.tools.list_models.client")
def test_list_models_main(mock_client):
    # Setup mock
    mock_model = MagicMock()
    mock_model.name = "models/gemini-2.5-flash"
    mock_model.display_name = "Gemini 2.5 Flash"
    mock_client.models.list.return_value = [mock_model]
    
    # Run main
    list_models_main()
    
    # Verify
    mock_client.models.list.assert_called_once()

@patch("rca_extractor.tools.snippet_api_key.client")
def test_snippet_api_key_error_handling(mock_client):
    """Verifica que main() maneja errores de API sin explotar."""
    mock_client.models.get.side_effect = Exception("UNAVAILABLE")
    
    # No debería lanzar excepción no capturada si el script tiene un bloque try-except en main
    # Si no lo tiene, este test fallará y nos dirá que debemos agregarlo.
    try:
        snippet_main()
    except Exception as exc:
        pytest.fail(f"snippet_api_key.main() lanzó una excepción no capturada: {exc}")

@patch("rca_extractor.tools.list_models.client")
def test_list_models_error_handling(mock_client):
    """Verifica que main() maneja errores de API sin explotar."""
    mock_client.models.list.side_effect = Exception("PERMISSION_DENIED")
    
    try:
        list_models_main()
    except Exception as exc:
        pytest.fail(f"list_models.main() lanzó una excepción no capturada: {exc}")

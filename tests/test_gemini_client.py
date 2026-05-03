import pytest
import httpx
from unittest.mock import Mock, patch

from rca_extractor.core.gemini_client import GeminiClient, _classify_error, _compute_wait
from google.genai import types

class TestGeminiClient:
    
    def test_classify_error(self):
        # Error quotas
        assert _classify_error("429 Too Many Requests") == "quota"
        assert _classify_error("RESOURCE_EXHAUSTED") == "quota"
        
        # Errores fatales
        assert _classify_error("400 Bad Request") == "fatal"
        assert _classify_error("INVALID_ARGUMENT") == "fatal"
        
        # Errores de red
        assert _classify_error("The read operation timed out") == "network_timeout"
        assert _classify_error("deadline_exceeded") == "network_timeout"
        assert _classify_error("[Errno 54] Connection reset") == "network_timeout"
        
        # Errores transitorios
        assert _classify_error("503 Service Unavailable") == "transient"
        assert _classify_error("INTERNAL") == "transient"

    def test_compute_wait(self):
        # Quota: 65s base, attempt 0 -> min(65*1, max_backoff) -> 65 * jitter
        wait = _compute_wait("quota", 0, "429")
        assert 58 <= wait <= 72
        
        # Network timeout: 30s base, attempt 1 -> min(30*2, max_backoff) -> 60 * jitter
        wait = _compute_wait("network_timeout", 1, "timed out")
        assert 54 <= wait <= 66
        
        # API hints "retry after X"
        wait = _compute_wait("transient", 0, "retry after 100")
        assert 91.8 <= wait <= 112.2 # 102 * jitter

    @patch("rca_extractor.core.gemini_client.genai.Client")
    def test_generate_success(self, mock_client_cls):
        # Setup mock
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_response = Mock()
        mock_response.text = '{"variable": "valor"}'
        mock_client.models.generate_content.return_value = mock_response

        # Init client
        client = GeminiClient(api_key="fake", model="gemini-fake")
        
        # Test generate
        file_ref = types.File(name="files/123", uri="https://fake")
        result = client.generate("prompt", file_ref)
        
        assert result == '{"variable": "valor"}'
        mock_client.models.generate_content.assert_called_once()

    @patch("time.sleep")
    @patch("rca_extractor.core.gemini_client.genai.Client")
    def test_generate_network_timeout_retries(self, mock_client_cls, mock_sleep):
        # Setup mock to raise NetworkError then succeed
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        
        mock_response = Mock()
        mock_response.text = '{"variable": "ok"}'
        
        # Fail first 2 times, succeed on 3rd
        mock_client.models.generate_content.side_effect = [
            httpx.TimeoutException("Read operation timed out"),
            httpx.TimeoutException("Deadline exceeded"),
            mock_response
        ]

        client = GeminiClient(api_key="fake", model="gemini-fake")
        file_ref = types.File(name="files/123", uri="https://fake")
        
        result = client.generate("prompt", file_ref, retries=4)
        
        assert result == '{"variable": "ok"}'
        assert mock_client.models.generate_content.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    @patch("rca_extractor.core.gemini_client.genai.Client")
    def test_generate_fatal_error(self, mock_client_cls, mock_sleep):
        # Setup mock to raise fatal error
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("400 Bad Request")

        client = GeminiClient(api_key="fake", model="gemini-fake")
        file_ref = types.File(name="files/123", uri="https://fake")
        
        with pytest.raises(RuntimeError, match="Error fatal de Gemini"):
            client.generate("prompt", file_ref, retries=4)
            
        # Should fail immediately without retries
        assert mock_client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

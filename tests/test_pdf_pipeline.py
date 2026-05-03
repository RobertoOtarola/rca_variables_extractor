import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from rca_extractor.core.pdf_pipeline import RCAExtractor

class TestRCAExtractor:
    
    @patch("rca_extractor.core.pdf_pipeline.detect_scanned")
    @patch("rca_extractor.core.pdf_pipeline.pdf_to_images")
    @patch("rca_extractor.core.pdf_pipeline.detect_technology")
    @patch("rca_extractor.core.pdf_pipeline.GeminiClient")
    def test_process_pdf_scanned(self, mock_client_cls, mock_detect, mock_pdf_to_images, mock_detect_scanned, tmp_path):
        # Setup mocks
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.upload_pdf.return_value = Mock(name="file_ref")
        mock_client.generate_from_images.return_value = '```json\n{"tipo_de_generacion": "Desconocido"}\n```'
        
        # Simulate PDF converted to images
        mock_detect_scanned.return_value = True
        mock_pdf_to_images.return_value = [b"img1", b"img2"]
        mock_detect.return_value = "Desconocido"
        
        extractor = RCAExtractor(model="test-model")
        
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"dummy pdf")
        
        variables = [{"variable": "tipo_de_generacion", "tipo": "str", "descripcion": "test"}]
        
        result = extractor.process_pdf(pdf_path, variables)
        
        assert result is not None
        assert result["tipo_de_generacion"] == "Desconocido"
        assert result["escaneado"] == "sí"
        
        assert mock_pdf_to_images.call_count == 2
        mock_client.generate_from_images.assert_called_once()
        mock_client.upload_pdf.assert_not_called()
        mock_detect.assert_called_once_with(
            mock_client,
            "test.pdf",
            file_ref=None,
            images=[b"img1", b"img2"],
            retries=extractor.detect_retries,
            base_delay=extractor.retry_base_delay
        )

    @patch("rca_extractor.core.pdf_pipeline.detect_scanned")
    @patch("rca_extractor.core.pdf_pipeline.pdf_to_images")
    @patch("rca_extractor.core.pdf_pipeline.detect_technology")
    @patch("rca_extractor.core.pdf_pipeline.GeminiClient")
    def test_process_pdf_native(self, mock_client_cls, mock_detect, mock_pdf_to_images, mock_detect_scanned, tmp_path):
        # Setup mocks
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        
        # Simulate native PDF
        mock_detect_scanned.return_value = False
        mock_pdf_to_images.return_value = []
        mock_detect.return_value = "Eólica"
        
        mock_file_ref = Mock(name="file_ref")
        mock_client.upload_pdf.return_value = mock_file_ref
        mock_client.generate.return_value = '```json\n{"tipo_de_generacion": "Eólica"}\n```'
        
        extractor = RCAExtractor(model="test-model")
        
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"dummy pdf")
        
        variables = [{"variable": "tipo_de_generacion", "tipo": "str", "descripcion": "test"}]
        
        result = extractor.process_pdf(pdf_path, variables)
        
        assert result is not None
        assert result["tipo_de_generacion"] == "Eólica"
        assert result["escaneado"] == "no"
        assert result["tecnologia_detectada"] == "Eólica"
        
        mock_client.upload_pdf.assert_called_once()
        mock_detect.assert_called_once_with(
            mock_client,
            "test.pdf",
            file_ref=mock_file_ref,
            images=None,
            retries=extractor.detect_retries,
            base_delay=extractor.retry_base_delay
        )
        mock_client.generate.assert_called_once()
        mock_client.delete_file.assert_called_once_with(mock_file_ref)

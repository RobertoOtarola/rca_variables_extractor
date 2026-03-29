import pytest
import requests
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from rca_extractor.tools.rca_scraper import find_doc_links, download_file

@pytest.fixture
def sample_html():
    return """
    <html>
        <body>
            <table>
                <tr>
                    <td><a href="/documentos/visor.php?id=1">Resolución de Calificación Ambiental</a></td>
                </tr>
                <tr>
                    <td><a href="/archivos/proceso.pdf">RCA Definitiva</a></td>
                </tr>
                <tr>
                    <td><a href="/expediente/ficha.php?id=123">Ficha</a></td>
                </tr>
            </table>
        </body>
    </html>
    """

def test_find_doc_links_basic(sample_html):
    pattern = r"RCA|Resolución de Calificación Ambiental"
    links = find_doc_links(sample_html, pattern)
    assert len(links) == 2
    assert "/documentos/visor.php?id=1" in links
    assert "/archivos/proceso.pdf" in links

def test_find_doc_links_no_match(sample_html):
    pattern = r"ICE|Informe Consolidado"
    links = find_doc_links(sample_html, pattern)
    assert len(links) == 0

def test_download_file_rejects_html(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.content = b"<html>Sesion expirada</html>"
    mock_session.get.return_value = mock_response
    
    output_path = tmp_path / "test.pdf"
    result = download_file("https://example.com/doc.pdf", output_path, session=mock_session)
    
    assert result is False
    assert not output_path.exists()

def test_download_file_valid_pdf(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.content = b"%PDF-1.4 dummy content" * 100 # > 512 bytes
    mock_session.get.return_value = mock_response
    
    output_path = tmp_path / "valid.pdf"
    result = download_file("https://example.com/valid.pdf", output_path, session=mock_session)
    
    assert result is True
    assert output_path.exists()
    assert output_path.read_bytes() == mock_response.content

def test_download_file_too_small(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.content = b"too small"
    mock_session.get.return_value = mock_response
    
    output_path = tmp_path / "small.pdf"
    with pytest.raises(ValueError, match="Respuesta demasiado pequeña"):
        download_file("https://example.com/small.pdf", output_path, session=mock_session)

def test_download_file_propagates_http_error():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    mock_session.get.return_value = mock_response
    
    with pytest.raises(requests.HTTPError):
        download_file("https://example.com/403.pdf", Path("dummy.pdf"), session=mock_session)

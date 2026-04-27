import pytest
from pathlib import Path
from rca_extractor.core.pdf_pipeline import RCAExtractor
from rca_extractor.utils.prompt_builder import load_variables
from rca_extractor import config

@pytest.mark.integration
@pytest.mark.skipif(not Path("data/raw").exists(), reason="Corpus real no disponible")
def test_integration_pipeline_real_pdfs():
    """
    Test de integración que procesa 4 PDFs reales para validar el flujo completo.
    Requiere GEMINI_API_KEY real y acceso a la carpeta data/raw/.
    """
    pdfs_to_test = {
        "Eólico Nativo": "1706.pdf",
        "Eólico Escaneado": "1682.pdf",
        "FV Nativo": "1680.pdf",
        "FV Escaneado": "1656.pdf"
    }

    base_dir = Path("data/raw")
    extractor = RCAExtractor()
    variables = load_variables(config.VARIABLES_FILE, config.VARIABLES_COLUMN)

    results = []
    for desc, filename in pdfs_to_test.items():
        pdf_path = base_dir / filename
        if not pdf_path.exists():
            pytest.skip(f"Archivo {filename} no encontrado para test de integración")

        try:
            data = extractor.process_pdf(pdf_path, variables)
            results.append(data)
            
            assert data["archivo"] == filename
            assert "tecnologia_detectada" in data
            assert data["tecnologia_detectada"] != "Desconocido"
            assert "prompt_version" in data
            
            # Verificar que se extrajeron variables (más allá de los metadatos)
            keys_extracted = len([k for k, v in data.items() if v is not None]) - 4
            assert keys_extracted > 5
            
        except Exception as e:
            pytest.fail(f"Falla integración en {desc} ({filename}): {e}")

    assert len(results) == 4

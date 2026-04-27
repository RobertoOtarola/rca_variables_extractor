import logging
import os
import sys
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from rca_extractor.core.pdf_pipeline import RCAExtractor
from rca_extractor.utils.prompt_builder import load_variables
from rca_extractor import config

def main():
    pdfs_to_test = {
        "Eólico Nativo": "1706.pdf",
        "Eólico Escaneado": "1682.pdf",
        "FV Nativo": "1680.pdf",
        "FV Escaneado": "1656.pdf"
    }

    base_dir = Path("data/raw")
    if not base_dir.exists():
        base_dir = Path("data/scraped")

    extractor = RCAExtractor()
    variables = load_variables(config.VARIABLES_FILE, config.VARIABLES_COLUMN)

    print("=== Iniciando Validación de Integración (4 PDFs Reales) ===")
    
    for desc, filename in pdfs_to_test.items():
        pdf_path = base_dir / filename
        if not pdf_path.exists():
            print(f"❌ Error: {filename} ({desc}) no se encontró en {base_dir}")
            continue

        print(f"\nProcesando {desc}: {filename}")
        try:
            data = extractor.process_pdf(pdf_path, variables)
            tech = data.get("tecnologia_detectada", "N/A")
            version = data.get("prompt_version", "N/A")
            keys_extracted = len([k for k, v in data.items() if v is not None]) - 4
            
            print(f"✅ Éxito! Tecnología: {tech} | Versión: {version} | Variables extraídas: {keys_extracted}")
        except Exception as e:
            print(f"❌ Falló el procesamiento de {filename}: {e}")

if __name__ == "__main__":
    main()

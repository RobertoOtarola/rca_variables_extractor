"""
pdf_utils.py — Utilidades compartidas para inspección de PDFs.
Importado por pdf_pipeline.py y tools/check_pdfs.py.
"""

import logging
import pypdf
from pathlib import Path

log = logging.getLogger("rca_extractor")

SCANNED_CHARS_THRESHOLD = 50
SCANNED_SAMPLE_PAGES    = 5


def is_scanned_pdf(
    reader: "pypdf.PdfReader",
    sample_pages: int = SCANNED_SAMPLE_PAGES,
    threshold: int = SCANNED_CHARS_THRESHOLD,
) -> tuple[bool, str]:
    """
    Determina si un PDF está escaneado como imagen (sin capa de texto).
    Muestrea hasta `sample_pages` páginas distribuidas uniformemente.
    Devuelve (es_escaneado, mensaje).
    """
    num_pages = len(reader.pages)
    if num_pages == 0:
        return False, ""

    if num_pages <= sample_pages:
        indices = list(range(num_pages))
    else:
        step = num_pages / sample_pages
        indices = [int(i * step) for i in range(sample_pages)]

    total_chars  = 0
    pages_sampled = 0

    for idx in indices:
        try:
            text = reader.pages[idx].extract_text() or ""
            total_chars += len(text.strip())
            pages_sampled += 1
        except Exception:
            pass

    if pages_sampled == 0:
        return False, ""

    avg_chars = total_chars / pages_sampled

    if avg_chars < threshold:
        return True, (
            f"Promedio {avg_chars:.0f} chars/página en {pages_sampled} "
            f"páginas muestreadas (umbral: {threshold}) — PDF escaneado como imagen"
        )

    return False, ""


def detect_scanned(pdf_path: Path) -> bool:
    """
    Wrapper de conveniencia: abre el PDF y llama is_scanned_pdf.
    Devuelve True si el PDF es escaneado.
    """
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f, strict=False)
            scanned, _ = is_scanned_pdf(reader)
            return scanned
    except Exception as exc:
        log.warning(
            "No se pudo determinar si %s es escaneado: %s. Asumiendo texto.",
            pdf_path.name, exc,
        )
        return False

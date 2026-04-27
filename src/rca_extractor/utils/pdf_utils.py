"""
pdf_utils.py — Utilidades compartidas para inspección de PDFs.
Importado por pdf_pipeline.py y tools/check_pdfs.py.
"""

import logging
import pypdf
from pathlib import Path

log = logging.getLogger("rca_extractor")

SCANNED_CHARS_THRESHOLD = 50
SCANNED_SAMPLE_PAGES = 5


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

    total_chars = 0
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
            pdf_path.name,
            exc,
        )
        return False


def pdf_to_images(pdf_path: Path | str, dpi: int = 150, max_pages: int | None = None) -> list[bytes]:
    """
    Convierte un PDF a una lista de imágenes PNG (como bytes).
    Si max_pages está definido, solo convierte hasta esa cantidad de páginas.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        raise RuntimeError("pymupdf no está instalado. Ejecuta: pip install pymupdf")

    log.debug("Convirtiendo PDF a imágenes: %s (dpi=%d, max_pages=%s)", pdf_path, dpi, max_pages)

    doc = fitz.open(str(pdf_path))
    images: list[bytes] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    
    limit = min(len(doc), max_pages) if max_pages else len(doc)

    for i in range(limit):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
        images.append(pix.tobytes("png"))

    doc.close()
    return images

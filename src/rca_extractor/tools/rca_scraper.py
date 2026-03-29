"""
rca_scraper.py — Herramienta para descargar documentos (RCA e ICE) desde el SEIA.
Soporta descarga individual por id_expediente o masiva desde archivos CSV/Excel/ODS.
"""

import time
import argparse
import re
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

from rca_extractor.config import (
    SCRAPED_DIR,
    SCRAPER_DELAY,
    SCRAPER_CHECKPOINT,
    SCRAPER_LOG_FILE,
)
from rca_extractor.utils.logger import get_logger
from rca_extractor.utils.checkpoint import Checkpoint

log = get_logger("rca_scraper", log_file=SCRAPER_LOG_FILE)

# --- CONFIGURACIÓN ---
BASE_URL = "https://seia.sea.gob.cl"
# Endpoint XHR interno del SEIA: devuelve la tabla de documentos de un expediente
# sin cargar toda la ficha. Más liviano pero no documentado públicamente.
# Alternativa si cambia: /expediente/expedientesEvaluacion.php?modo=ficha&id_expediente={}
FICHA_URL = f"{BASE_URL}/expediente/xhr_documentos.php?id_expediente={{}}"
DOC_VIEWER_URL = f"{BASE_URL}/documentos/documento.php?idDocumento={{}}"
XML_DOWNLOAD_URL = f"{BASE_URL}/documentos/getXmlFile?docId={{}}"

# User-Agent identificable (Investigación CEDEUS UC)
HEADERS = {
    "User-Agent": (
        "RCA-Extractor/0.6 (Investigación ERNC — CEDEUS UC; "
        "https://github.com/RobertoOtarola/rca_variables_extractor)"
    )
}


def create_session() -> requests.Session:
    """Crea una sesión de requests configurada con los headers base."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get_project_html(url: str, session: requests.Session | None = None) -> str:
    """Obtiene el HTML de una página del proyecto."""
    s = session or create_session()
    res = s.get(url, timeout=30)
    res.encoding = res.apparent_encoding # SEIA suele usar ISO-8859-1
    res.raise_for_status()
    return res.text


def find_doc_links(html: str, pattern: str) -> list[str]:
    """Busca hrefs de <a> cuyo texto visible coincida con el patrón (RCA o ICE)."""
    soup = BeautifulSoup(html, "html.parser")
    return [
        a["href"]
        for a in soup.find_all("a", href=True)
        if re.search(pattern, a.get_text(strip=True), re.IGNORECASE)
    ]


def download_file(
    url: str,
    output_path: Path,
    referer: str | None = None,
    session: requests.Session | None = None,
    min_bytes: int = 512,
) -> bool:
    """Descarga url -> output_path. Retorna False si el servidor devuelve HTML.
    Propaga HTTPError y otras excepciones al caller."""
    s = session or create_session()
    headers = {"Referer": referer} if referer else {}

    log.debug("Descargando: %s", url)
    response = s.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        return False

    content = response.content
    if len(content) < min_bytes:
        raise ValueError(f"Respuesta demasiado pequeña ({len(content)} bytes) para {url}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return True


def get_doc_id_from_viewer(viewer_url: str) -> str | None:
    """Extrae el idDocumento de una URL de visor."""
    match = re.search(r"idDocumento=(\d+)", viewer_url)
    return match.group(1) if match else None


def process_id(
    id_expediente: str,
    doc_patterns: dict[str, str],
    session: requests.Session | None = None,
) -> None:
    """Procesa un id_expediente buscando y descargando los documentos solicitados."""
    log.info("Procesando id_expediente: %s", id_expediente)
    s = session or create_session()
    
    try:
        html = get_project_html(FICHA_URL.format(id_expediente), session=s)
        target_dir = SCRAPED_DIR / id_expediente
        
        for doc_type, pattern in doc_patterns.items():
            all_links = find_doc_links(html, pattern)
            
            if not all_links:
                log.warning("    ❌ No se encontró %s", doc_type)
                continue
            
            found = False
            # Usamos dict.fromkeys para de-duplicar manteniendo el orden
            links_to_try = reversed(list(dict.fromkeys(all_links)))
            
            for link in links_to_try:
                full_url = urljoin(BASE_URL, link)
                
                # Caso 1: Link directo a PDF
                if full_url.lower().endswith(".pdf"):
                    out_path = target_dir / f"{doc_type}.pdf"
                    if download_file(full_url, out_path, referer=FICHA_URL.format(id_expediente), session=s):
                        log.info("    ✅ %s descargado (PDF Directo)", doc_type)
                        found = True
                        break

                # Caso 2: Link a visor /documentos/documento.php
                elif "documento.php" in full_url:
                    log.debug("      - Explorando visor: %s", full_url)
                    try:
                        inner_html = get_project_html(full_url, session=s)
                        inner_links = find_doc_links(inner_html, r"\.pdf|\.xml|descargar|archivo")
                        
                        for i_link in inner_links:
                            i_full_url = urljoin(full_url, i_link)
                            ext = "pdf" if ".pdf" in i_full_url.lower() else "xml"
                            out_path = target_dir / f"{doc_type}.{ext}"
                            
                            if download_file(i_full_url, out_path, referer=full_url, session=s):
                                log.info("    ✅ %s descargado (desde visor: %s)", doc_type, ext)
                                found = True
                                break
                        if found:
                            break
                    except Exception as e:
                        log.warning("      ⚠️  Error en visor %s: %s", full_url, e)

            if not found:
                # Caso 3: Fallback XML — solo si no se encontró PDF arriba
                log.debug("      - Intentando fallback XML para %s", doc_type)
                for link in reversed(list(dict.fromkeys(all_links))):
                    doc_id = get_doc_id_from_viewer(urljoin(BASE_URL, link))
                    if doc_id:
                        xml_url = XML_DOWNLOAD_URL.format(doc_id)
                        xml_path = target_dir / f"{doc_type}.xml"
                        if download_file(xml_url, xml_path, referer=urljoin(BASE_URL, link), session=s):
                            log.info("    ✅ %s descargado (XML Directo)", doc_type)
                            found = True
                            break
            
            if not found:
                log.error("    ❌ Falló la descarga de %s", doc_type)
            
    except Exception as e:
        log.error("    💥 Error procesando %s: %s", id_expediente, e)


def main():
    parser = argparse.ArgumentParser(description="Scraper de documentos RCA/ICE desde SEIA.")
    parser.add_argument("--id", help="ID de expediente individual")
    parser.add_argument("--input", help="Archivo (CSV/XLSX/ODS) con lista de IDs")
    parser.add_argument(
        "--delay",
        type=float,
        default=SCRAPER_DELAY,
        help=f"Segundos base entre peticiones (default: {SCRAPER_DELAY})",
    )
    parser.add_argument("--ice", action="store_true", help="Descargar también el ICE")
    parser.add_argument(
        "--force", action="store_true", help="Ignorar checkpoint y re-descargar todo"
    )

    args = parser.parse_args()

    # ── Preparativos ───────────────────────────────────────────────────────
    checkpoint = Checkpoint(SCRAPER_CHECKPOINT)
    session = create_session()

    doc_patterns = {"RCA": r"RCA|Resoluci[oó]n de Calificaci[oó]n Ambiental"}
    if args.ice:
        doc_patterns["ICE"] = r"ICE|Informe Consolidado"

    ids = []
    if args.id:
        ids.append(args.id)
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            log.error("Archivo no encontrado: %s", args.input)
            return

        ext = path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        elif ext == ".ods":
            df = pd.read_excel(path, engine="odf")
        else:
            log.error("Formato no soportado: %s", ext)
            return

        if "id_expediente" not in df.columns:
            log.error("Columna 'id_expediente' no encontrada en %s", args.input)
            return

        ids = df["id_expediente"].dropna().astype(str).tolist()

    if not ids:
        log.info("💡 Usa --id o --input para especificar qué descargar.")
        return

    log.info("🚀 Iniciando descarga de %d expedientes...", len(ids))

    for idx, id_exp in enumerate(ids):
        # ── Checkpoint ─────────────────────────────────────────────────────
        if not args.force and checkpoint.is_done(id_exp):
            log.info("Saltando %s (ya procesado)", id_exp)
            continue

        try:
            process_id(id_exp, doc_patterns, session=session)
            checkpoint.mark_ok(id_exp)
        except Exception as exc:
            log.error("Fallo procesando %s: %s", id_exp, exc)
            checkpoint.mark_error(id_exp, str(exc))

        # ── Delay con Jitter ───────────────────────────────────────────────
        if idx < len(ids) - 1:
            actual_delay = args.delay + random.uniform(-0.5, 1.5)
            log.debug("Esperando %.2fs...", actual_delay)
            time.sleep(max(1.0, actual_delay))

    log.info("✨ Proceso finalizado.")


if __name__ == "__main__":
    main()

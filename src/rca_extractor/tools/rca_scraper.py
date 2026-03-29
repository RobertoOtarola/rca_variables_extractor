"""
rca_scraper.py — Herramienta para descargar documentos (RCA e ICE) desde el SEIA.
Soporta descarga individual por id_expediente o masiva desde archivos CSV/Excel/ODS.
"""

import os
import time
import argparse
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# --- CONFIGURACIÓN ---
BASE_URL = "https://seia.sea.gob.cl"
FICHA_URL = f"{BASE_URL}/expediente/xhr_documentos.php?id_expediente={{}}"
DOC_VIEWER_URL = f"{BASE_URL}/documentos/documento.php?idDocumento={{}}"
XML_DOWNLOAD_URL = f"{BASE_URL}/documentos/getXmlFile?docId={{}}"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

SCRAPED_DIR = Path("data/raw/scraped")
SESSION = requests.Session()


def get_project_html(url: str) -> str:
    """Obtiene el HTML de una página del proyecto."""
    res = SESSION.get(url, headers=HEADERS, timeout=30)
    res.encoding = res.apparent_encoding # SEIA suele usar ISO-8859-1
    res.raise_for_status()
    return res.text


def find_doc_links(html: str, pattern: str) -> list[str]:
    """Busca enlaces a documentos que coincidan con el patrón (RCA o ICE)."""
    # Usar regex directamente sobre el HTML para ser más robustos
    all_links = re.findall(r'href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    links = []
    for href, text in all_links:
        # Limpiamos el texto (BS4 es bueno para esto incluso en fragmentos)
        clean_text = BeautifulSoup(text, "html.parser").get_text().strip()
        if re.search(pattern, clean_text, re.IGNORECASE):
            links.append(href)
    return links


def download_file(url: str, output_path: Path, referer: str = None) -> bool:
    """Descarga un archivo verificando que no sea HTML."""
    try:
        headers = HEADERS.copy()
        if referer:
            headers["Referer"] = referer
            
        print(f"      - Descargando: {url}")
        res = SESSION.get(url, headers=headers, stream=True, timeout=30)
        res.raise_for_status()
        
        content_type = res.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"      ⚠️  Error descargando {url}: {e}")
        return False


def get_doc_id_from_viewer(viewer_url: str) -> str | None:
    """Extrae el idDocumento de una URL de visor."""
    match = re.search(r"idDocumento=(\d+)", viewer_url)
    return match.group(1) if match else None


def process_id(id_expediente: str, doc_patterns: dict[str, str], delay: float = 2.0):
    """Procesa un id_expediente buscando y descargando los documentos solicitados."""
    print(f"🔍 Procesando id_expediente: {id_expediente}...")
    
    try:
        # Obtenemos HTML de la tabla de documentos vía XHR
        html = get_project_html(FICHA_URL.format(id_expediente))
        target_dir = SCRAPED_DIR / id_expediente
        
        for doc_type, pattern in doc_patterns.items():
            all_links = find_doc_links(html, pattern)
            
            if not all_links:
                print(f"    ❌ No se encontró {doc_type}")
                continue
            
            # Intentamos con el último link encontrado (suele ser el más reciente/definitivo)
            found = False
            # Usamos dict.fromkeys para de-duplicar manteniendo el orden
            for link in reversed(list(dict.fromkeys(all_links))):
                full_url = urljoin(BASE_URL, link)
                
                # Caso 1: Link directo a PDF
                if full_url.lower().endswith(".pdf"):
                    pdf_path = target_dir / f"{doc_type}.pdf"
                    # El referer es la tabla de documentos
                    if download_file(full_url, pdf_path, referer=FICHA_URL.format(id_expediente)):
                        print(f"    ✅ {doc_type} descendado (PDF Directo)")
                        found = True
                        break

                # Caso 2: Link a visor /documentos/documento.php
                elif "documento.php" in full_url:
                    print(f"      - Explorando visor: {full_url}")
                    try:
                        inner_html = get_project_html(full_url)
                        # Buscamos cualquier link a .pdf o .xml dentro del visor
                        # A menudo los botones de descarga tienen texto como "Descargar" o el nombre del archivo
                        inner_links = find_doc_links(inner_html, r"\.pdf|\.xml|descargar|archivo")
                        
                        for i_link in inner_links:
                            # Usamos full_url (el visor) como base para resolver links relativos
                            i_full_url = urljoin(full_url, i_link)
                            ext = "pdf" if ".pdf" in i_full_url.lower() else "xml"
                            out_path = target_dir / f"{doc_type}.{ext}"
                            
                            if download_file(i_full_url, out_path, referer=full_url):
                                print(f"    ✅ {doc_type} descendado (desde visor: {ext})")
                                found = True
                                break
                        if found: break
                    except Exception as e:
                        print(f"      ⚠️  Error en visor {full_url}: {e}")

                if not found:
                    # Último recurso: intentar el XML directo si tenemos el ID
                    doc_id = get_doc_id_from_viewer(full_url)
                    if doc_id:
                        xml_url = XML_DOWNLOAD_URL.format(doc_id)
                        xml_path = target_dir / f"{doc_type}.xml"
                        # El referer es el visor
                        if download_file(xml_url, xml_path, referer=full_url):
                            print(f"    ✅ {doc_type} descargado (XML Directo)")
                            found = True
                            break
            
            if not found:
                print(f"    ❌ Falló la descarga de {doc_type}")
            
            time.sleep(delay) # Delay entre tipos de documentos del mismo proyecto

    except Exception as e:
        print(f"    💥 Error procesando {id_expediente}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Scraper de documentos RCA/ICE desde SEIA.")
    parser.add_argument("--id", help="ID de expediente individual")
    parser.add_argument("--input", help="Archivo (CSV/XLSX/ODS) con lista de IDs")
    parser.add_argument("--delay", type=float, default=2.0, help="Segundos entre peticiones (default: 2.0)")
    parser.add_argument("--ice", action="store_true", help="Descargar también el ICE")
    
    args = parser.parse_args()

    doc_patterns = {"RCA": r"RCA|Resoluci[oó]n de Calificaci[oó]n Ambiental"}
    if args.ice:
        doc_patterns["ICE"] = r"ICE|Informe Consolidado"

    ids = []
    if args.id:
        ids.append(args.id)
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"❌ Archivo no encontrado: {args.input}")
            return
            
        ext = path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        elif ext == ".ods":
            df = pd.read_excel(path, engine="odf")
        else:
            print(f"❌ Formato no soportado: {ext}")
            return
            
        if "id_expediente" not in df.columns:
            print(f"❌ Columna 'id_expediente' no encontrada en {args.input}")
            return
            
        ids = df["id_expediente"].dropna().astype(str).tolist()

    if not ids:
        print("💡 Usa --id o --input para especificar qué descargar.")
        return

    print(f"🚀 Iniciando descarga de {len(ids)} expedientes...")
    for idx, id_exp in enumerate(ids):
        process_id(id_exp, doc_patterns, delay=args.delay)
        if idx < len(ids) - 1:
            time.sleep(args.delay)

    print("✨ Proceso finalizado.")


if __name__ == "__main__":
    main()

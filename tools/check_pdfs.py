"""
check_pdfs.py
=============
Escanea una carpeta de PDFs e identifica archivos corruptos, con firma
incorrecta (ZIP renombrado como PDF, HTML, etc.), cifrados, con páginas
ilegibles, o escaneados como imagen (sin texto extraíble).

Genera:
  - Reporte en consola con resumen y detalle.
  - CSV completo con todos los archivos y su estado.
  - TXT con las rutas de los archivos a re-descargar (solo CORRUPTO).
  - TXT con las rutas de los PDFs escaneados (para pipeline OCR/imagen).

Uso:
    python check_pdfs.py                          # usa DEFAULT_SCAN_FOLDER
    python check_pdfs.py /ruta/a/carpeta          # otra carpeta
    python check_pdfs.py /ruta -o reporte.csv     # CSV personalizado
    python check_pdfs.py /ruta -w 8               # más hilos
    python check_pdfs.py /ruta --deep             # verifica TODAS las páginas
    python check_pdfs.py /ruta --hash             # añade columna MD5 al CSV
    python check_pdfs.py /ruta --strict           # %%EOF ausente → CORRUPTO
    python check_pdfs.py /ruta --detect-scanned   # detecta PDFs escaneados

Dependencias:
    python3 -m pip install -r requirements.txt
"""

import csv
import hashlib
import logging
import sys
import argparse
import time
import functools
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import pypdf
except ModuleNotFoundError:
    print(
        "No está instalado 'pypdf'. Ejecuta:\n"
        "  python3 -m pip install pypdf\n"
        "o, desde esta carpeta:\n"
        "  python3 -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

logging.getLogger("pypdf").setLevel(logging.ERROR)


# ─────────────────────────────────────────────
# CONSTANTES Y CONFIGURACIÓN
# ─────────────────────────────────────────────
DEFAULT_WORKERS = 6
DEFAULT_OUTPUT = "pdfs_report.csv"
DEFAULT_SCAN_FOLDER = (
    "/Users/roberto/Documents/1 Projects/CEDEUS UC/Databases/PDFs_RCAs"
)

HEADER_SCAN_BYTES = 1024
TAIL_SCAN_BYTES   = 4096

# Umbral de texto por página para considerar un PDF como escaneado.
# Si el promedio de caracteres por página muestreada es menor que este
# valor, se clasifica como ESCANEADO.
SCANNED_CHARS_THRESHOLD = 50
# Número de páginas a muestrear para detección de escaneado
SCANNED_SAMPLE_PAGES = 5

# ── Estados ───────────────────────────────────────────────────────────────────
ESTADO_OK          = "OK"
ESTADO_ADVERTENCIA = "ADVERTENCIA"
ESTADO_CORRUPTO    = "CORRUPTO"
ESTADO_CIFRADO     = "CIFRADO"
ESTADO_ESCANEADO   = "ESCANEADO"   # PDF válido pero sin texto extraíble (imagen)

# ── Tipos de error ────────────────────────────────────────────────────────────
TIPO_VACIO       = "vacio"
TIPO_FORMATO     = "formato_incorrecto"
TIPO_CABECERA    = "cabecera_faltante"
TIPO_EOF         = "eof_faltante"
TIPO_CIFRADO     = "cifrado"
TIPO_PYPDF       = "error_pypdf"
TIPO_IO          = "error_io"
TIPO_PAGINA      = "pagina_ilegible"
TIPO_TEXTO       = "texto_no_extraible"
TIPO_ESCANEADO   = "pdf_escaneado"   # imagen sin capa de texto
TIPO_INESPERADO  = "error_inesperado"
TIPO_NINGUNO     = ""

# ── Firmas binarias de formatos no-PDF ────────────────────────────────────────
NON_PDF_SIGNATURES: dict[bytes, str] = {
    b"PK\x03\x04":           "ZIP / DOCX / XLSX / PPTX",
    b"PK\x05\x06":           "ZIP (vacío)",
    b"PK\x07\x08":           "ZIP (spanned)",
    b"Rar!\x1a\x07\x00":     "RAR",
    b"Rar!\x1a\x07\x01\x00": "RAR5",
    b"7z\xbc\xaf'\x1c":      "7Z",
    b"\x1f\x8b\x08":         "GZIP",
    b"BZh":                   "BZIP2",
    b"\x89PNG\r\n\x1a\n":    "PNG",
    b"\xff\xd8\xff":          "JPEG",
    b"GIF87a":                "GIF",
    b"GIF89a":                "GIF",
    b"II\x2a\x00":           "TIFF (little-endian)",
    b"MM\x00\x2a":           "TIFF (big-endian)",
    b"BM":                    "BMP",
    b"RIFF":                  "WebP / WAV / AVI",
    b"\x00\x00\x01\x00":     "ICO",
    b"{\rtf":                 "RTF",
    b"\xd0\xcf\x11\xe0":     "Office 97–2003 (DOC/XLS/PPT)",
    b"\x00\x00\x00\x18ftyp": "MP4",
    b"\x00\x00\x00\x1cftyp": "MP4",
    b"fLaC":                  "FLAC",
    b"ID3":                   "MP3",
}

_SHORT_SIG_MIN_LEN: dict[bytes, int] = {
    b"BM": 14,
}


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def md5_of_file(file_path: Path, chunk: int = 1 << 20) -> str:
    hasher = hashlib.md5()
    try:
        with open(file_path, "rb") as fh:
            while True:
                data = fh.read(chunk)
                if not data:
                    break
                hasher.update(data)
        return hasher.hexdigest()
    except OSError:
        return "N/A"


def _make_result(file_path: Path, size: int) -> dict:
    return {
        "archivo":    file_path.name,
        "ruta":       str(file_path),
        "estado":     ESTADO_OK,
        "tipo_error": TIPO_NINGUNO,
        "paginas":    None,
        "tamanio_kb": round(size / 1024, 1),
        "md5":        "",
        "error":      "",
    }


# ─────────────────────────────────────────────
# DETECCIÓN DE FIRMA Y ESTRUCTURA BÁSICA
# ─────────────────────────────────────────────
def _is_html_bytes(data: bytes) -> bool:
    stripped = data.lstrip(b"\xef\xbb\xbf\xff\xfe\xfe\xff")
    lower = stripped[:64].lower()
    return lower.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def detect_format_error(file_path: Path) -> Optional[tuple[str, str]]:
    try:
        with open(file_path, "rb") as fh:
            head = fh.read(HEADER_SCAN_BYTES)
    except OSError as exc:
        return TIPO_IO, f"No se pudo leer el archivo: {exc}"

    if not head:
        return TIPO_VACIO, "Archivo vacío o sin contenido legible"

    for sig, fmt in NON_PDF_SIGNATURES.items():
        min_len = _SHORT_SIG_MIN_LEN.get(sig, 0)
        if head.startswith(sig) and len(head) >= max(len(sig), min_len):
            return TIPO_FORMATO, f"Firma binaria detectada: {fmt} (no es PDF)"

    if _is_html_bytes(head):
        return TIPO_FORMATO, "Firma detectada: HTML (no es PDF)"

    if b"%PDF-" not in head:
        return TIPO_CABECERA, (
            f"No se encontró la cabecera '%PDF-' en los primeros "
            f"{HEADER_SCAN_BYTES} bytes"
        )

    return None


def detect_eof_warning(file_path: Path) -> Optional[str]:
    try:
        with open(file_path, "rb") as fh:
            fh.seek(0, 2)
            file_size = fh.tell()
            fh.seek(max(file_size - TAIL_SCAN_BYTES, 0))
            tail = fh.read()
    except OSError:
        return None

    if b"%%EOF" not in tail:
        return (
            f"Marcador '%%EOF' ausente en los últimos {TAIL_SCAN_BYTES} bytes "
            "(PDF posiblemente truncado)"
        )
    return None


# ─────────────────────────────────────────────
# DETECCIÓN DE PDFs ESCANEADOS
# ─────────────────────────────────────────────
def is_scanned_pdf(
    reader: "pypdf.PdfReader",
    sample_pages: int = SCANNED_SAMPLE_PAGES,
    threshold: int = SCANNED_CHARS_THRESHOLD,
) -> tuple[bool, str]:
    """
    Determina si un PDF está escaneado como imagen (sin capa de texto).

    Muestrea hasta `sample_pages` páginas distribuidas uniformemente.
    Si el promedio de caracteres extraídos por página es menor que
    `threshold`, se considera escaneado.

    Devuelve (es_escaneado, mensaje).
    """
    num_pages = len(reader.pages)
    if num_pages == 0:
        return False, ""

    # Distribuir las páginas de muestra uniformemente
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
            pass  # página problemática → se ignora en el promedio

    if pages_sampled == 0:
        return False, ""

    avg_chars = total_chars / pages_sampled

    if avg_chars < threshold:
        return True, (
            f"Promedio {avg_chars:.0f} chars/página en {pages_sampled} "
            f"páginas muestreadas (umbral: {threshold}) — PDF escaneado como imagen"
        )

    return False, ""


# ─────────────────────────────────────────────
# INSPECCIÓN PRINCIPAL DE CADA PDF
# ─────────────────────────────────────────────
def check_pdf(
    file_path: Path,
    *,
    deep: bool = False,
    compute_hash: bool = False,
    strict_eof: bool = False,
    detect_scanned: bool = False,
) -> dict:
    """
    Inspecciona un archivo PDF y devuelve un dict con su estado.

    Estados posibles: OK, ADVERTENCIA, CORRUPTO, CIFRADO, ESCANEADO.
    """
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return {
            "archivo":    file_path.name,
            "ruta":       str(file_path),
            "estado":     ESTADO_CORRUPTO,
            "tipo_error": TIPO_IO,
            "paginas":    None,
            "tamanio_kb": 0.0,
            "md5":        "N/A",
            "error":      f"No se pudo acceder al archivo: {exc}",
        }

    result = _make_result(file_path, size)

    if compute_hash:
        result["md5"] = md5_of_file(file_path)

    if size == 0:
        result["estado"]     = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_VACIO
        result["error"]      = "Archivo vacío (0 bytes)"
        return result

    format_hit = detect_format_error(file_path)
    if format_hit:
        tipo, msg = format_hit
        result["estado"]     = ESTADO_CORRUPTO
        result["tipo_error"] = tipo
        result["error"]      = msg
        return result

    try:
        with open(file_path, "rb") as pdf_file:
            reader = pypdf.PdfReader(pdf_file, strict=False)

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                    if reader.is_encrypted:
                        raise pypdf.errors.FileNotDecryptedError("contraseña requerida")
                except pypdf.errors.FileNotDecryptedError:
                    result["estado"]     = ESTADO_CIFRADO
                    result["tipo_error"] = TIPO_CIFRADO
                    result["error"]      = "PDF protegido con contraseña"
                    return result

            num_pages = len(reader.pages)
            result["paginas"] = num_pages

            # ── Verificar páginas ─────────────────────────────────────────────
            pages_to_check = (
                range(num_pages) if deep else (range(1) if num_pages > 0 else range(0))
            )
            bad_pages: list[str] = []

            for idx in pages_to_check:
                try:
                    reader.pages[idx].extract_text()
                except (
                    pypdf.errors.PyPdfError,
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    UnicodeDecodeError,
                ) as page_err:
                    bad_pages.append(f"pág.{idx + 1}: {type(page_err).__name__}")

            if bad_pages:
                scope = "todas las páginas" if deep else "la página 1"
                result["estado"]     = ESTADO_ADVERTENCIA
                result["tipo_error"] = TIPO_TEXTO if not deep else TIPO_PAGINA
                result["error"]      = (
                    f"No se pudo extraer texto de {scope}: "
                    + ", ".join(bad_pages[:5])
                    + (" …" if len(bad_pages) > 5 else "")
                )

            # ── Detección de escaneado ────────────────────────────────────────
            # Solo aplica a PDFs que pasaron las verificaciones anteriores
            # (OK o ADVERTENCIA por EOF), no a los que ya tienen otro error.
            if detect_scanned and result["estado"] in (ESTADO_OK, ESTADO_ADVERTENCIA):
                scanned, scan_msg = is_scanned_pdf(reader)
                if scanned:
                    result["estado"]     = ESTADO_ESCANEADO
                    result["tipo_error"] = TIPO_ESCANEADO
                    result["error"]      = scan_msg

    except pypdf.errors.FileNotDecryptedError as exc:
        result["estado"]     = ESTADO_CIFRADO
        result["tipo_error"] = TIPO_CIFRADO
        result["error"]      = f"PDF cifrado: {exc}"

    except pypdf.errors.PyPdfError as exc:
        result["estado"]     = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_PYPDF
        result["error"]      = f"{type(exc).__name__}: {exc}"

    except (OSError, ValueError) as exc:
        result["estado"]     = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_IO
        result["error"]      = f"Error de E/S: {exc}"

    except (RuntimeError, MemoryError, RecursionError) as exc:
        result["estado"]     = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_INESPERADO
        result["error"]      = f"{type(exc).__name__}: {exc}"

    # ── Verificación de %%EOF ─────────────────────────────────────────────────
    if result["estado"] in (ESTADO_OK, ESTADO_ADVERTENCIA):
        eof_msg = detect_eof_warning(file_path)
        if eof_msg:
            if strict_eof:
                result["estado"]     = ESTADO_CORRUPTO
                result["tipo_error"] = TIPO_EOF
                result["error"]      = eof_msg
            elif result["estado"] == ESTADO_OK:
                result["estado"]     = ESTADO_ADVERTENCIA
                result["tipo_error"] = TIPO_EOF
                result["error"]      = eof_msg

    return result


# ─────────────────────────────────────────────
# ESCANEO DE CARPETA
# ─────────────────────────────────────────────
def scan_folder(
    folder: Path,
    workers: int,
    deep: bool = False,
    compute_hash: bool = False,
    strict_eof: bool = False,
    detect_scanned: bool = False,
) -> list:
    """
    Recorre la carpeta recursivamente y revisa cada PDF en paralelo.
    Devuelve lista de dicts ordenada: CORRUPTO → CIFRADO → ESCANEADO → ADVERTENCIA → OK.
    """
    pdf_files = sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() == ".pdf"
    )
    total = len(pdf_files)

    if total == 0:
        print("⚠  No se encontraron archivos PDF en la carpeta indicada.")
        return []

    modo = []
    if deep:
        modo.append("deep (todas las páginas)")
    if compute_hash:
        modo.append("MD5")
    if strict_eof:
        modo.append("strict-eof")
    if detect_scanned:
        modo.append("detect-scanned")

    print(f"\n📂  Carpeta           : {folder}")
    print(f"📄  PDFs encontrados  : {total}")
    print(f"⚙   Hilos paralelos  : {workers}")
    if modo:
        print(f"🔧  Opciones activas  : {', '.join(modo)}")
    print(f"{'─' * 60}")

    worker_fn = functools.partial(
        check_pdf,
        deep=deep,
        compute_hash=compute_hash,
        strict_eof=strict_eof,
        detect_scanned=detect_scanned,
    )

    results: list = []
    completed = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(worker_fn, p): p for p in pdf_files}

        for future in as_completed(futures):
            completed += 1
            res = future.result()
            results.append(res)

            pct = completed / total * 100
            filled = int(pct // 5)
            progress_bar = "█" * filled + "░" * (20 - filled)
            print(
                f"\r  [{progress_bar}] {pct:5.1f}%  ({completed}/{total})",
                end="",
                flush=True,
            )

    elapsed = time.time() - start
    print(f"\n{'─' * 60}")
    print(f"✅  Escaneo completado en {elapsed:.1f}s\n")

    order = {
        ESTADO_CORRUPTO:    0,
        ESTADO_CIFRADO:     1,
        ESTADO_ESCANEADO:   2,
        ESTADO_ADVERTENCIA: 3,
        ESTADO_OK:          4,
    }
    results.sort(key=lambda r: (order.get(r["estado"], 9), r["archivo"]))
    return results


# ─────────────────────────────────────────────
# REPORTE EN CONSOLA
# ─────────────────────────────────────────────
def print_report(results: list) -> None:
    corruptos    = [r for r in results if r["estado"] == ESTADO_CORRUPTO]
    cifrados     = [r for r in results if r["estado"] == ESTADO_CIFRADO]
    escaneados   = [r for r in results if r["estado"] == ESTADO_ESCANEADO]
    advertencias = [r for r in results if r["estado"] == ESTADO_ADVERTENCIA]
    ok           = [r for r in results if r["estado"] == ESTADO_OK]

    print("=" * 70)
    print("  RESUMEN DEL ESCANEO DE PDFs")
    print("=" * 70)
    print(f"  Total revisados  : {len(results)}")
    print(f"  ✅  OK            : {len(ok)}")
    print(f"  🔐  Cifrados      : {len(cifrados)}")
    print(f"  🖼   Escaneados    : {len(escaneados)}")
    print(f"  ⚠   Advertencias  : {len(advertencias)}")
    print(f"  ❌  Corruptos     : {len(corruptos)}")

    if corruptos:
        tipos: dict[str, int] = {}
        for r in corruptos:
            tipos[r["tipo_error"]] = tipos.get(r["tipo_error"], 0) + 1
        print("\n  Desglose de corruptos por tipo:")
        for tipo, cnt in sorted(tipos.items(), key=lambda x: -x[1]):
            print(f"    · {tipo:<25} {cnt}")

    print("=" * 70)

    if corruptos:
        print("\n❌  ARCHIVOS CORRUPTOS (requieren re-descarga):")
        print(f"  {'#':<4} {'Archivo':<42} {'KB':>8}  {'Tipo':<22}  Error")
        print(f"  {'─'*4} {'─'*42} {'─'*8}  {'─'*22}  {'─'*35}")
        for i, r in enumerate(corruptos, 1):
            nombre = r["archivo"][:41]
            tipo   = r["tipo_error"][:21]
            error  = r["error"][:60]
            print(f"  {i:<4} {nombre:<42} {r['tamanio_kb']:>8.1f}  {tipo:<22}  {error}")

    if cifrados:
        print(f"\n🔐  ARCHIVOS CIFRADOS ({len(cifrados)} — no son corruptos, solo protegidos):")
        for r in cifrados:
            print(f"  • {r['archivo']}")

    if escaneados:
        print(f"\n🖼   ARCHIVOS ESCANEADOS ({len(escaneados)} — se procesarán por imágenes):")
        for r in escaneados:
            print(f"  • {r['archivo']}  →  {r['error'][:80]}")

    if advertencias:
        print(f"\n⚠   ADVERTENCIAS ({len(advertencias)} archivos con posibles problemas):")
        for r in advertencias:
            print(f"  • {r['archivo']}  [{r['tipo_error']}]  →  {r['error'][:80]}")

    print()


# ─────────────────────────────────────────────
# EXPORTAR ARCHIVOS DE SALIDA
# ─────────────────────────────────────────────
def save_outputs(results: list, output_path: Path, compute_hash: bool) -> None:
    campos = ["archivo", "estado", "tipo_error", "paginas", "tamanio_kb", "ruta", "error"]
    if compute_hash:
        campos.insert(5, "md5")

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [{k: r.get(k, "") for k in campos} for r in results]

    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=campos)
        writer.writeheader()
        writer.writerows(rows)

    print(f"💾  CSV guardado en      : {output_path}")

    corruptos = [r for r in results if r["estado"] == ESTADO_CORRUPTO]
    if corruptos:
        txt_path = output_path.with_name("archivos_a_recargar.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(txt_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(f"# PDFs corruptos detectados el {timestamp}\n")
            txt_file.write(f"# Total: {len(corruptos)}\n\n")
            for r in corruptos:
                txt_file.write(f"{r['ruta']}\n")
        print(f"📋  Lista re-descarga en : {txt_path}")

    # Lista separada de PDFs escaneados para el pipeline de imágenes
    escaneados = [r for r in results if r["estado"] == ESTADO_ESCANEADO]
    if escaneados:
        scan_path = output_path.with_name("pdfs_escaneados.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(scan_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(f"# PDFs escaneados detectados el {timestamp}\n")
            txt_file.write(f"# Total: {len(escaneados)}\n")
            txt_file.write("# Estos archivos se procesarán mediante conversión a imágenes\n\n")
            for r in escaneados:
                txt_file.write(f"{r['ruta']}\n")
        print(f"🖼   Lista escaneados en  : {scan_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecta PDFs corruptos, cifrados, escaneados o con firma incorrecta.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python check_pdfs.py /datos/pdfs\n"
            "  python check_pdfs.py /datos/pdfs --deep --hash\n"
            "  python check_pdfs.py /datos/pdfs --detect-scanned -o resultado.csv\n"
            "  python check_pdfs.py /datos/pdfs --strict -o resultado.csv -w 8\n"
        ),
    )
    parser.add_argument(
        "carpeta",
        nargs="?",
        default=DEFAULT_SCAN_FOLDER,
        help=f"Carpeta a escanear (default: {DEFAULT_SCAN_FOLDER})",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Archivo CSV de salida (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Hilos paralelos (default: {DEFAULT_WORKERS}; rango: 1–32)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Verifica TODAS las páginas, no solo la primera (más lento)",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="Añade columna MD5 al CSV para cruzar con listas de descarga",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Trata la ausencia de '%%%%EOF' como CORRUPTO (en vez de ADVERTENCIA)",
    )
    parser.add_argument(
        "--detect-scanned",
        action="store_true",
        help=(
            "Detecta PDFs escaneados como imagen (sin texto extraíble). "
            f"Umbral: {SCANNED_CHARS_THRESHOLD} chars/página promedio. "
            "Genera pdfs_escaneados.txt para el pipeline de imágenes."
        ),
    )
    args = parser.parse_args()

    if not 1 <= args.workers <= 32:
        parser.error("--workers debe estar entre 1 y 32")

    folder = Path(args.carpeta).expanduser().resolve()
    if not folder.is_dir():
        print(f"❌  La carpeta '{folder}' no existe o no es un directorio.")
        sys.exit(1)

    results = scan_folder(
        folder,
        workers=args.workers,
        deep=args.deep,
        compute_hash=args.hash,
        strict_eof=args.strict,
        detect_scanned=args.detect_scanned,
    )
    if not results:
        sys.exit(0)

    print_report(results)
    save_outputs(results, Path(args.output).expanduser(), compute_hash=args.hash)


if __name__ == "__main__":
    main()

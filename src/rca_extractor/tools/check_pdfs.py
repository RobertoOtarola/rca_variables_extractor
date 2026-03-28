"""
check_pdfs.py
=============
Escanea una carpeta de PDFs e identifica archivos corruptos, con firma
incorrecta (ZIP renombrado como PDF, HTML, etc.), cifrados o con páginas
ilegibles.

Genera:
  - Reporte en consola con resumen y detalle.
  - CSV completo con todos los archivos y su estado.
  - TXT con las rutas de los archivos a re-descargar (solo CORRUPTO).

Uso:
    python check_pdfs.py                          # usa DEFAULT_SCAN_FOLDER
    python check_pdfs.py /ruta/a/carpeta          # otra carpeta
    python check_pdfs.py /ruta -o reporte.csv     # CSV personalizado
    python check_pdfs.py /ruta -w 8               # más hilos
    python check_pdfs.py /ruta --deep             # verifica TODAS las páginas
    python check_pdfs.py /ruta --hash             # añade columna MD5 al CSV
    python check_pdfs.py /ruta --strict           # %%EOF ausente → CORRUPTO

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

# Silencia los avisos de pypdf sobre PDFs dañados; el detalle va al CSV.
logging.getLogger("pypdf").setLevel(logging.ERROR)


# ─────────────────────────────────────────────
# CONSTANTES Y CONFIGURACIÓN
# ─────────────────────────────────────────────
DEFAULT_WORKERS = 6
DEFAULT_OUTPUT = "pdfs_report.csv"
DEFAULT_SCAN_FOLDER = "/Users/roberto/Documents/1 Projects/CEDEUS UC/Databases/PDFs_RCAs"

HEADER_SCAN_BYTES = 1024  # bytes a leer al inicio para detectar firma
TAIL_SCAN_BYTES = 4096  # bytes a leer al final para buscar %%EOF

# ── Estados ────────────────────────────────────────────────────────────────────
ESTADO_OK = "OK"
ESTADO_ADVERTENCIA = "ADVERTENCIA"
ESTADO_CORRUPTO = "CORRUPTO"
ESTADO_CIFRADO = "CIFRADO"

# ── Tipos de error (campo tipo_error en el CSV) ────────────────────────────────
TIPO_VACIO = "vacio"
TIPO_FORMATO = "formato_incorrecto"  # ZIP, PNG, HTML… renombrado como PDF
TIPO_CABECERA = "cabecera_faltante"  # no hay "%PDF-" en los primeros bytes
TIPO_EOF = "eof_faltante"  # falta "%%EOF" al final
TIPO_CIFRADO = "cifrado"  # PDF protegido con contraseña
TIPO_PYPDF = "error_pypdf"  # pypdf lanzó PyPdfError
TIPO_IO = "error_io"  # OSError / ValueError
TIPO_PAGINA = "pagina_ilegible"  # error al leer una página concreta
TIPO_TEXTO = "texto_no_extraible"  # texto de pág. 1 no extraíble (ADVERTENCIA)
TIPO_INESPERADO = "error_inesperado"  # excepción no catalogada
TIPO_NINGUNO = ""  # sin error

# ── Firmas binarias de formatos no-PDF ────────────────────────────────────────
# Clave: primeros bytes del archivo. Valor: nombre legible del formato.
NON_PDF_SIGNATURES: dict[bytes, str] = {
    # Archivos comprimidos / contenedores
    b"PK\x03\x04": "ZIP / DOCX / XLSX / PPTX",
    b"PK\x05\x06": "ZIP (vacío)",
    b"PK\x07\x08": "ZIP (spanned)",
    b"Rar!\x1a\x07\x00": "RAR",
    b"Rar!\x1a\x07\x01\x00": "RAR5",
    b"7z\xbc\xaf'\x1c": "7Z",
    b"\x1f\x8b\x08": "GZIP",
    b"BZh": "BZIP2",
    # Imágenes
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"\xff\xd8\xff": "JPEG",
    b"GIF87a": "GIF",
    b"GIF89a": "GIF",
    b"II\x2a\x00": "TIFF (little-endian)",
    b"MM\x00\x2a": "TIFF (big-endian)",
    b"BM": "BMP",  # 2 bytes; verificado abajo
    b"RIFF": "WebP / WAV / AVI",
    b"\x00\x00\x01\x00": "ICO",
    # Documentos / texto
    b"{\rtf": "RTF",
    b"\xd0\xcf\x11\xe0": "Office 97–2003 (DOC/XLS/PPT)",  # OLE2
    # Vídeo / audio
    b"\x00\x00\x00\x18ftyp": "MP4",
    b"\x00\x00\x00\x1cftyp": "MP4",
    b"fLaC": "FLAC",
    b"ID3": "MP3",
}

# Firmas cortas (≤ 2 bytes) que podrían dar falsos positivos: exigimos longitud mínima
_SHORT_SIG_MIN_LEN: dict[bytes, int] = {
    b"BM": 14,  # cabecera BMP siempre tiene ≥ 14 bytes
}


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def md5_of_file(file_path: Path, chunk: int = 1 << 20) -> str:
    """Calcula el MD5 del archivo en bloques para no cargar todo en memoria."""
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
    """Crea el dict de resultado con valores por defecto (estado OK)."""
    return {
        "archivo": file_path.name,
        "ruta": str(file_path),
        "estado": ESTADO_OK,
        "tipo_error": TIPO_NINGUNO,
        "paginas": None,
        "tamanio_kb": round(size / 1024, 1),
        "md5": "",  # se rellena si --hash está activo
        "error": "",
    }


# ─────────────────────────────────────────────
# DETECCIÓN DE FIRMA Y ESTRUCTURA BÁSICA
# ─────────────────────────────────────────────
def _is_html_bytes(data: bytes) -> bool:
    """Devuelve True si los primeros bytes parecen HTML (ignora BOM y mayúsculas)."""
    stripped = data.lstrip(b"\xef\xbb\xbf\xff\xfe\xfe\xff")  # elimina BOM
    lower = stripped[:64].lower()
    return lower.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def detect_format_error(file_path: Path) -> Optional[tuple[str, str]]:
    """
    Comprueba la firma binaria del archivo para detectar formatos no-PDF.

    Devuelve None si el archivo parece un PDF, o una tupla
    (tipo_error, mensaje) si se detecta un problema estructural duro.

    Solo lanza excepciones que no sean OSError (ya capturadas en check_pdf).
    """
    try:
        with open(file_path, "rb") as fh:
            head = fh.read(HEADER_SCAN_BYTES)
    except OSError as exc:
        return TIPO_IO, f"No se pudo leer el archivo: {exc}"

    if not head:
        return TIPO_VACIO, "Archivo vacío o sin contenido legible"

    # ── Firmas de formatos conocidos ─────────────────────────────────────────
    for sig, fmt in NON_PDF_SIGNATURES.items():
        min_len = _SHORT_SIG_MIN_LEN.get(sig, 0)
        if head.startswith(sig) and len(head) >= max(len(sig), min_len):
            return TIPO_FORMATO, f"Firma binaria detectada: {fmt} (no es PDF)"

    # ── Detección de HTML (puede tener BOM, distintas mayúsculas, etc.) ──────
    if _is_html_bytes(head):
        return TIPO_FORMATO, "Firma detectada: HTML (no es PDF)"

    # ── Comprobación de cabecera PDF ─────────────────────────────────────────
    if b"%PDF-" not in head:
        # Intentamos leer un poco más por si el archivo tiene bytes basura al inicio
        return TIPO_CABECERA, (
            f"No se encontró la cabecera '%PDF-' en los primeros {HEADER_SCAN_BYTES} bytes"
        )

    return None  # parece un PDF estructuralmente válido en cabecera


def detect_eof_warning(file_path: Path) -> Optional[str]:
    """
    Comprueba que el PDF tenga el marcador '%%EOF' cerca del final.

    Devuelve un mensaje de advertencia o None si todo está bien.
    Se ejecuta SOLO si pypdf ya pudo abrir el archivo (para evitar
    falsos positivos; hay PDFs válidos sin %%EOF que pypdf maneja bien).
    """
    try:
        with open(file_path, "rb") as fh:
            fh.seek(0, 2)
            file_size = fh.tell()
            fh.seek(max(file_size - TAIL_SCAN_BYTES, 0))
            tail = fh.read()
    except OSError:
        return None  # no bloqueamos; el error de IO ya se capturó antes

    if b"%%EOF" not in tail:
        return (
            f"Marcador '%%EOF' ausente en los últimos {TAIL_SCAN_BYTES} bytes "
            "(PDF posiblemente truncado)"
        )
    return None


# ─────────────────────────────────────────────
# INSPECCIÓN PRINCIPAL DE CADA PDF
# ─────────────────────────────────────────────
def check_pdf(
    file_path: Path, *, deep: bool = False, compute_hash: bool = False, strict_eof: bool = False
) -> dict:
    """
    Inspecciona un archivo PDF y devuelve un dict con su estado.

    Parámetros
    ----------
    file_path    : ruta al archivo.
    deep         : si True, intenta leer TODAS las páginas (más lento).
    compute_hash : si True, calcula el MD5 del archivo.
    strict_eof   : si True, la ausencia de %%EOF se trata como CORRUPTO.

    Estados posibles: OK, ADVERTENCIA, CORRUPTO, CIFRADO.
    """
    # ── 1. Acceso al sistema de archivos ────────────────────────────────────
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return {
            "archivo": file_path.name,
            "ruta": str(file_path),
            "estado": ESTADO_CORRUPTO,
            "tipo_error": TIPO_IO,
            "paginas": None,
            "tamanio_kb": 0.0,
            "md5": "N/A",
            "error": f"No se pudo acceder al archivo: {exc}",
        }

    result = _make_result(file_path, size)

    if compute_hash:
        result["md5"] = md5_of_file(file_path)

    # ── 2. Archivo vacío ─────────────────────────────────────────────────────
    if size == 0:
        result["estado"] = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_VACIO
        result["error"] = "Archivo vacío (0 bytes)"
        return result

    # ── 3. Firma binaria / cabecera PDF ──────────────────────────────────────
    format_hit = detect_format_error(file_path)
    if format_hit:
        tipo, msg = format_hit
        result["estado"] = ESTADO_CORRUPTO
        result["tipo_error"] = tipo
        result["error"] = msg
        return result

    # ── 4. Lectura con pypdf ─────────────────────────────────────────────────
    try:
        with open(file_path, "rb") as pdf_file:
            reader = pypdf.PdfReader(pdf_file, strict=False)

            # PDF cifrado sin contraseña → CIFRADO (no es corrupción)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")  # intenta contraseña vacía
                    if reader.is_encrypted:  # sigue cifrado
                        raise pypdf.errors.FileNotDecryptedError("contraseña requerida")
                except pypdf.errors.FileNotDecryptedError:
                    result["estado"] = ESTADO_CIFRADO
                    result["tipo_error"] = TIPO_CIFRADO
                    result["error"] = "PDF protegido con contraseña"
                    return result

            num_pages = len(reader.pages)
            result["paginas"] = num_pages

            # ── 4a. Verificar páginas ────────────────────────────────────────
            pages_to_check = range(num_pages) if deep else (range(1) if num_pages > 0 else range(0))
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
                result["estado"] = ESTADO_ADVERTENCIA
                result["tipo_error"] = TIPO_TEXTO if not deep else TIPO_PAGINA
                result["error"] = (
                    f"No se pudo extraer texto de {scope}: "
                    + ", ".join(bad_pages[:5])
                    + (" …" if len(bad_pages) > 5 else "")
                )

    except pypdf.errors.FileNotDecryptedError as exc:
        result["estado"] = ESTADO_CIFRADO
        result["tipo_error"] = TIPO_CIFRADO
        result["error"] = f"PDF cifrado: {exc}"

    except pypdf.errors.PyPdfError as exc:
        result["estado"] = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_PYPDF
        result["error"] = f"{type(exc).__name__}: {exc}"

    except (OSError, ValueError) as exc:
        result["estado"] = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_IO
        result["error"] = f"Error de E/S: {exc}"

    except (RuntimeError, MemoryError, RecursionError) as exc:
        result["estado"] = ESTADO_CORRUPTO
        result["tipo_error"] = TIPO_INESPERADO
        result["error"] = f"{type(exc).__name__}: {exc}"

    # ── 5. Verificación de %%EOF (solo si el archivo abrió sin errores graves)
    if result["estado"] in (ESTADO_OK, ESTADO_ADVERTENCIA):
        eof_msg = detect_eof_warning(file_path)
        if eof_msg:
            if strict_eof:
                result["estado"] = ESTADO_CORRUPTO
                result["tipo_error"] = TIPO_EOF
                result["error"] = eof_msg
            elif result["estado"] == ESTADO_OK:
                # Solo degradar a ADVERTENCIA si no había ya otro aviso
                result["estado"] = ESTADO_ADVERTENCIA
                result["tipo_error"] = TIPO_EOF
                result["error"] = eof_msg

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
) -> list:
    """
    Recorre la carpeta recursivamente y revisa cada PDF en paralelo.

    Devuelve lista de dicts ordenada: CORRUPTO → CIFRADO → ADVERTENCIA → OK.
    """
    pdf_files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
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

    order = {ESTADO_CORRUPTO: 0, ESTADO_CIFRADO: 1, ESTADO_ADVERTENCIA: 2, ESTADO_OK: 3}
    results.sort(key=lambda r: (order.get(r["estado"], 9), r["archivo"]))
    return results


# ─────────────────────────────────────────────
# REPORTE EN CONSOLA
# ─────────────────────────────────────────────
def print_report(results: list) -> None:
    """Imprime resumen y detalle de corruptos, cifrados y advertencias."""
    corruptos = [r for r in results if r["estado"] == ESTADO_CORRUPTO]
    cifrados = [r for r in results if r["estado"] == ESTADO_CIFRADO]
    advertencias = [r for r in results if r["estado"] == ESTADO_ADVERTENCIA]
    ok = [r for r in results if r["estado"] == ESTADO_OK]

    print("=" * 70)
    print("  RESUMEN DEL ESCANEO DE PDFs")
    print("=" * 70)
    print(f"  Total revisados  : {len(results)}")
    print(f"  ✅  OK            : {len(ok)}")
    print(f"  🔐  Cifrados      : {len(cifrados)}")
    print(f"  ⚠   Advertencias  : {len(advertencias)}")
    print(f"  ❌  Corruptos     : {len(corruptos)}")

    # Desglose por tipo de error dentro de los corruptos
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
        print(f"  {'─' * 4} {'─' * 42} {'─' * 8}  {'─' * 22}  {'─' * 35}")
        for i, r in enumerate(corruptos, 1):
            nombre = r["archivo"][:41]
            tipo = r["tipo_error"][:21]
            error = r["error"][:60]
            print(f"  {i:<4} {nombre:<42} {r['tamanio_kb']:>8.1f}  {tipo:<22}  {error}")

    if cifrados:
        print(f"\n🔐  ARCHIVOS CIFRADOS ({len(cifrados)} — no son corruptos, solo protegidos):")
        for r in cifrados:
            print(f"  • {r['archivo']}")

    if advertencias:
        print(f"\n⚠   ADVERTENCIAS ({len(advertencias)} archivos con posibles problemas):")
        for r in advertencias:
            print(f"  • {r['archivo']}  [{r['tipo_error']}]  →  {r['error'][:80]}")

    print()


# ─────────────────────────────────────────────
# EXPORTAR ARCHIVOS DE SALIDA
# ─────────────────────────────────────────────
def save_outputs(results: list, output_path: Path, compute_hash: bool) -> None:
    """
    Guarda el CSV completo y, si hay corruptos, el TXT de re-descarga.

    El campo 'md5' se omite de las columnas si --hash no estaba activo.
    """
    campos = ["archivo", "estado", "tipo_error", "paginas", "tamanio_kb", "ruta", "error"]
    if compute_hash:
        campos.insert(5, "md5")

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Filtrar campos en cada fila para evitar KeyError si md5 no fue calculado
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


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main() -> None:
    """Punto de entrada: parsea argumentos, escanea carpeta y genera salidas."""
    parser = argparse.ArgumentParser(
        description="Detecta PDFs corruptos, cifrados o con firma incorrecta.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python check_pdfs.py /datos/pdfs\n"
            "  python check_pdfs.py /datos/pdfs --deep --hash\n"
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
        "--output",
        "-o",
        default=DEFAULT_OUTPUT,
        help=f"Archivo CSV de salida (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--workers",
        "-w",
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
    )
    if not results:
        sys.exit(0)

    print_report(results)
    save_outputs(results, Path(args.output).expanduser(), compute_hash=args.hash)


if __name__ == "__main__":
    main()

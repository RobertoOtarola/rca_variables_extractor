"""
main.py — Punto de entrada del extractor de variables RCA.

Uso básico:
    python main.py

Opciones avanzadas:
    python main.py --pdf-folder data/raw/ --output rca_results.xlsx --workers 2 --reset
"""

import argparse
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import config
from logger import get_logger
from checkpoint import Checkpoint
from pdf_pipeline import RCAExtractor
from prompt_builder import load_variables

# ── Logger global ─────────────────────────────────────────────────────────────
log = get_logger(log_file=config.LOG_FILE)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extractor automático de variables RCA usando Gemini."
    )
    p.add_argument("--pdf-folder",   default=str(config.PDF_FOLDER),
                   help="Carpeta con los PDFs de RCA (default: %(default)s)")
    p.add_argument("--variables",    default=str(config.VARIABLES_FILE),
                   help="Excel con las variables a extraer (default: %(default)s)")
    p.add_argument("--output",       default=str(config.OUTPUT_FILE),
                   help="Archivo Excel de salida (default: %(default)s)")
    p.add_argument("--checkpoint",   default=str(config.CHECKPOINT_FILE),
                   help="Archivo de checkpoint (default: %(default)s)")
    p.add_argument("--workers",      type=int, default=config.MAX_WORKERS,
                   help="Nº de PDFs en paralelo (default: %(default)s)")
    p.add_argument("--model",        default=config.GEMINI_MODEL,
                   help="Modelo Gemini (default: %(default)s)")
    p.add_argument("--max-retries",  type=int, default=config.MAX_RETRIES,
                   help="Reintentos por PDF ante errores de API (default: %(default)s)")
    p.add_argument("--cooldown",     type=int, default=config.INTER_PDF_COOLDOWN,
                   help="Segundos de pausa entre PDFs consecutivos (default: %(default)s). "
                        "Aumentar a 60+ si hay 429s frecuentes en free tier.")
    p.add_argument("--reset",        action="store_true",
                   help="Ignora el checkpoint y reprocesa todos los PDFs")
    p.add_argument("--dry-run",      action="store_true",
                   help="Lista los PDFs pendientes sin procesarlos")
    return p.parse_args()


# ── Procesamiento individual (para ThreadPoolExecutor) ───────────────────────

def _process_one(extractor: RCAExtractor, pdf: Path, variables: list[dict]) -> tuple[str, dict | None, str | None]:
    """Retorna (nombre, datos_o_None, mensaje_error_o_None)."""
    try:
        data = extractor.process_pdf(pdf, variables)
        return pdf.name, data, None
    except Exception as exc:
        return pdf.name, None, str(exc)


# ── Barra de progreso ─────────────────────────────────────────────────────────

def _make_bar(pending: list[Path], total: int) -> tqdm:
    """
    Crea la barra de progreso.
    - total   : PDFs en el lote completo (incluye ya procesados)
    - initial : PDFs ya marcados OK en el checkpoint (se saltan)
    """
    already_done = total - len(pending)
    return tqdm(
        total=total,
        initial=already_done,
        unit="PDF",
        desc="Extrayendo variables",
        bar_format=(
            "{desc}: {percentage:3.0f}%|{bar}| "
            "PDF {n_fmt}/{total_fmt} "
            "[{elapsed}<{remaining}, {rate_fmt}]"
        ),
        dynamic_ncols=True,
        colour="green",
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    pdf_folder  = Path(args.pdf_folder)
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Cargar variables
    try:
        variables = load_variables(args.variables, config.VARIABLES_COLUMN)
    except (FileNotFoundError, ValueError) as exc:
        log.error("Error cargando variables: %s", exc)
        return 1

    # 2. Enumerar PDFs
    pdfs = sorted(pdf_folder.glob("*.pdf"))
    if not pdfs:
        log.warning("No se encontraron PDFs en '%s'", pdf_folder)
        return 0

    log.info("PDFs encontrados: %d", len(pdfs))

    # 3. Checkpoint
    checkpoint = Checkpoint(Path(args.checkpoint))

    if args.reset:
        log.info("--reset activado: se ignorará el checkpoint existente.")
        pending = pdfs
    else:
        pending = checkpoint.pending(pdfs)
        skipped = len(pdfs) - len(pending)
        if skipped:
            log.info("PDFs ya procesados (checkpoint): %d — se omiten.", skipped)

    if not pending:
        log.info("Todos los PDFs ya fueron procesados. Nada que hacer.")
        return 0

    if args.dry_run:
        log.info("-- DRY RUN: %d PDFs pendientes --", len(pending))
        for p in pending:
            print(f"  • {p.name}")
        return 0

    # 4. Cargar resultados previos si existen, excluyendo PDFs que se van a reprocesar
    existing_results: list[dict] = []
    if output_file.exists() and not args.reset:
        try:
            pending_names = {p.name for p in pending}
            existing_results = [
                r for r in pd.read_excel(output_file).to_dict("records")
                if r.get("archivo") not in pending_names
            ]
            log.info("Resultados previos cargados: %d filas", len(existing_results))
        except Exception as exc:
            log.warning("No se pudo leer el archivo de salida existente: %s", exc)

    # 5. Extraer
    extractor = RCAExtractor(model=args.model, max_retries=args.max_retries)
    results: list[dict] = list(existing_results)
    stats = {"ok": 0, "error": 0}
    t0 = time.time()

    def _flush(results: list[dict]) -> None:
        """Guarda el Excel de forma progresiva."""
        df = pd.DataFrame(results)
        cols = ["archivo"] + [c for c in df.columns if c != "archivo"]
        df[cols].to_excel(output_file, index=False)

    if args.workers == 1:
        # Modo secuencial con barra de progreso
        with _make_bar(pending, len(pdfs)) as bar:
            for idx, pdf in enumerate(pending):
                bar.set_description(
                    f"Extrayendo RCA {bar.n + 1}/{len(pdfs)} — {pdf.name}"
                )
                name, data, err = _process_one(extractor, pdf, variables)

                if data:
                    results.append(data)
                    checkpoint.mark_ok(name)
                    stats["ok"] += 1
                    _flush(results)
                else:
                    log.error("❌ %s: %s", name, err)
                    checkpoint.mark_error(name, err or "desconocido")
                    stats["error"] += 1

                bar.set_postfix(ok=stats["ok"], error=stats["error"], refresh=False)
                bar.update(1)

                # Cooldown entre PDFs (no después del último)
                if args.cooldown > 0 and idx < len(pending) - 1:
                    bar.set_description(f"Cooldown {args.cooldown}s…")
                    time.sleep(args.cooldown)

    else:
        # Modo concurrente con barra de progreso
        log.info("Procesando con %d workers en paralelo.", args.workers)
        with _make_bar(pending, len(pdfs)) as bar:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {
                    pool.submit(_process_one, extractor, pdf, variables): pdf
                    for pdf in pending
                }
                for future in as_completed(futures):
                    name, data, err = future.result()
                    if data:
                        results.append(data)
                        checkpoint.mark_ok(name)
                        stats["ok"] += 1
                        _flush(results)
                    else:
                        log.error("❌ %s: %s", name, err)
                        checkpoint.mark_error(name, err or "desconocido")
                        stats["error"] += 1

                    bar.set_postfix(ok=stats["ok"], error=stats["error"], refresh=False)
                    bar.update(1)

    # 6. Resumen
    elapsed = time.time() - t0
    log.info(
        "── Resumen ── OK: %d | Error: %d | Total: %d | Tiempo: %.1fs",
        stats["ok"], stats["error"], len(pending), elapsed
    )
    log.info("Resultados guardados en: %s", output_file)
    return 0 if stats["error"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

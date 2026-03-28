"""
post_processing/run.py — CLI de post-procesamiento.

Uso:
    python -m post_processing.run --input data/processed/results.xlsx
    python -m post_processing.run --input data/processed/results.xlsx --db sqlite:///data/processed/rca_data.db
    python -m post_processing.run --input data/processed/results.xlsx --no-db

Genera:
    data/processed/results_normalized.xlsx   — datos tipados + intensidad derivada
    data/processed/validation_report.xlsx    — flags de rango y outliers
"""

import argparse
import sys
import logging
from pathlib import Path

import pandas as pd

from rca_extractor.post_processing.normalizer import normalize
from rca_extractor.post_processing.validator import (
    validate_ranges,
    detect_outliers,
    completeness_report,
)
from rca_extractor.post_processing.db_storage import get_engine, init_db, upsert_projects

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rca_extractor")


def parse_args():
    p = argparse.ArgumentParser(description="Post-procesamiento RCA Extractor")
    p.add_argument(
        "--input",
        default="data/processed/results.xlsx",
        help="Excel de extracción (default: %(default)s)",
    )
    p.add_argument(
        "--output-dir", default="data/processed", help="Carpeta de salida (default: %(default)s)"
    )
    p.add_argument(
        "--db",
        default="sqlite:///data/processed/rca_data.db",
        help="URL SQLAlchemy para la BD (default: %(default)s)",
    )
    p.add_argument("--no-db", action="store_true", help="Omite la persistencia en BD")
    p.add_argument(
        "--sigma",
        type=float,
        default=3.0,
        help="Umbral z-score para outliers (default: %(default)s)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cargar
    log.info("Cargando: %s", args.input)
    df_raw = pd.read_excel(args.input)
    log.info("Filas cargadas: %d", len(df_raw))

    # 2. Normalizar
    log.info("Normalizando tipos y vocabulario...")
    df = normalize(df_raw)

    # 3. Validar rangos
    log.info("Validando rangos científicos...")
    range_df = validate_ranges(df)
    log.info("  Flags fuera de rango: %d", len(range_df))

    # 4. Detectar outliers
    log.info("Detectando outliers (σ=%.1f)...", args.sigma)
    outlier_df = detect_outliers(df, sigma=args.sigma)
    log.info("  Outliers detectados: %d", len(outlier_df))

    # 5. Reporte de completitud
    completeness_df = completeness_report(df)

    # 6. Guardar Excel normalizado
    out_norm = out_dir / "results_normalized.xlsx"
    df.to_excel(out_norm, index=False)
    log.info("Excel normalizado: %s", out_norm)

    # 7. Guardar reporte de validación
    out_val = out_dir / "validation_report.xlsx"
    with pd.ExcelWriter(out_val) as writer:
        completeness_df.to_excel(writer, sheet_name="completitud", index=False)
        range_df.to_excel(writer, sheet_name="fuera_de_rango", index=False)
        outlier_df.to_excel(writer, sheet_name="outliers", index=False)
    log.info("Reporte de validación: %s", out_val)

    # 8. Persistir en BD
    if not args.no_db:
        log.info("Persistiendo en BD: %s", args.db)
        engine = get_engine(args.db)
        init_db(engine)
        n = upsert_projects(engine, df, outlier_df, range_df)
        log.info("  %d proyectos en BD.", n)

    # 9. Resumen
    log.info("── Resumen ──────────────────────────────────")
    log.info("  Filas normalizadas : %d", len(df))
    log.info(
        "  Flags fuera rango  : %d en %d proyectos",
        len(range_df),
        range_df["archivo"].nunique() if len(range_df) else 0,
    )
    log.info(
        "  Outliers (%.1fσ)   : %d en %d proyectos",
        args.sigma,
        len(outlier_df),
        outlier_df["archivo"].nunique() if len(outlier_df) else 0,
    )
    log.info("  Completitud media  : %.1f%%", completeness_df["completitud_pct"].mean())
    log.info("─────────────────────────────────────────────")
    return 0


if __name__ == "__main__":
    sys.exit(main())

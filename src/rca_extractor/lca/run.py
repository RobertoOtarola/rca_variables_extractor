"""
lca/run.py — CLI de Fase 4a: calcula ACV para todos los proyectos.

Uso:
    python -m lca.run --input data/processed/results_normalized.xlsx

Genera:
    data/processed/results_lca.xlsx — datos originales + columnas ACV
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
from rca_extractor.lca.calculator import calculate

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger("rca_extractor")


def main():
    p = argparse.ArgumentParser(description="Fase 4a — ACV")
    p.add_argument("--input", default="data/processed/results_normalized.xlsx")
    p.add_argument("--output-dir", default="data/processed")
    args = p.parse_args()

    df = pd.read_excel(args.input)
    log.info("Calculando ACV para %d proyectos...", len(df))

    lca_rows = [calculate(row) for _, row in df.iterrows()]
    lca_df = pd.DataFrame([vars(r) for r in lca_rows])

    # Merge: drop 'archivo' de lca_df para evitar duplicado
    out = pd.concat([df, lca_df.drop(columns=["archivo", "tech"])], axis=1)

    out_path = Path(args.output_dir) / "results_lca.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_excel(out_path, index=False)

    # Stats
    with_energy = lca_df["lifetime_energy_mwh"].notna().sum()
    with_ghg = lca_df["ghg_total_kt"].notna().sum()
    total_gw = df["potencia_nominal_bruta_mw"].sum() / 1000
    total_gwh = lca_df["lifetime_energy_mwh"].sum() / 1e6

    log.info("── Resumen ACV ──────────────────────────────")
    log.info("  Potencia total instalada : %.2f GW", total_gw)
    log.info("  Energía total vida útil  : %.2f TWh", total_gwh)
    log.info("  Proyectos con energía    : %d / %d", with_energy, len(df))
    log.info("  Proyectos con GEI calc.  : %d / %d", with_ghg, len(df))
    log.info("  Output: %s", out_path)
    log.info("─────────────────────────────────────────────")
    return 0


if __name__ == "__main__":
    sys.exit(main())

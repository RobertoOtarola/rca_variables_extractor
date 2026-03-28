"""
geo/run.py — CLI de la Fase 3: georreferenciación y análisis espacial.

Uso básico (solo parseo de coordenadas):
    python -m geo.run --input data/processed/results_normalized.xlsx

Con análisis de áreas protegidas (requiere shapefile SNASPE):
    python -m geo.run \
      --input data/processed/results_normalized.xlsx \
      --protected data/geo/snaspe.shp \
      --protected-name-col NOMBRE \
      --buffer-km 5

Genera:
    data/processed/results_geo.xlsx     — datos con lon/lat y flags espaciales
    data/processed/region_summary.xlsx  — métricas agregadas por región
    data/processed/projects.geojson     — GeoJSON descargable para QGIS/Mapbox
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from rca_extractor.geo.spatial_analysis import (
    build_geodataframe,
    load_protected_areas,
    intersect_protected,
    region_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rca_extractor")


def parse_args():
    p = argparse.ArgumentParser(description="Fase 3 — Georreferenciación RCA")
    p.add_argument(
        "--input",
        default="data/processed/results_normalized.xlsx",
        help="Excel normalizado (default: %(default)s)",
    )
    p.add_argument(
        "--output-dir", default="data/processed", help="Carpeta de salida (default: %(default)s)"
    )
    p.add_argument(
        "--protected", default=None, help="Shapefile de áreas protegidas (SNASPE). Opcional."
    )
    p.add_argument(
        "--protected-name-col", default=None, help="Columna con el nombre del área en el shapefile"
    )
    p.add_argument(
        "--buffer-km",
        type=float,
        default=5.0,
        help="Radio de buffer alrededor de áreas protegidas en km (default: 5)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cargar datos normalizados
    log.info("Cargando: %s", args.input)
    df = pd.read_excel(args.input)
    log.info("Filas cargadas: %d", len(df))

    # 2. Parsear coordenadas → GeoDataFrame
    log.info("Parseando coordenadas UTM...")
    gdf = build_geodataframe(df)
    parsed = gdf["coord_parsed"].sum()
    log.info("  Parseadas: %d / %d (%.1f%%)", parsed, len(gdf), parsed / len(gdf) * 100)

    # Reporte de métodos de parseo usados
    method_counts = gdf["coord_method"].value_counts()
    log.info("  Métodos: %s", method_counts.to_dict())

    # 3. Análisis espacial (si se provee shapefile)
    if args.protected:
        log.info("Cargando áreas protegidas: %s", args.protected)
        protected = load_protected_areas(args.protected)
        log.info("Intersectando con áreas protegidas (buffer=%g km)...", args.buffer_km)
        gdf = intersect_protected(
            gdf,
            protected,
            buffer_km=args.buffer_km,
            name_col=args.protected_name_col,
        )

    # 4. Resumen por región
    log.info("Generando resumen por región...")
    reg_df = region_summary(gdf)

    # 5. Guardar outputs
    # Excel con coordenadas
    out_geo = out_dir / "results_geo.xlsx"
    geo_df = gdf.drop(columns=["geometry"], errors="ignore")
    geo_df.to_excel(out_geo, index=False)
    log.info("Excel georreferenciado: %s", out_geo)

    # Excel resumen regional
    out_reg = out_dir / "region_summary.xlsx"
    reg_df.to_excel(out_reg, index=False)
    log.info("Resumen regional: %s", out_reg)

    # GeoJSON para QGIS / Mapbox / kepler.gl
    out_geojson = out_dir / "projects.geojson"
    gdf_valid = gdf[gdf["coord_parsed"]].copy()
    if not gdf_valid.empty:
        # Mantener solo columnas clave en el GeoJSON para peso razonable
        keep = [
            "archivo",
            "region_provincia_y_comuna",
            "tipo_de_generacion_eolica_fv_csp",
            "potencia_nominal_bruta_mw",
            "superficie_total_intervenida_ha",
            "vida_util_anos",
            "escaneado",
            "lon",
            "lat",
            "utm_zone",
            "coord_method",
            "inside_protected_area",
            "near_protected_area",
            "protected_area_name",
            "distance_to_protected_km",
            "geometry",
        ]
        keep = [c for c in keep if c in gdf_valid.columns]
        gdf_valid[keep].to_file(out_geojson, driver="GeoJSON")
        log.info("GeoJSON: %s (%d proyectos)", out_geojson, len(gdf_valid))

    # 6. Resumen final
    log.info("── Resumen ──────────────────────────────────")
    log.info("  Proyectos georreferenciados : %d / %d", parsed, len(gdf))
    log.info("  No parseables               : %d", len(gdf) - parsed)
    log.info("  Regiones en el dataset      : %d", reg_df["region"].nunique())
    if "inside_protected_area" in gdf.columns:
        log.info("  Dentro de áreas protegidas  : %d", gdf["inside_protected_area"].sum())
        log.info(
            "  Cerca (<%g km)               : %d", args.buffer_km, gdf["near_protected_area"].sum()
        )
    log.info("─────────────────────────────────────────────")
    return 0


if __name__ == "__main__":
    sys.exit(main())

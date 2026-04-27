"""
geo/spatial_analysis.py — Análisis espacial sobre proyectos georreferenciados.

Fixes v2:
  - region_summary: usa 'FV' y 'Eólica' (valores post-normalización, no pre)
  - region_summary: regex cubre 'Región del/de' para evitar duplicados O'Higgins
  - build_geodataframe: agrega columna datum_warning
"""

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from rca_extractor.geo.coord_parser import parse_utm, UTMPoint

log = logging.getLogger("rca_extractor")

COORD_COL = "coordenadas_utm_geograficas_punto_representativo"
WGS84 = "EPSG:4326"
UTM19S = "EPSG:32719"

# ── Normalización de nombres de región ───────────────────────────────────────
# Mapea variantes textuales → nombre canónico oficial
_REGION_ALIASES: dict[str, str] = {
    # O'Higgins — múltiples variantes en RCAs
    "libertador general bernardo o'higgins": "O'Higgins",
    "libertador general bernardo o’higgins": "O'Higgins",
    "libertador bernardo o'higgins": "O'Higgins",
    "libertador bernardo o’higgins": "O'Higgins",
    "libertador gral. bernardo o'higgins": "O'Higgins",
    "o'higgins": "O'Higgins",
    "o’higgins": "O'Higgins",
    # Metropolitana
    "metropolitana de santiago": "Metropolitana",
    "metropolitana": "Metropolitana",
    "región metropolitana de santiago": "Metropolitana",
    "región metropolitana": "Metropolitana",
    # Magallanes
    "magallanes y la antártica chilena": "Magallanes",
    "magallanes y de la antártica chilena": "Magallanes",
    # Biobío
    "biobío": "Biobío",
    "bío bío": "Biobío",
    "bio-bío": "Biobío",
    # Aysén
    "aysén del general carlos ibáñez del campo": "Aysén",
    "aysén del gral. carlos ibáñez del campo": "Aysén",
    "aysen": "Aysén",
    # Araucanía
    "la araucanía": "La Araucanía",
    "araucanía": "La Araucanía",
    # Valparaíso
    "región valparaíso": "Valparaíso",
}

_REGION_RE = re.compile(r"Región\s+(?:(?:de(?:l)?|del)\s+)?([^,]+)", re.I)


def _normalize_region(raw: str) -> str:
    """Extrae y normaliza el nombre de región desde el campo región/provincia/comuna."""
    if not raw or pd.isna(raw):
        return "Sin datos"
    m = _REGION_RE.search(str(raw))
    if not m:
        return str(raw).split(",")[0].strip()
    name = m.group(1).strip().rstrip(".")
    return _REGION_ALIASES.get(name.lower(), name)


# ── GeoDataFrame ─────────────────────────────────────────────────────────────


def build_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Parsea coordenadas UTM y construye GeoDataFrame de puntos WGS84.

    Agrega columnas:
      lon, lat              — WGS84
      utm_easting/northing  — UTM original
      utm_zone              — huso (18 o 19)
      coord_method          — patrón de parseo usado
      coord_parsed          — bool
      datum_warning         — string si datum no es WGS84, vacío si WGS84
      region_norm           — nombre de región normalizado
    """
    results = []
    parsed, failed = 0, 0

    for _, row in df.iterrows():
        raw = row.get(COORD_COL, None)
        pt: Optional[UTMPoint] = parse_utm(str(raw)) if pd.notna(raw) else None

        base = row.to_dict()
        base["region_norm"] = _normalize_region(str(row.get("region_provincia_y_comuna", "")))

        if pt:
            results.append(
                {
                    **base,
                    "lon": pt.lon,
                    "lat": pt.lat,
                    "utm_easting": pt.easting,
                    "utm_northing": pt.northing,
                    "utm_zone": pt.zone,
                    "coord_method": pt.method,
                    "coord_parsed": True,
                    "datum_warning": pt.datum_warning if pt.datum_warning else None,
                    "geometry": Point(pt.lon, pt.lat),
                }
            )
            parsed += 1
        else:
            results.append(
                {
                    **base,
                    "lon": None,
                    "lat": None,
                    "utm_easting": None,
                    "utm_northing": None,
                    "utm_zone": None,
                    "coord_method": None,
                    "coord_parsed": False,
                    "datum_warning": None,
                    "geometry": None,
                }
            )
            failed += 1

    log.info("Coordenadas parseadas: %d | No parseadas: %d", parsed, failed)
    return gpd.GeoDataFrame(results, geometry="geometry", crs=WGS84)


# ── Áreas protegidas ──────────────────────────────────────────────────────────


def load_protected_areas(shapefile_path: str | Path) -> gpd.GeoDataFrame:
    """
    Carga shapefile de áreas protegidas (ej. SNASPE).
    Nota de Versión (CB-02): Asegurarse de documentar la versión o fecha de descarga
    del shapefile en el nombre del archivo (ej. `SNASPE_2023_WGS84.shp`) ya que 
    CONAF actualiza regularmente los linderos.
    """
    path = Path(shapefile_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Shapefile no encontrado: {path}\n"
            "Descarga SNASPE desde:\n"
            "  https://www.conaf.cl/nuestros-bosques/bosques-en-chile/"
            "sistema-nacional-de-areas-silvestres-protegidas/\n"
            "o sitios prioritarios desde:\n"
            "  https://www.mma.gob.cl/biodiversidad/sitios-prioritarios/"
        )
    gdf = gpd.read_file(path)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(WGS84)
    log.info("Áreas protegidas cargadas: %d polígonos", len(gdf))
    return gdf


def intersect_protected(
    projects: gpd.GeoDataFrame,
    protected: gpd.GeoDataFrame,
    buffer_km: float = 5.0,
    name_col: str | None = None,
) -> gpd.GeoDataFrame:
    """
    Añade flags inside_protected_area, near_protected_area y distance_to_protected_km.
    Usa UTM19S para cálculos de distancia en metros.
    """
    proj = projects.copy()
    proj["inside_protected_area"] = False
    proj["near_protected_area"] = False
    proj["protected_area_name"] = None
    proj["distance_to_protected_km"] = None

    has_geom = proj[proj["geometry"].notna() & proj["coord_parsed"]]
    if has_geom.empty:
        log.warning("Sin geometrías válidas para intersección.")
        return proj

    proj_utm = has_geom.to_crs(UTM19S)
    prot_utm = protected.to_crs(UTM19S)
    buffer_m = buffer_km * 1000

    for idx, row in proj_utm.iterrows():
        pt = row.geometry
        if pt is None:
            continue
        dists = prot_utm.geometry.distance(pt)
        min_d = dists.min()
        closest = dists.idxmin()
        dist_km = round(min_d / 1000, 3)
        proj.at[idx, "distance_to_protected_km"] = dist_km
        proj.at[idx, "inside_protected_area"] = min_d == 0
        proj.at[idx, "near_protected_area"] = min_d <= buffer_m
        if name_col and name_col in prot_utm.columns:
            proj.at[idx, "protected_area_name"] = prot_utm.at[closest, name_col]

    log.info(
        "Dentro: %d | Cerca (<%gkm): %d",
        proj["inside_protected_area"].sum(),
        buffer_km,
        proj["near_protected_area"].sum(),
    )
    return proj


# ── Resumen regional ──────────────────────────────────────────────────────────


def region_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Agrega métricas por región usando nombres de región normalizados.
    Usa los valores post-normalización del normalizer:
      tipo 'FV' (no 'Fotovoltaica'), 'Eólica', 'FV+CSP', 'Eólica+FV'
    """
    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    # Usar región normalizada si existe, sino derivar
    if "region_norm" not in df.columns:
        df["region_norm"] = df["region_provincia_y_comuna"].apply(_normalize_region)

    agg = (
        df.groupby("region_norm")
        .agg(
            n_proyectos=("archivo", "count"),
            potencia_total_mw=("potencia_nominal_bruta_mw", "sum"),
            potencia_media_mw=("potencia_nominal_bruta_mw", "mean"),
            superficie_total_ha=("superficie_total_intervenida_ha", "sum"),
            vida_util_media=("vida_util_anos", "mean"),
            # Fix: usar valores post-normalización ('FV' no 'Fotovoltaica')
            n_fotovoltaica=(
                "tipo_de_generacion_eolica_fv_csp",
                lambda x: x.str.contains(r"FV|[Ff]otovoltaica", na=False).sum(),
            ),
            n_eolica=(
                "tipo_de_generacion_eolica_fv_csp",
                lambda x: x.str.contains(r"Eólica|Eolica", na=False).sum(),
            ),
            n_georreferenciados=("coord_parsed", "sum"),
            n_datum_warnings=(
                "datum_warning",
                lambda x: x.notna().sum() if "datum_warning" in df.columns else 0,
            ),
        )
        .reset_index()
        .rename(columns={"region_norm": "region"})
    )

    for col in ["potencia_total_mw", "potencia_media_mw", "superficie_total_ha", "vida_util_media"]:
        agg[col] = agg[col].round(2)

    return agg.sort_values("n_proyectos", ascending=False).reset_index(drop=True)

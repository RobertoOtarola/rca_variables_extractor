"""
geo/spatial_analysis.py — Análisis espacial sobre los proyectos georreferenciados.

Funciones:
  - build_geodataframe()    : crea GeoDataFrame con puntos WGS84 de todos los proyectos
  - load_protected_areas()  : carga shapefile SNASPE / sitios prioritarios
  - intersect_protected()   : marca proyectos dentro o cerca de áreas protegidas
  - region_summary()        : agrega métricas por región
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from geo.coord_parser import parse_utm, UTMPoint

log = logging.getLogger("rca_extractor")

COORD_COL  = "coordenadas_utm_geograficas_punto_representativo"
WGS84      = "EPSG:4326"
UTM19S     = "EPSG:32719"   # para cálculos de distancia en metros


def build_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Parsea la columna de coordenadas y construye un GeoDataFrame de puntos WGS84.

    Agrega columnas:
      - lon, lat          : coordenadas WGS84
      - utm_easting/northing : coordenadas UTM originales
      - utm_zone          : huso detectado (18 o 19)
      - coord_method      : estrategia de parseo usada
      - coord_parsed      : bool — True si se pudo parsear
    """
    results = []
    parsed, failed = 0, 0

    for _, row in df.iterrows():
        raw = row.get(COORD_COL, None)
        pt: Optional[UTMPoint] = parse_utm(str(raw)) if pd.notna(raw) else None

        if pt:
            results.append({
                **row.to_dict(),
                "lon":           pt.lon,
                "lat":           pt.lat,
                "utm_easting":   pt.easting,
                "utm_northing":  pt.northing,
                "utm_zone":      pt.zone,
                "coord_method":  pt.method,
                "coord_parsed":  True,
                "geometry":      Point(pt.lon, pt.lat),
            })
            parsed += 1
        else:
            results.append({
                **row.to_dict(),
                "lon": None, "lat": None,
                "utm_easting": None, "utm_northing": None,
                "utm_zone": None, "coord_method": None,
                "coord_parsed": False, "geometry": None,
            })
            failed += 1

    log.info("Coordenadas parseadas: %d | No parseadas: %d", parsed, failed)

    gdf = gpd.GeoDataFrame(results, geometry="geometry", crs=WGS84)
    return gdf


def load_protected_areas(shapefile_path: str | Path) -> gpd.GeoDataFrame:
    """
    Carga un shapefile de áreas protegidas (SNASPE u otro).
    Reproyecta a WGS84 si es necesario.
    """
    path = Path(shapefile_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Shapefile no encontrado: {path}\n"
            "Descarga el shapefile SNASPE desde:\n"
            "  https://www.conaf.cl/nuestros-bosques/bosques-en-chile/sistema-nacional-de-areas-silvestres-protegidas/\n"
            "o sitios prioritarios desde:\n"
            "  https://www.mma.gob.cl/biodiversidad/sitios-prioritarios/"
        )
    gdf = gpd.read_file(path)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(WGS84)
    log.info("Áreas protegidas cargadas: %d polígonos (CRS: %s)", len(gdf), gdf.crs)
    return gdf


def intersect_protected(
    projects: gpd.GeoDataFrame,
    protected: gpd.GeoDataFrame,
    buffer_km: float = 5.0,
    name_col: str | None = None,
) -> gpd.GeoDataFrame:
    """
    Marca proyectos que intersectan o están dentro de `buffer_km` km de
    áreas protegidas.

    Agrega columnas al GeoDataFrame de proyectos:
      - inside_protected_area : bool — dentro del polígono
      - near_protected_area   : bool — dentro del buffer (incluye los de dentro)
      - protected_area_name   : nombre del área más cercana (si name_col definida)
      - distance_to_protected_km : distancia mínima al borde del área más cercana
    """
    proj = projects.copy()
    proj["inside_protected_area"]    = False
    proj["near_protected_area"]      = False
    proj["protected_area_name"]      = None
    proj["distance_to_protected_km"] = None

    # Solo proyectos con geometría válida
    has_geom = proj[proj["geometry"].notna() & proj["coord_parsed"]]
    if has_geom.empty:
        log.warning("Sin geometrías válidas para intersección espacial.")
        return proj

    # Reproyectar a UTM para cálculos de distancia correctos
    proj_utm  = has_geom.to_crs(UTM19S)
    prot_utm  = protected.to_crs(UTM19S)
    buffer_m  = buffer_km * 1000

    for idx, project_row in proj_utm.iterrows():
        pt = project_row.geometry
        if pt is None:
            continue

        # Distancias a todos los polígonos de áreas protegidas
        distances = prot_utm.geometry.distance(pt)
        min_dist  = distances.min()
        closest_i = distances.idxmin()

        dist_km = round(min_dist / 1000, 3)
        proj.at[idx, "distance_to_protected_km"] = dist_km
        proj.at[idx, "inside_protected_area"]    = (min_dist == 0)
        proj.at[idx, "near_protected_area"]       = (min_dist <= buffer_m)

        if name_col and name_col in prot_utm.columns:
            proj.at[idx, "protected_area_name"] = prot_utm.at[closest_i, name_col]

    inside = proj["inside_protected_area"].sum()
    near   = proj["near_protected_area"].sum()
    log.info("Dentro de área protegida: %d | Dentro de %g km: %d", inside, buffer_km, near)
    return proj


def region_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Agrega métricas clave por región para el dashboard.
    """
    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    # Extraer región limpia
    df["region"] = df["region_provincia_y_comuna"].str.extract(
        r"Región de ([^,]+)", expand=False
    ).str.strip()

    numeric = [
        "potencia_nominal_bruta_mw",
        "superficie_total_intervenida_ha",
        "intensidad_de_uso_de_suelo_ha_mw_1",
    ]

    agg = df.groupby("region").agg(
        n_proyectos          = ("archivo", "count"),
        potencia_total_mw    = ("potencia_nominal_bruta_mw", "sum"),
        potencia_media_mw    = ("potencia_nominal_bruta_mw", "mean"),
        superficie_total_ha  = ("superficie_total_intervenida_ha", "sum"),
        vida_util_media      = ("vida_util_anos", "mean"),
        n_fotovoltaica = ("tipo_de_generacion_eolica_fv_csp",
                                lambda x: x.str.contains('Fotovoltaica', na=False).sum()),
        n_eolica       = ("tipo_de_generacion_eolica_fv_csp",
                                lambda x: x.str.contains('Eólica', na=False).sum()),
    ).reset_index()

    for col in ["potencia_total_mw", "potencia_media_mw",
                "superficie_total_ha", "vida_util_media"]:
        agg[col] = agg[col].round(2)

    return agg.sort_values("n_proyectos", ascending=False)

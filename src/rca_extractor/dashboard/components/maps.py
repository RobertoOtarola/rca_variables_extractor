"""
dashboard/components/maps.py — Mapas geoespaciales para el dashboard.

Genera mapas interactivos Plotly scatter_mapbox para visualizar
proyectos ERNC georreferenciados en Chile.

Ejemplo:
    from rca_extractor.dashboard.components.maps import render_project_map
    fig = render_project_map(geo_df)
    st.plotly_chart(fig, use_container_width=True)
"""

from __future__ import annotations

from typing import Any, Optional

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


# ── Paleta por defecto ─────────────────────────────────────────────────────────

TECH_COLORS: dict[str, str] = {
    "FV": "#F59E0B",
    "Fotovoltaica": "#F59E0B",
    "Eólica": "#3B82F6",
    "CSP": "#EF4444",
    "Eólica+FV": "#8B5CF6",
    "FV+CSP": "#EC4899",
}

# Centroide y zoom para Chile
_CHILE_CENTER = {"lat": -30.0, "lon": -70.0}
_CHILE_ZOOM = 4


def render_project_map(
    df: pd.DataFrame,
    *,
    lat_col: str = "lat",
    lon_col: str = "lon",
    color_col: str = "tech",
    size_col: str = "potencia_nominal_bruta_mw",
    hover_name: str = "archivo",
    color_discrete_map: Optional[dict[str, str]] = None,
    mapbox_style: str = "carto-positron",
    height: int = 520,
    size_max: int = 18,
    center: Optional[dict[str, float]] = None,
    zoom: Optional[int] = None,
    hover_data: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> go.Figure:
    """
    Mapa scatter_mapbox de proyectos ERNC geolocalizados.

    Args:
        df: DataFrame con columnas lat/lon como mínimo.
        lat_col: Nombre de columna de latitud.
        lon_col: Nombre de columna de longitud.
        color_col: Columna para coloreado (categorías).
        size_col: Columna para tamaño de punto (numérica).
        hover_name: Columna para nombre en tooltip.
        mapbox_style: Estilo de mapa base (carto-positron, open-street-map, etc.).
        height: Altura del mapa en píxeles.
        size_max: Tamaño máximo de punto en píxeles.
        center: Dict con lat/lon del centro del mapa.
        zoom: Nivel de zoom inicial.
        hover_data: Datos adicionales para el tooltip.

    Returns:
        go.Figure configurada para render con st.plotly_chart().
    """
    if df.empty or lat_col not in df.columns or lon_col not in df.columns:
        # Devolver figura vacía con mensaje
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                dict(
                    text="Sin datos georreferenciados disponibles",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=16, color="#6B7280"),
                )
            ],
            height=height,
        )
        return fig

    map_df = df.dropna(subset=[lat_col, lon_col]).copy()
    if map_df.empty:
        fig = go.Figure()
        fig.update_layout(height=height)
        return fig

    # Columna de tamaño con clip para evitar puntos gigantes
    if size_col in map_df.columns:
        map_df["_size_px"] = map_df[size_col].clip(upper=300).fillna(10)
    else:
        map_df["_size_px"] = 10

    cmap = color_discrete_map or TECH_COLORS

    default_hover = {
        "potencia_nominal_bruta_mw": ":.1f",
        "region_provincia_y_comuna": True,
        lat_col: False,
        lon_col: False,
        "_size_px": False,
    }
    hover = hover_data if hover_data is not None else default_hover

    fig = px.scatter_mapbox(
        map_df,
        lat=lat_col,
        lon=lon_col,
        color=color_col if color_col in map_df.columns else None,
        color_discrete_map=cmap,
        size="_size_px",
        size_max=size_max,
        hover_name=hover_name if hover_name in map_df.columns else None,
        hover_data={k: v for k, v in hover.items() if k in map_df.columns or k == "_size_px"},
        zoom=zoom or _CHILE_ZOOM,
        center=center or _CHILE_CENTER,
        mapbox_style=mapbox_style,
        height=height,
        **kwargs,
    )
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        legend=dict(orientation="h", y=-0.05),
    )
    return fig

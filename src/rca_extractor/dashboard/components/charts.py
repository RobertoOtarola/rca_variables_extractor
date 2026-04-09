"""
dashboard/components/charts.py — Gráficos reutilizables para el dashboard.

Centraliza la creación de figuras Plotly con los estilos y paletas de color
del proyecto. Las funciones devuelven objetos go.Figure que el caller
puede renderizar con st.plotly_chart().

Ejemplo:
    from rca_extractor.dashboard.components.charts import render_histogram
    fig = render_histogram(df, column="potencia_nominal_bruta_mw", nbins=30)
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

_DEFAULT_MARGIN = dict(t=4, b=4, l=4, r=4)


def render_histogram(
    df: pd.DataFrame,
    column: str,
    *,
    color: Optional[str] = None,
    color_discrete_map: Optional[dict[str, str]] = None,
    nbins: int = 30,
    log_y: bool = False,
    height: int = 280,
    labels: Optional[dict[str, str]] = None,
    median_line: bool = False,
    **kwargs: Any,
) -> go.Figure:
    """
    Histograma configurable con estilos del proyecto.

    Args:
        df: DataFrame fuente.
        column: Nombre de la columna a graficar.
        color: Columna para color (e.g. "tech").
        color_discrete_map: Mapa de colores (default: TECH_COLORS).
        nbins: Número de bins.
        log_y: Escala logarítmica en eje Y.
        height: Altura en píxeles.
        labels: Etiquetas personalizadas para ejes.
        median_line: Si True, agrega línea vertical en la mediana.
    """
    plot_df = df.dropna(subset=[column])
    cmap = color_discrete_map or (TECH_COLORS if color else None)

    fig = px.histogram(
        plot_df,
        x=column,
        color=color,
        color_discrete_map=cmap,
        nbins=nbins,
        log_y=log_y,
        height=height,
        labels=labels,
        **kwargs,
    )
    fig.update_layout(
        bargap=0.04,
        margin=_DEFAULT_MARGIN,
        showlegend=bool(color),
    )

    if median_line:
        median_val = plot_df[column].median()
        fig.add_vline(
            x=float(median_val),
            line_dash="dash",
            line_color="#6B7280",
            annotation_text=f"Mediana {median_val:.1f}",
            annotation_position="top right",
        )

    return fig


def render_scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: Optional[str] = None,
    color_discrete_map: Optional[dict[str, str]] = None,
    log_x: bool = False,
    log_y: bool = False,
    height: int = 280,
    hover_data: Optional[list[str]] = None,
    labels: Optional[dict[str, str]] = None,
    marker_size: int = 5,
    marker_opacity: float = 0.7,
    **kwargs: Any,
) -> go.Figure:
    """
    Scatter plot configurable.

    Args:
        df: DataFrame fuente.
        x: Columna eje X.
        y: Columna eje Y.
        color: Columna para color.
        log_x: Escala logarítmica en X.
        log_y: Escala logarítmica en Y.
        hover_data: Columnas adicionales en hover tooltip.
    """
    plot_df = df.dropna(subset=[x, y])
    cmap = color_discrete_map or (TECH_COLORS if color else None)

    fig = px.scatter(
        plot_df,
        x=x,
        y=y,
        color=color,
        color_discrete_map=cmap,
        log_x=log_x,
        log_y=log_y,
        height=height,
        hover_data=hover_data,
        labels=labels,
        **kwargs,
    )
    fig.update_traces(marker_size=marker_size, marker_opacity=marker_opacity)
    fig.update_layout(
        margin=_DEFAULT_MARGIN,
        legend=dict(orientation="h", y=1.12) if color else {},
    )
    return fig


def render_box_plot(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: Optional[str] = None,
    color_discrete_map: Optional[dict[str, str]] = None,
    height: int = 280,
    labels: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> go.Figure:
    """
    Box plot configurable.

    Args:
        df: DataFrame fuente.
        x: Columna eje X (categorías).
        y: Columna eje Y (valores).
        color: Columna para color.
    """
    plot_df = df.dropna(subset=[y])
    cmap = color_discrete_map or (TECH_COLORS if color else None)

    fig = px.box(
        plot_df,
        x=x,
        y=y,
        color=color,
        color_discrete_map=cmap,
        height=height,
        labels=labels,
        **kwargs,
    )
    fig.update_layout(
        showlegend=False,
        margin=_DEFAULT_MARGIN,
    )
    return fig

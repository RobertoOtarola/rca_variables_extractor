import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from rca_extractor.lca.calculator import calculate
from rca_extractor.post_processing.db_storage import get_engine
from rca_extractor.config import DB_URL

# ── Sistema de Datos ──────────────────────────────────────────────────────────
engine = get_engine(DB_URL)

# ── Config página ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RCA Extractor · Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Se asume que el Dashboard se corre en el entorno donde rca_extractor está instalado

TECH_COLORS = {
    "FV": "#F59E0B",
    "Fotovoltaica": "#F59E0B",
    "Eólica": "#3B82F6",
    "CSP": "#EF4444",
    "Eólica+FV": "#8B5CF6",
    "FV+CSP": "#EC4899",
}
TECH_ORDER = ["FV", "Eólica", "CSP", "Eólica+FV", "FV+CSP"]


# ── Carga ──────────────────────────────────────────────────────────────────────


@st.cache_data
def load_main() -> pd.DataFrame:
    """Carga los datos directamente de la base de datos SQLite."""
    try:
        df = pd.read_sql("SELECT * FROM projects", engine)
        if df.empty:
            return df

        # Normalizar nombres de columna para compatibilidad con la lógica del Dashboard
        # El dashboard espera 'region' y 'tech' como columnas normalizadas
        
        # Columna región (simplificada ya que el pipeline ya normaliza o debería)
        if "region_norm" in df.columns:
            df["region"] = df["region_norm"]
        else:
            df["region"] = df["region_provincia_y_comuna"].str.extract(r"Región\s+(?:de(?:l)?\s+)?([^,]+)")[0].str.strip()
            
        _aliases = {
            "Libertador General Bernardo O'Higgins": "O'Higgins",
            "Libertador Bernardo O'Higgins": "O'Higgins",
            "Metropolitana de Santiago": "Metropolitana",
            "Magallanes y la Antártica Chilena": "Magallanes",
            "Bío Bío": "Biobío",
        }
        df["region"] = df["region"].replace(_aliases)

        # Columna tech
        df["tech"] = df["tipo_de_generacion_eolica_fv_csp"].astype(str).replace({
            "Eólica + Fotovoltaica": "Eólica+FV",
            "Fotovoltaica + CSP": "FV+CSP",
            "Fotovoltaica": "FV",
        })
        return df
    except Exception as e:
        st.error(f"Error cargando base de datos: {e}")
        return pd.DataFrame()


@st.cache_data
def compute_lca(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula ACV si las columnas no existen ya (results_lca.xlsx las incluye)."""
    if "lifetime_energy_mwh" not in df.columns:
        rows = [vars(calculate(r)) for _, r in df.iterrows()]
        lca = pd.DataFrame(rows)
        df = pd.concat([df, lca.drop(columns=["archivo", "tech"], errors="ignore")], axis=1)
    return df


@st.cache_data
def load_geo() -> pd.DataFrame:
    """Carga proyectos con georreferenciación desde la BD."""
    try:
        # Buscamos proyectos en la tabla que tengan coordenadas cargadas
        # El pipeline de geo debe haber llenado lon/lat en la tabla 'projects'
        df = pd.read_sql("SELECT * FROM projects", engine)
        
        # Filtramos los que tengan lat/lon (asumiendo que existen las columnas)
        if "lat" not in df.columns:
             # Si no hay columnas en BD, intentamos leer el Excel legacy por ahora
             # o simplemente devolvemos vacío si queremos ser puristas con la BD.
             return pd.DataFrame()

        gdf = df.dropna(subset=["lat", "lon"])
        gdf["tech"] = gdf["tipo_de_generacion_eolica_fv_csp"].astype(str).replace({
            "Eólica + Fotovoltaica": "Eólica+FV",
            "Fotovoltaica + CSP": "FV+CSP",
            "Fotovoltaica": "FV",
        })
        return gdf
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_region_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula resumen regional dinámicamente desde el dataframe principal."""
    if df.empty: return pd.DataFrame()
    return df.groupby("region").agg(
        n_proyectos=("archivo", "count"),
        potencia_total_mw=("potencia_nominal_bruta_mw", "sum")
    ).reset_index()


# ── Sidebar ────────────────────────────────────────────────────────────────────


def render_sidebar(df: pd.DataFrame):
    with st.sidebar:
        st.markdown("## ⚡ RCA Extractor")
        st.caption("430 RCAs · SEIA Chile")
        st.divider()

        techs = ["Todas"] + [t for t in TECH_ORDER if t in df["tech"].values]
        sel_tech = st.selectbox("Tecnología", techs)

        regions = ["Todas"] + sorted(df["region"].dropna().unique())
        sel_reg = st.selectbox("Región", regions)

        mw_vals = df["potencia_nominal_bruta_mw"].dropna()
        mw_min, mw_max = float(mw_vals.min()), float(mw_vals.max())
        sel_mw = st.slider("Potencia (MW)", mw_min, mw_max, (mw_min, mw_max), step=0.5)

        st.divider()
        st.caption("Pipeline completado")
        for label, done in [
            ("Fase 1 · Extracción LLM", True),
            ("Fase 2 · Post-procesamiento", True),
            ("Fase 3 · Geoespacial", True),
            ("Fase 4 · ACV + API + Dashboard", True),
        ]:
            st.markdown(f"{'✅' if done else '🚧'} {label}")

    return sel_tech, sel_reg, sel_mw


def apply_filters(df, sel_tech, sel_reg, sel_mw):
    mask = df["potencia_nominal_bruta_mw"].between(sel_mw[0], sel_mw[1], inclusive="both")
    if sel_tech != "Todas":
        mask &= df["tech"] == sel_tech
    if sel_reg != "Todas":
        mask &= df["region"] == sel_reg
    return df[mask]


# ── KPIs ───────────────────────────────────────────────────────────────────────


def render_kpis(df: pd.DataFrame):
    pot_gw = df["potencia_nominal_bruta_mw"].sum() / 1000
    sup_kha = df["superficie_total_intervenida_ha"].sum() / 1000
    twh = df["lifetime_energy_mwh"].sum() / 1e6 if "lifetime_energy_mwh" in df else 0
    ghg_mt = df["ghg_total_kt"].sum() / 1000 if "ghg_total_kt" in df else 0
    vida_med = df["vida_util_anos"].median()

    cols = st.columns(5)
    cols[0].metric("Proyectos", f"{len(df):,}")
    cols[1].metric("Potencia total", f"{pot_gw:.1f} GW")
    cols[2].metric("Superficie", f"{sup_kha:.0f} k·ha")
    cols[3].metric("Energía vida útil", f"{twh:.0f} TWh")
    cols[4].metric("GEI embebido est.", f"{ghg_mt:.1f} Mt CO₂-eq")


# ── Gráficos sección 1 — Overview ─────────────────────────────────────────────


def render_overview(df: pd.DataFrame):
    c1, c2, c3 = st.columns([1, 1.4, 1])

    # Donut tecnología
    with c1:
        st.markdown("**Mix tecnológico**")
        tech_s = df["tech"].value_counts().reset_index()
        tech_s.columns = ["tech", "n"]
        fig = px.pie(
            tech_s,
            values="n",
            names="tech",
            color="tech",
            color_discrete_map=TECH_COLORS,
            hole=0.52,
            height=280,
        )
        fig.update_traces(
            textinfo="percent+label", textposition="outside", pull=[0.03] * len(tech_s)
        )
        fig.update_layout(showlegend=False, margin=dict(t=4, b=4, l=4, r=4))
        st.plotly_chart(fig, use_container_width=True)

    # Proyectos + potencia por región
    with c2:
        st.markdown("**Potencia instalada por región (MW)**")
        reg = (
            df.groupby("region")
            .agg(potencia=("potencia_nominal_bruta_mw", "sum"), n=("archivo", "count"))
            .reset_index()
            .sort_values("potencia", ascending=True)
            .tail(12)
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=reg["potencia"],
                y=reg["region"],
                orientation="h",
                name="MW",
                marker_color="#3B82F6",
                text=reg["potencia"].round(0).astype(int),
                textposition="outside",
            )
        )
        fig.update_layout(
            height=280,
            showlegend=False,
            margin=dict(t=4, b=4, l=4, r=60),
            xaxis_title="MW",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Distribución vida útil
    with c3:
        st.markdown("**Vida útil (años)**")
        vu = df["vida_util_anos"].dropna()
        fig = px.histogram(vu, nbins=20, height=280, color_discrete_sequence=["#10B981"])
        fig.update_layout(
            showlegend=False,
            bargap=0.05,
            margin=dict(t=4, b=4, l=4, r=4),
            xaxis_title="Años",
            yaxis_title="Proyectos",
        )
        fig.add_vline(
            x=float(vu.median()),
            line_dash="dash",
            line_color="#6B7280",
            annotation_text=f"Mediana {vu.median():.0f}a",
            annotation_position="top right",
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Gráficos sección 2 — Uso de suelo y potencia ─────────────────────────────


def render_land_power(df: pd.DataFrame):
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Distribución potencia nominal (MW, escala log)**")
        plot_df = df.dropna(subset=["potencia_nominal_bruta_mw"])
        fig = px.histogram(
            plot_df,
            x="potencia_nominal_bruta_mw",
            color="tech",
            color_discrete_map=TECH_COLORS,
            nbins=45,
            log_y=True,
            height=270,
            labels={"potencia_nominal_bruta_mw": "MW", "tech": "Tecnología"},
        )
        fig.update_layout(
            bargap=0.04, margin=dict(t=4, b=4, l=4, r=4), legend=dict(orientation="h", y=1.12)
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**Potencia vs Intensidad uso de suelo**")
        sc = df.dropna(subset=["potencia_nominal_bruta_mw", "intensidad_de_uso_de_suelo_ha_mw_1"])
        fig = px.scatter(
            sc,
            x="potencia_nominal_bruta_mw",
            y="intensidad_de_uso_de_suelo_ha_mw_1",
            color="tech",
            color_discrete_map=TECH_COLORS,
            log_x=True,
            height=270,
            hover_data=["archivo", "region"],
            labels={
                "potencia_nominal_bruta_mw": "Potencia (MW)",
                "intensidad_de_uso_de_suelo_ha_mw_1": "ha/MW",
                "tech": "",
            },
        )
        fig.update_traces(marker_size=5, marker_opacity=0.7)
        fig.update_layout(margin=dict(t=4, b=4, l=4, r=4), legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)


# ── Sección ACV ────────────────────────────────────────────────────────────────


def render_lca(df: pd.DataFrame):
    st.subheader("⚗️ Análisis de Ciclo de Vida (ACV)")
    st.caption(
        "GEI estimados con factores IPCC AR6 · Agua de RCA cuando disponible, benchmark NREL si no · Tierra comparada con Ong et al. (2013)"
    )

    c1, c2, c3, c4 = st.columns(4)
    twh = df["lifetime_energy_mwh"].sum() / 1e6
    ghg = df["ghg_total_kt"].sum()
    water_rca = (df.get("water_source", pd.Series()) == "rca").sum()
    land_high = (df.get("land_benchmark", pd.Series()) == "HIGH").sum()
    c1.metric("Energía total vida útil", f"{twh:.0f} TWh")
    c2.metric("GEI total estimado", f"{ghg:,.0f} kt CO₂-eq")
    c3.metric("Proyectos con agua RCA", f"{water_rca}")
    c4.metric("Uso suelo alto (>2× ref)", f"{land_high}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**GEI estimado por tecnología (kt CO₂-eq)**")
        ghg_df = (
            df.groupby("tech")["ghg_total_kt"]
            .sum()
            .reset_index()
            .sort_values("ghg_total_kt", ascending=False)
        )
        fig = px.bar(
            ghg_df,
            x="tech",
            y="ghg_total_kt",
            color="tech",
            color_discrete_map=TECH_COLORS,
            labels={"ghg_total_kt": "kt CO₂-eq", "tech": ""},
            height=260,
            text_auto=".0f",
        )
        fig.update_layout(showlegend=False, margin=dict(t=4, b=4, l=4, r=4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Energía generada vida útil (TWh)**")
        e_df = (
            df.groupby("tech")["lifetime_energy_mwh"]
            .sum()
            .div(1e6)
            .reset_index()
            .rename(columns={"lifetime_energy_mwh": "TWh"})
            .sort_values("TWh", ascending=False)
        )
        fig = px.bar(
            e_df,
            x="tech",
            y="TWh",
            color="tech",
            color_discrete_map=TECH_COLORS,
            labels={"tech": ""},
            height=260,
            text_auto=".0f",
        )
        fig.update_layout(showlegend=False, margin=dict(t=4, b=4, l=4, r=4))
        st.plotly_chart(fig, use_container_width=True)

    with col3:
        st.markdown("**Consumo agua (m³/MWh) — proyectos con dato RCA**")
        w_df = df[df.get("water_source", pd.Series()) == "rca"].dropna(
            subset=["water_intensity_m3_mwh"]
        )
        if w_df.empty:
            st.info("Sin datos de agua en RCAs para el filtro actual.")
        else:
            fig = px.box(
                w_df,
                x="tech",
                y="water_intensity_m3_mwh",
                color="tech",
                color_discrete_map=TECH_COLORS,
                labels={"water_intensity_m3_mwh": "m³/MWh", "tech": ""},
                height=260,
            )
            fig.update_layout(showlegend=False, margin=dict(t=4, b=4, l=4, r=4))
            st.plotly_chart(fig, use_container_width=True)


# ── Mapa ───────────────────────────────────────────────────────────────────────


def render_map(geo_df: pd.DataFrame):
    st.subheader("🗺️ Mapa de proyectos georreferenciados")

    if geo_df.empty or "lat" not in geo_df.columns:
        st.info("Ejecuta `python -m geo.run` para generar coordenadas WGS84.")
        return

    map_df = geo_df.dropna(subset=["lat", "lon"]).copy()
    map_df["size_px"] = map_df["potencia_nominal_bruta_mw"].clip(upper=300).fillna(10)

    fig = px.scatter_mapbox(
        map_df,
        lat="lat",
        lon="lon",
        color="tech",
        color_discrete_map=TECH_COLORS,
        size="size_px",
        size_max=18,
        hover_name="archivo",
        hover_data={
            "potencia_nominal_bruta_mw": ":.1f",
            "region_provincia_y_comuna": True,
            "coord_method": True,
            "lat": False,
            "lon": False,
            "size_px": False,
        },
        zoom=4,
        center={"lat": -30, "lon": -70},
        mapbox_style="carto-positron",
        labels={
            "tech": "Tecnología",
            "potencia_nominal_bruta_mw": "MW",
            "region_provincia_y_comuna": "Región/Provincia/Comuna",
            "coord_method": "Método coord.",
        },
        height=520,
    )
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), legend=dict(orientation="h", y=-0.05))
    st.plotly_chart(fig, use_container_width=True)

    n_total = len(geo_df)
    n_mapped = len(map_df)
    pct = n_mapped / n_total * 100
    st.caption(
        f"**{n_mapped}** proyectos georreferenciados de {n_total} totales "
        f"(**{pct:.0f}%**). El {100 - pct:.0f}% restante referencia anexos sin "
        "coordenadas inline. "
        "Tamaño de cada punto proporcional a la potencia instalada (MW)."
    )


# ── Tabla filtrada ──────────────────────────────────────────────────────────────


def render_table(df: pd.DataFrame):
    with st.expander(f"📋 Tabla de datos filtrados ({len(df)} proyectos)"):
        cols = [
            "archivo",
            "region",
            "tech",
            "potencia_nominal_bruta_mw",
            "superficie_total_intervenida_ha",
            "intensidad_de_uso_de_suelo_ha_mw_1",
            "vida_util_anos",
            "emisiones_mp10_t_ano_1",
            "lifetime_energy_mwh",
            "ghg_total_kt",
        ]
        cols = [c for c in cols if c in df.columns]
        fmt = {
            "potencia_nominal_bruta_mw": "{:.1f}",
            "superficie_total_intervenida_ha": "{:.1f}",
            "intensidad_de_uso_de_suelo_ha_mw_1": "{:.2f}",
            "vida_util_anos": "{:.0f}",
            "emisiones_mp10_t_ano_1": "{:.2f}",
            "lifetime_energy_mwh": "{:,.0f}",
            "ghg_total_kt": "{:.1f}",
        }
        st.dataframe(
            df[cols]
            .reset_index(drop=True)
            .style.format({k: v for k, v in fmt.items() if k in cols}, na_rep="—"),
            use_container_width=True,
        )


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    df = load_main()
    if df.empty:
        st.error(
            "La base de datos está vacía o no se encuentra en `data/processed/rca_data.db`.\n\n"
            "Ejecuta el pipeline de extracción y post-procesamiento primero."
        )
        return

    df = compute_lca(df)
    geo_df = load_geo()
    sel_tech, sel_reg, sel_mw = render_sidebar(df)
    df_f = apply_filters(df, sel_tech, sel_reg, sel_mw)

    # Header
    st.markdown("# ⚡ RCA Extractor — Dashboard")
    st.caption(
        f"**{len(df_f)}** proyectos · "
        f"tech: {sel_tech} · región: {sel_reg} · "
        f"potencia: {sel_mw[0]:.0f}–{sel_mw[1]:.0f} MW"
    )

    render_kpis(df_f)

    st.divider()
    st.subheader("📊 Resumen general")
    render_overview(df_f)

    st.divider()
    st.subheader("🏗️ Potencia y uso de suelo")
    render_land_power(df_f)

    st.divider()
    render_lca(df_f)

    st.divider()
    render_map(geo_df)

    st.divider()
    render_table(df_f)


if __name__ == "__main__":
    main()

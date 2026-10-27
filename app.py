# -*- coding: utf-8 -*-
"""
Colombia Spatial Intelligence · Spatial VAR
Versión para Streamlit (local o Streamlit Community Cloud).

Datos:
  - PIB: DANE (se descarga y se guarda en caché local)
  - Internet: si existe internet_departamentos.csv en el repo se usa; si no, MinTIC
  - NTL: si existe ntl_departamentos.csv en el repo se usa; si no, Google Earth Engine
"""
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from libpysal.weights import Queen, lag_spatial
from esda.moran import Moran
from spreg import OLS, ML_Lag, ML_Error, GM_Combo

# set_page_config debe ser el primer comando de Streamlit
st.set_page_config(
    page_title="Colombia Spatial Intelligence",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache_datos_reales"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (SpatialVAR/1.0)"}

URL_GEOJSON = "https://raw.githubusercontent.com/caticoa3/colombia_mapa/master/co_2018_MGN_DPTO_POLITICO.geojson"
URL_PIB = "https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx"
URL_INTERNET = "https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv"
GEE_PROJECT = "utility-inquiry-512618-m6"
VARIABLES = ["ln_pib", "ln_internet", "ln_ntl"]


# =============================================================================
# UTILIDADES
# =============================================================================
def normalizar_nombres_deptos(serie):
    s = serie.astype(str).str.strip()
    mapa = {
        "bogota": "Bogotá D.C.", "bogotá": "Bogotá D.C.", "bogota d.c.": "Bogotá D.C.",
        "bogotá d.c.": "Bogotá D.C.", "distrito capital": "Bogotá D.C.",
        "san andres": "San Andrés, Providencia y Santa Catalina (Archipiélago)",
        "san andrés": "San Andrés, Providencia y Santa Catalina (Archipiélago)",
        "archipielago de san andres": "San Andrés, Providencia y Santa Catalina (Archipiélago)",
        "norte de santander": "Norte de Santander", "valle del cauca": "Valle del Cauca",
        "la guajira": "La Guajira", "atlantico": "Atlántico", "bolivar": "Bolívar",
        "boyaca": "Boyacá", "caqueta": "Caquetá", "choco": "Chocó", "cordoba": "Córdoba",
        "narino": "Nariño", "quindio": "Quindío", "vaupes": "Vaupés",
    }
    s_lower = s.str.lower()
    for k, v in mapa.items():
        s_lower = s_lower.replace(k, v)
    return s_lower.where(~s_lower.isin(mapa.values()), s_lower).str.title().replace({
        "Bogotá D.C.": "Bogotá D.C.",
        "San Andrés, Providencia Y Santa Catalina (Archipiélago)":
            "San Andrés, Providencia y Santa Catalina (Archipiélago)",
        "Norte De Santander": "Norte de Santander",
        "Valle Del Cauca": "Valle del Cauca",
        "La Guajira": "La Guajira",
    })


def unificar_nombre(nombre):
    n = str(nombre).lower().strip().replace(",", " ").replace(".", " ")
    n = " ".join(n.split())
    if "bogota" in n or "bogotá" in n: return "Bogotá D.C."
    if "san andres" in n or "archipielago" in n or "archipiélago" in n: return "San Andrés y Providencia"
    if "norte de santander" in n: return "Norte de Santander"
    if "valle del cauca" in n: return "Valle del Cauca"
    if "la guajira" in n: return "La Guajira"
    if "atlantico" in n or "atlántico" in n: return "Atlántico"
    if "bolivar" in n or "bolívar" in n: return "Bolívar"
    if "boyaca" in n or "boyacá" in n: return "Boyacá"
    if "caqueta" in n or "caquetá" in n: return "Caquetá"
    if "choco" in n or "chocó" in n: return "Chocó"
    if "cordoba" in n or "córdoba" in n: return "Córdoba"
    if "narino" in n or "nariño" in n: return "Nariño"
    if "quindio" in n or "quindío" in n: return "Quindío"
    if "vaupes" in n or "vaupés" in n: return "Vaupés"
    return str(nombre).strip().title()


def _num(x):
    try:
        return float(np.asarray(x).flatten()[0])
    except Exception:
        return np.nan


# =============================================================================
# CARGA DE DATOS
# =============================================================================
def cargar_geometrias():
    gdf = gpd.read_file(URL_GEOJSON)
    if "DPTO_CNMBR" in gdf.columns:
        gdf = gdf.rename(columns={"DPTO_CNMBR": "departamento", "DPTO_CCDGO": "cod_dpto"})
    elif "NOM_DEP" in gdf.columns:
        gdf = gdf.rename(columns={"NOM_DEP": "departamento", "COD_DEP": "cod_dpto"})
    gdf["departamento"] = normalizar_nombres_deptos(gdf["departamento"])
    return gdf.to_crs(4326).sort_values("departamento").reset_index(drop=True)


def cargar_pib():
    ruta = CACHE_DIR / "anex-PIBDep-TotalDep-2025pr.xlsx"
    if not ruta.exists():
        r = requests.get(URL_PIB, headers=HEADERS, timeout=180)
        r.raise_for_status()
        ruta.write_bytes(r.content)

    df_raw = pd.read_excel(ruta, sheet_name="Cuadro 1", header=None)
    años = []
    for a in df_raw.iloc[9, 2:23].tolist():
        s = str(a).replace(".0", "").replace("p", "").replace("pr", "").strip()
        años.append(int("".join(ch for ch in s if ch.isdigit())))

    wide = df_raw.iloc[11:45, [0, 1] + list(range(2, 23))].copy()
    wide.columns = ["cod_dpto", "departamento"] + años
    wide = wide.dropna(subset=["departamento"])
    wide["departamento"] = normalizar_nombres_deptos(wide["departamento"])
    df_pib = wide.melt(id_vars=["cod_dpto", "departamento"], value_vars=años,
                       var_name="año", value_name="pib_millones")
    df_pib["año"] = df_pib["año"].astype(int)
    df_pib["pib_millones"] = pd.to_numeric(df_pib["pib_millones"], errors="coerce")
    return df_pib.dropna(subset=["pib_millones"])


def cargar_internet():
    ruta_agg = BASE_DIR / "internet_departamentos.csv"
    if ruta_agg.exists():
        return pd.read_csv(ruta_agg)

    ruta = CACHE_DIR / "internet_fijo_n48w-gutb.csv"
    if not ruta.exists():
        r = requests.get(URL_INTERNET + "?$limit=3000000", headers=HEADERS, timeout=300)
        r.raise_for_status()
        ruta.write_bytes(r.content)

    raw = pd.read_csv(ruta, low_memory=False)
    raw = raw.rename(columns={"anno": "año", "no_de_accesos": "accesos"})
    raw["año"] = pd.to_numeric(raw["año"], errors="coerce")
    raw["accesos"] = pd.to_numeric(raw["accesos"], errors="coerce").fillna(0)
    raw["departamento"] = normalizar_nombres_deptos(raw["departamento"])
    df = (raw.groupby(["año", "departamento"], as_index=False)["accesos"]
             .sum().rename(columns={"accesos": "accesos_internet"}))
    return df[~df["departamento"].str.contains("Colombia", case=False, na=False)]


def iniciar_gee():
    """Usa una cuenta de servicio en st.secrets['gee'] si existe."""
    import ee
    if "gee" in st.secrets:
        info = dict(st.secrets["gee"])
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
        ee.Initialize(creds, project=info.get("project_id", GEE_PROJECT))
    else:
        ee.Initialize(project=GEE_PROJECT)
    return ee


def cargar_ntl(gdf, años=range(2015, 2025)):
    ruta_csv = BASE_DIR / "ntl_departamentos.csv"
    if ruta_csv.exists():
        return pd.read_csv(ruta_csv)

    ee = iniciar_gee()
    coleccion = ee.ImageCollection("NOAA/VIIRS/DNB/ANNUAL_V21").select("average")
    features = []
    for idx, row in gdf.iterrows():
        try:
            geom = ee.Geometry.Polygon(list(row.geometry.exterior.coords))
        except Exception:
            geom = ee.Geometry(row.geometry.__geo_interface__)
        features.append(ee.Feature(geom, {"departamento": row["departamento"], "id": int(idx)}))
    fc = ee.FeatureCollection(features)

    resultados = []
    for año in años:
        img = coleccion.filter(ee.Filter.calendarRange(año, año, "year")).first()
        try:
            img.get("system:index").getInfo()
        except Exception:
            continue
        info = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=500).getInfo()
        for f in info["features"]:
            p = f["properties"]
            resultados.append({"año": año, "departamento": p["departamento"],
                               "ntl_mean": p.get("mean", np.nan)})
    df = pd.DataFrame(resultados)
    df.to_csv(ruta_csv, index=False)
    return df


# =============================================================================
# MODELOS
# =============================================================================
def seleccionar_modelo_espacial(y, X, W, nombre_y, nombre_x):
    resultados = {}
    for nom, fn in [
        ("OLS", lambda: OLS(y, X, w=W, spat_diag=True, name_y=nombre_y, name_x=nombre_x)),
        ("SAR", lambda: ML_Lag(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SEM", lambda: ML_Error(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SAC", lambda: GM_Combo(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SDM", lambda: ML_Lag(y, X, w=W, slx_lags=1, name_y=nombre_y, name_x=nombre_x)),
    ]:
        try:
            m = fn()
            resultados[nom] = {"modelo": m, "aic": _num(getattr(m, "aic", np.nan)),
                               "rho": getattr(m, "rho", None)}
        except Exception:
            pass
    valid = {k: v for k, v in resultados.items() if not np.isnan(v["aic"])}
    mejor = min(valid, key=lambda k: valid[k]["aic"]) if valid else None
    return resultados, mejor


def descomposicion_impactos(modelo, W):
    if not hasattr(modelo, "rho") or modelo.rho is None:
        return None
    rho = float(modelo.rho)
    betas = np.asarray(modelo.betas).flatten()
    N = W.n
    W_mat = W.full()[0]
    S = np.linalg.inv(np.eye(N) - rho * W_mat)
    nombres = list(modelo.name_x) if getattr(modelo, "name_x", None) else []
    nombres_orig = [n for n in nombres if not str(n).upper().startswith(("W_", "W "))]
    n_orig = len(nombres_orig) or (len(nombres) // 2)
    if not nombres_orig:
        nombres_orig = nombres[:n_orig]
    out = {}
    for i in range(n_orig):
        if i + 1 >= len(betas):
            continue
        b = float(betas[i + 1])
        theta = float(betas[1 + n_orig + i]) if (1 + n_orig + i) < len(betas) else 0.0
        M = S @ (b * np.eye(N) + theta * W_mat)
        d = float(np.mean(np.diag(M)))
        t = float(np.mean(M.sum(axis=1)))
        out[nombres_orig[i] if i < len(nombres_orig) else f"x{i+1}"] = {
            "directo": d, "indirecto": t - d, "total": t}
    return out


# =============================================================================
# PIPELINE COMPLETO (se ejecuta una sola vez y queda en caché)
# =============================================================================
@st.cache_resource(show_spinner="Cargando datos y estimando modelos espaciales…")
def pipeline():
    gdf = cargar_geometrias()
    df_pib = cargar_pib()
    df_internet = cargar_internet()
    df_ntl = cargar_ntl(gdf)

    años_comunes = [a for a in sorted(set(df_pib["año"]) & set(df_internet["año"]) & set(df_ntl["año"]))
                    if a >= 2017]
    df_pib_f = df_pib[df_pib["año"].isin(años_comunes)].copy()
    df_int_f = df_internet[df_internet["año"].isin(años_comunes)].copy()
    df_ntl_f = df_ntl[df_ntl["año"].isin(años_comunes)].copy()

    for d in (df_pib_f, df_int_f, df_ntl_f):
        d["departamento"] = d["departamento"].apply(unificar_nombre)
    gdf["departamento"] = gdf["departamento"].apply(unificar_nombre)

    df = (df_pib_f.merge(df_int_f, on=["año", "departamento"], how="inner")
                  .merge(df_ntl_f, on=["año", "departamento"], how="inner"))
    deptos_orden = sorted(df["departamento"].unique())
    gdf = gdf[gdf["departamento"].isin(deptos_orden)].drop_duplicates("departamento")
    gdf = gdf.set_index("departamento").loc[deptos_orden].reset_index()
    df["departamento"] = pd.Categorical(df["departamento"], categories=deptos_orden, ordered=True)
    df = df.sort_values(["año", "departamento"]).reset_index(drop=True)
    df["ln_pib"] = np.log(df["pib_millones"].clip(1))
    df["ln_internet"] = np.log(df["accesos_internet"].clip(1))
    df["ln_ntl"] = np.log(df["ntl_mean"].clip(0.01))

    W = Queen.from_dataframe(gdf, ids=gdf.index.tolist())
    W.transform = "r"

    años_disp = sorted(df["año"].unique())
    año_t, año_tm1 = años_disp[-1], años_disp[-2]
    df_t = df[df["año"] == año_t].set_index("departamento").loc[deptos_orden]
    df_tm1 = df[df["año"] == año_tm1].set_index("departamento").loc[deptos_orden]

    y1 = df_t["ln_pib"].values.reshape(-1, 1)
    y2 = df_t["ln_internet"].values.reshape(-1, 1)
    X = np.column_stack([df_tm1["ln_pib"].values, df_tm1["ln_internet"].values, df_t["ln_ntl"].values])
    nombres_x = ["ln_pib_lag", "ln_internet_lag", "ln_ntl"]

    res_pib, mejor_pib = seleccionar_modelo_espacial(y1, X, W, "ln_pib", nombres_x)
    res_int, mejor_int = seleccionar_modelo_espacial(y2, X, W, "ln_internet", nombres_x)

    impactos_pib = descomposicion_impactos(res_pib[mejor_pib]["modelo"], W) if mejor_pib else None
    impactos_int = descomposicion_impactos(res_int[mejor_int]["modelo"], W) if mejor_int else None

    gdf_plot = gdf.merge(df_t[VARIABLES].reset_index(), on="departamento")
    gdf_plot["lon"] = gdf_plot.geometry.centroid.x
    gdf_plot["lat"] = gdf_plot.geometry.centroid.y

    return dict(df=df, df_t=df_t, W=W, gdf_plot=gdf_plot, deptos=deptos_orden, año_t=año_t,
                res_pib=res_pib, mejor_pib=mejor_pib, res_int=res_int, mejor_int=mejor_int,
                impactos_pib=impactos_pib, impactos_int=impactos_int)


# =============================================================================
# VISUALIZACIONES
# =============================================================================
def escala(variable):
    return "YlOrRd" if "pib" in variable else ("Blues" if "internet" in variable else "Inferno")


def crear_mapa(D, variable):
    g = D["gdf_plot"]
    kwargs = dict(
        geojson=g.__geo_interface__, locations=g.index, color=variable,
        hover_name="departamento",
        center={"lat": 4.5, "lon": -74}, zoom=4.3, opacity=0.78,
        color_continuous_scale=escala(variable), title=f"{variable} · {D['año_t']}",
    )
    if hasattr(px, "choropleth_map"):  # Plotly >= 5.24 (MapLibre)
        fig = px.choropleth_map(g, map_style="carto-darkmatter", **kwargs)
    else:  # Plotly antiguo
        fig = px.choropleth_mapbox(g, mapbox_style="carto-darkmatter", **kwargs)
    fig.update_layout(template="plotly_dark", height=520, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def crear_3d(D, variable):
    g = D["gdf_plot"]
    fig = go.Figure(go.Scatter3d(
        x=g["lon"], y=g["lat"], z=g[variable], mode="markers+text",
        text=g["departamento"], textposition="top center",
        textfont=dict(size=8, color="white"),
        marker=dict(size=9, color=g[variable], colorscale=escala(variable), opacity=0.9,
                    colorbar=dict(title=variable), line=dict(width=0.5, color="white")),
        hovertemplate="<b>%{text}</b><br>%{z:.3f}<extra></extra>",
    ))
    fig.update_layout(title=f"Topografía 3D · {variable} ({D['año_t']})", template="plotly_dark",
                      scene=dict(xaxis_title="Lon", yaxis_title="Lat", zaxis_title=variable),
                      height=520, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def crear_moran(D, variable):
    y = D["df_t"][variable].values
    yl = lag_spatial(D["W"], y)
    mi = Moran(y, D["W"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y, y=yl, mode="markers", text=D["deptos"],
        marker=dict(size=11, color=y, colorscale="Viridis", line=dict(color="white", width=1)),
        hovertemplate="%{text}<br>y=%{x:.2f} · Wy=%{y:.2f}<extra></extra>", showlegend=False))
    b, a = np.polyfit(y, yl, 1)
    xs = np.linspace(y.min(), y.max(), 40)
    fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines",
                             line=dict(color="tomato", dash="dash"), name=f"I={mi.I:.3f}"))
    fig.update_layout(title=f"Moran · {variable} (I={mi.I:.3f}, p={mi.p_sim:.3f})",
                      template="plotly_dark", height=420,
                      xaxis_title=variable, yaxis_title=f"W·{variable}")
    return fig


def crear_serie(D, depto):
    d = D["df"][D["df"]["departamento"] == depto]
    fig = go.Figure()
    for c, n, col in [("ln_pib", "ln(PIB)", "#f4a261"),
                      ("ln_internet", "ln(Internet)", "#2a9d8f"),
                      ("ln_ntl", "ln(NTL)", "#e9c46a")]:
        fig.add_trace(go.Scatter(x=d["año"], y=d[c], mode="lines+markers", name=n, line=dict(color=col)))
    fig.update_layout(title=f"Serie temporal · {depto}", template="plotly_dark", height=400)
    return fig


def tabla_modelos(D):
    rows = []
    for eq, res, best in [("PIB", D["res_pib"], D["mejor_pib"]),
                          ("Internet", D["res_int"], D["mejor_int"])]:
        for nom, v in res.items():
            rows.append({"Ecuación": eq, "Modelo": nom, "AIC": v["aic"],
                         "rho": _num(v["rho"]) if v["rho"] is not None else np.nan,
                         "Mejor": "★" if nom == best else ""})
    return pd.DataFrame(rows)


def tabla_impactos(D, ecuacion):
    imp = D["impactos_int"] if ecuacion == "Internet" else D["impactos_pib"]
    if not imp:
        return pd.DataFrame({"mensaje": ["El mejor modelo no tiene rho (OLS/SEM)"]})
    return pd.DataFrame([{"Variable": k, "Directo": v["directo"],
                          "Indirecto": v["indirecto"], "Total": v["total"]}
                         for k, v in imp.items()])


# =============================================================================
# APLICACIÓN
# =============================================================================
try:
    D = pipeline()
except Exception as e:
    st.error("No se pudieron cargar los datos.")
    st.exception(e)
    st.stop()

st.title("Colombia Spatial Intelligence")
st.markdown(f"""
**Spatial VAR** · Conectividad Digital ↔ Dinámica Económica · Luces Nocturnas VIIRS

Datos oficiales **DANE + MinTIC + NOAA/VIIRS** · {len(D['deptos'])} departamentos · {D['df']['año'].min()}–{D['df']['año'].max()}

**Mejor especificación** → PIB: **{D['mejor_pib']}** | Internet: **{D['mejor_int']}**
""")

tabs = st.tabs(["🗺️ Mapa", "📊 Topografía 3D", "🔗 Autocorrelación (Moran)",
                "📈 Series por departamento", "🧠 Modelos Spatial VAR",
                "💥 Impactos LeSage-Pace", "📚 Fuentes"])

with tabs[0]:
    v = st.selectbox("Selecciona la variable", VARIABLES, index=0, key="mapa_var")
    st.plotly_chart(crear_mapa(D, v), use_container_width=True)

with tabs[1]:
    v = st.radio("Selecciona la variable", VARIABLES, index=2, horizontal=True, key="3d_var")
    st.plotly_chart(crear_3d(D, v), use_container_width=True)

with tabs[2]:
    v = st.selectbox("Selecciona la variable", VARIABLES, index=0, key="moran_var")
    st.plotly_chart(crear_moran(D, v), use_container_width=True)

with tabs[3]:
    dep = st.selectbox("Selecciona el departamento", D["deptos"], index=0, key="serie_depto")
    st.plotly_chart(crear_serie(D, dep), use_container_width=True)

with tabs[4]:
    st.subheader("Comparación de modelos espaciales")
    st.dataframe(tabla_modelos(D), use_container_width=True)
    st.markdown("""
- **SAR / SDM**: dependencia en Y (ρ)
- **SEM**: dependencia en el error
- **SDM**: ρ + rezagos espaciales de X (spillover contemporáneo)
""")

with tabs[5]:
    eq = st.radio("Ecuación", ["Internet", "PIB"], index=0, horizontal=True, key="impactos_eq")
    st.dataframe(tabla_impactos(D, eq), use_container_width=True)

with tabs[6]:
    st.markdown(f"""
### Fuentes de datos

- **PIB**: {URL_PIB}
- **Internet**: {URL_INTERNET}
- **NTL**: NOAA/VIIRS/DNB/ANNUAL_V21 (Google Earth Engine)

---
*Dashboard construido con Streamlit + Plotly*
""")

st.sidebar.markdown("---")
st.sidebar.info("Colombia Spatial Intelligence · Spatial VAR")

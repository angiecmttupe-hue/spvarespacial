# -*- coding: utf-8 -*-
"""
Colombia Spatial Intelligence - Dashboard Streamlit
Spatial VAR: Conectividad digital <-> Dinámica económica (NTL VIIRS)

Datos de luces nocturnas e internet:
  - Si existen ntl_departamentos.csv / internet_departamentos.csv en el repo, se usan.
  - Si no, internet se descarga de datos.gov.co y NTL se pide a Earth Engine
    (requiere cuenta de servicio en st.secrets["gee"]).
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from libpysal.weights import Queen, lag_spatial
from esda.moran import Moran
from spreg import OLS, ML_Lag, ML_Error, GM_Combo

st.set_page_config(page_title="Colombia Spatial Intelligence", page_icon="🇨🇴",
                   layout="wide", initial_sidebar_state="expanded")

BASE = Path(__file__).parent
CACHE_DIR = BASE / "cache_datos"
CACHE_DIR.mkdir(exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (SpatialVAR/1.0)"}

URL_GEO = "https://raw.githubusercontent.com/caticoa3/colombia_mapa/master/co_2018_MGN_DPTO_POLITICO.geojson"
URL_PIB = "https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx"
URL_INTERNET = "https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv"
CSV_NTL = BASE / "ntl_departamentos.csv"
CSV_INTERNET = BASE / "internet_departamentos.csv"


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------
# Carga de datos
# ----------------------------------------------------------------------------
def cargar_geometrias():
    gdf = gpd.read_file(URL_GEO)
    if "DPTO_CNMBR" in gdf.columns:
        gdf = gdf.rename(columns={"DPTO_CNMBR": "departamento", "DPTO_CCDGO": "cod_dpto"})
    elif "NOM_DEP" in gdf.columns:
        gdf = gdf.rename(columns={"NOM_DEP": "departamento", "COD_DEP": "cod_dpto"})
    gdf["departamento"] = normalizar_nombres_deptos(gdf["departamento"])
    gdf = gdf.to_crs(4326).sort_values("departamento").reset_index(drop=True)
    return gdf


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
        s = "".join(ch for ch in s if ch.isdigit())
        años.append(int(s))
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
    if CSV_INTERNET.exists():
        d = pd.read_csv(CSV_INTERNET)
        d["año"] = d["año"].astype(int)
        return d[["año", "departamento", "accesos_internet"]]
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
    d = (raw.groupby(["año", "departamento"], as_index=False)["accesos"].sum()
            .rename(columns={"accesos": "accesos_internet"}))
    d = d[~d["departamento"].str.contains("Colombia", case=False, na=False)]
    d["año"] = d["año"].astype(int)
    return d


def cargar_ntl(gdf):
    if CSV_NTL.exists():
        d = pd.read_csv(CSV_NTL)
        d["año"] = d["año"].astype(int)
        return d[["año", "departamento", "ntl_mean"]]
    # Alternativa: Earth Engine con cuenta de servicio en st.secrets["gee"]
    import ee, json
    if "gee" not in st.secrets:
        raise RuntimeError(
            "No se encontró ntl_departamentos.csv en el repositorio ni credenciales "
            "de Earth Engine en st.secrets['gee']. Sube el CSV generado desde Colab."
        )
    info = dict(st.secrets["gee"])
    creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
    ee.Initialize(creds, project=info.get("project_id"))
    coleccion = ee.ImageCollection("NOAA/VIIRS/DNB/ANNUAL_V21").select("average")
    feats = []
    for idx, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feats.append(ee.Feature(geom, {"departamento": row["departamento"], "id": int(idx)}))
    fc = ee.FeatureCollection(feats)
    out = []
    for año in range(2015, 2025):
        img = coleccion.filter(ee.Filter.calendarRange(año, año, "year")).first()
        try:
            img.get("system:index").getInfo()
        except Exception:
            continue
        res = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=500).getInfo()
        for f in res["features"]:
            p = f["properties"]
            out.append({"año": año, "departamento": p["departamento"], "ntl_mean": p.get("mean", np.nan)})
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------
# Pipeline + modelos (cacheado)
# ----------------------------------------------------------------------------
def seleccionar_modelo_espacial(y, X, W, nombre_y, nombre_x):
    resultados = {}
    specs = [
        ("OLS", lambda: OLS(y, X, w=W, spat_diag=True, name_y=nombre_y, name_x=nombre_x)),
        ("SAR", lambda: ML_Lag(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SEM", lambda: ML_Error(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SAC", lambda: GM_Combo(y, X, w=W, name_y=nombre_y, name_x=nombre_x)),
        ("SDM", lambda: ML_Lag(y, X, w=W, slx_lags=1, name_y=nombre_y, name_x=nombre_x)),
    ]
    for nom, fn in specs:
        try:
            m = fn()
            resultados[nom] = {"modelo": m, "aic": getattr(m, "aic", np.nan),
                               "rho": getattr(m, "rho", None)}
        except Exception:
            pass
    valid = {k: v for k, v in resultados.items()
             if v.get("aic") is not None and not np.isnan(v.get("aic", np.nan))}
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


@st.cache_resource(show_spinner="Cargando datos y estimando modelos espaciales…")
def construir_analisis():
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
    imp_pib = descomposicion_impactos(res_pib[mejor_pib]["modelo"], W) if mejor_pib else None
    imp_int = descomposicion_impactos(res_int[mejor_int]["modelo"], W) if mejor_int else None

    gdf_plot = gdf.merge(df_t[["ln_pib", "ln_internet", "ln_ntl"]].reset_index(), on="departamento")
    cent = gdf_plot.geometry.to_crs(3116).centroid.to_crs(4326)
    gdf_plot["lon"], gdf_plot["lat"] = cent.x, cent.y

    return dict(df=df, df_t=df_t, gdf_plot=gdf_plot, W=W, deptos=deptos_orden, año_t=año_t,
                res_pib=res_pib, mejor_pib=mejor_pib, res_int=res_int, mejor_int=mejor_int,
                imp_pib=imp_pib, imp_int=imp_int)


# ----------------------------------------------------------------------------
# Gráficos
# ----------------------------------------------------------------------------
def escala(variable):
    return "YlOrRd" if "pib" in variable else ("Blues" if "internet" in variable else "Inferno")


def fig_mapa(A, variable):
    g = A["gdf_plot"]
    fig = px.choropleth_mapbox(
        g, geojson=g.__geo_interface__, locations=g.index, color=variable,
        hover_name="departamento", mapbox_style="carto-darkmatter",
        center={"lat": 4.5, "lon": -74}, zoom=4.3, opacity=0.78,
        color_continuous_scale=escala(variable), title=f"{variable} · {A['año_t']}")
    fig.update_layout(template="plotly_dark", height=560, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def fig_3d(A, variable):
    g = A["gdf_plot"]
    fig = go.Figure(go.Scatter3d(
        x=g["lon"], y=g["lat"], z=g[variable], mode="markers+text",
        text=g["departamento"], textposition="top center",
        textfont=dict(size=8, color="white"),
        marker=dict(size=9, color=g[variable], colorscale=escala(variable), opacity=0.9,
                    colorbar=dict(title=variable), line=dict(width=0.5, color="white")),
        hovertemplate="<b>%{text}</b><br>%{z:.3f}<extra></extra>"))
    fig.update_layout(title=f"Topografía 3D · {variable} ({A['año_t']})", template="plotly_dark",
                      scene=dict(xaxis_title="Lon", yaxis_title="Lat", zaxis_title=variable),
                      height=560, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def fig_moran(A, variable):
    y = A["df_t"][variable].values
    yl = lag_spatial(A["W"], y)
    mi = Moran(y, A["W"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y, y=yl, mode="markers", text=A["deptos"],
        marker=dict(size=11, color=y, colorscale="Viridis", line=dict(color="white", width=1)),
        hovertemplate="%{text}<br>y=%{x:.2f} · Wy=%{y:.2f}<extra></extra>", showlegend=False))
    b, a = np.polyfit(y, yl, 1)
    xs = np.linspace(y.min(), y.max(), 40)
    fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines",
                             line=dict(color="tomato", dash="dash"), name=f"I={mi.I:.3f}"))
    fig.update_layout(title=f"Moran · {variable} (I={mi.I:.3f}, p={mi.p_sim:.3f})",
                      template="plotly_dark", height=460,
                      xaxis_title=variable, yaxis_title=f"W·{variable}")
    return fig


def fig_serie(A, depto):
    d = A["df"][A["df"]["departamento"] == depto]
    fig = go.Figure()
    for c, n, col in [("ln_pib", "ln(PIB)", "#f4a261"), ("ln_internet", "ln(Internet)", "#2a9d8f"),
                      ("ln_ntl", "ln(NTL)", "#e9c46a")]:
        fig.add_trace(go.Scatter(x=d["año"], y=d[c], mode="lines+markers", name=n, line=dict(color=col)))
    fig.update_layout(title=f"Serie temporal · {depto}", template="plotly_dark", height=420)
    return fig


def tabla_modelos(A):
    rows = []
    for eq, res, best in [("PIB", A["res_pib"], A["mejor_pib"]), ("Internet", A["res_int"], A["mejor_int"])]:
        for nom, v in res.items():
            rho = v.get("rho")
            try:
                rho = float(rho) if rho is not None else None
            except Exception:
                rho = None
            rows.append({"Ecuación": eq, "Modelo": nom, "AIC": v.get("aic"),
                         "rho": rho, "Mejor": "★" if nom == best else ""})
    return pd.DataFrame(rows)


def tabla_impactos(A, ecuacion):
    imp = A["imp_int"] if ecuacion == "Internet" else A["imp_pib"]
    if not imp:
        return pd.DataFrame({"mensaje": ["El mejor modelo no tiene rho (OLS/SEM): sin descomposición de impactos."]})
    return pd.DataFrame([{"Variable": k, "Directo": v["directo"], "Indirecto": v["indirecto"],
                          "Total": v["total"]} for k, v in imp.items()])


# ----------------------------------------------------------------------------
# Interfaz
# ----------------------------------------------------------------------------
try:
    A = construir_analisis()
except Exception as e:
    st.error(f"No se pudo construir el análisis: {e}")
    st.stop()

df, deptos = A["df"], A["deptos"]
VARS = ["ln_pib", "ln_internet", "ln_ntl"]

st.markdown(f"""
# Colombia Spatial Intelligence
**Spatial VAR** · Conectividad Digital ↔ Dinámica Económica · Luces Nocturnas VIIRS

Datos oficiales **DANE + MinTIC + NOAA/VIIRS** · {len(deptos)} departamentos · {df['año'].min()}–{df['año'].max()}

Mejor especificación → **PIB: {A['mejor_pib']}** | **Internet: {A['mejor_int']}**
""")

tabs = st.tabs(["🗺️ Mapa", "📊 Topografía 3D", "🔗 Autocorrelación (Moran)",
                "📈 Series por departamento", "🧮 Modelos Spatial VAR",
                "📉 Impactos LeSage-Pace", "📚 Fuentes"])

with tabs[0]:
    v = st.selectbox("Variable", VARS, index=0, key="mapa_var")
    st.plotly_chart(fig_mapa(A, v), use_container_width=True)

with tabs[1]:
    v = st.radio("Variable", VARS, index=2, horizontal=True, key="v3d")
    st.plotly_chart(fig_3d(A, v), use_container_width=True)

with tabs[2]:
    v = st.selectbox("Variable", VARS, index=0, key="moran_var")
    st.plotly_chart(fig_moran(A, v), use_container_width=True)

with tabs[3]:
    d = st.selectbox("Departamento", deptos, index=0, key="serie_depto")
    st.plotly_chart(fig_serie(A, d), use_container_width=True)

with tabs[4]:
    st.dataframe(tabla_modelos(A), use_container_width=True, hide_index=True)
    st.markdown("""
- **SAR / SDM**: dependencia en Y (ρ)
- **SEM**: dependencia en el error
- **SDM**: ρ + rezagos espaciales de X (spillover contemporáneo)
""")

with tabs[5]:
    eq = st.radio("Ecuación", ["Internet", "PIB"], index=0, horizontal=True, key="imp_eq")
    st.dataframe(tabla_impactos(A, eq), use_container_width=True, hide_index=True)

with tabs[6]:
    st.markdown(f"""
### Fuentes de datos
- **PIB**: {URL_PIB}
- **Internet**: {URL_INTERNET}
- **NTL**: NOAA/VIIRS/DNB/ANNUAL_V21 (Google Earth Engine)
""")

st.sidebar.info(f"""
**Panel final**  
Departamentos: {len(deptos)}  
Periodo: {df['año'].min()} – {df['año'].max()}  
Mejor PIB: **{A['mejor_pib']}**  
Mejor Internet: **{A['mejor_int']}**
""")

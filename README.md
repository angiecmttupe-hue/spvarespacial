# Colombia Spatial Intelligence

Análisis **Spatial VAR** de la relación entre **conectividad digital** y **dinámica económica** en los departamentos de Colombia, usando luces nocturnas satelitales (VIIRS) como variable de actividad. Incluye un dashboard interactivo (Gradio y Streamlit).

> Origen: cuaderno de Colab `Taller 4.1.ipynb` (versión 1.1 – FINAL), exportado como `app.py`.

---

## Qué hace

1. **Geometrías**: descarga el GeoJSON de departamentos de Colombia (MGN 2018) y normaliza los nombres.
2. **PIB departamental**: descarga el anexo del DANE (`anex-PIBDep-TotalDep-2025pr.xlsx`, hoja `Cuadro 1`) y lo pasa a formato largo.
3. **Internet fijo**: descarga accesos por departamento y año desde datos.gov.co (dataset `n48w-gutb`, MinTIC).
4. **Luces nocturnas (NTL)**: extrae el promedio anual por departamento de `NOAA/VIIRS/DNB/ANNUAL_V21` con Google Earth Engine (2015–2024).
5. **Panel**: une las tres fuentes por año y departamento (desde 2017, años comunes) y calcula `ln_pib`, `ln_internet` y `ln_ntl`.
6. **Análisis espacial**:
   - Matriz de pesos **Queen** (estandarizada por filas).
   - **I de Moran** global para cada variable.
   - Comparación de modelos por AIC: **OLS, SAR, SEM, SAC, SDM**, para dos ecuaciones (PIB e Internet).
   - Descomposición de impactos **directo / indirecto / total** (LeSage & Pace).
7. **Dashboard** con pestañas: Mapa, Topografía 3D, Moran, Series por departamento, Modelos, Impactos y Fuentes.

## Variables

| Variable | Descripción | Fuente |
|---|---|---|
| `ln_pib` | Log del PIB departamental (millones) | DANE |
| `ln_internet` | Log de accesos a internet fijo | MinTIC / datos.gov.co |
| `ln_ntl` | Log de luces nocturnas promedio | NOAA VIIRS (Google Earth Engine) |

Especificación base: `X = [ln_pib(t-1), ln_internet(t-1), ln_ntl(t)]`, estimada sobre el último año disponible del panel.

## Requisitos

- Python 3.10 o superior
- Una cuenta de **Google Earth Engine** con un proyecto de Cloud habilitado
- Conexión a internet (descarga de datos)

Instalación:

```bash
pip install -r requirements.txt
```

## Cómo ejecutarlo

### En Google Colab (recomendado)

El script fue escrito para Colab: usa la ruta `/content/cache_datos_reales` y `ee.Authenticate()` interactivo. Las líneas que empiezan con `!pip` solo funcionan en Colab o Jupyter.

1. Sube el código a un cuaderno de Colab.
2. Ejecuta las celdas en orden.
3. Al final, `demo.launch(share=True)` genera un enlace público de Gradio.

### En local

Antes de ejecutar `app.py` fuera de Colab:

1. Elimina o comenta las líneas `!pip install ...` (no son Python válido en un `.py`).
2. Cambia `CACHE_DIR` por una ruta local, por ejemplo `Path("./cache_datos_reales")`.
3. Autentica Earth Engine una vez con `earthengine authenticate`.
4. Reemplaza el ID de proyecto en `ee.Initialize(project="...")` por el tuyo.
5. Ejecuta:

```bash
python app.py
```

Para la versión Streamlit (segunda parte del archivo), sepárala en su propio script y ejecútala con:

```bash
streamlit run dashboard_streamlit.py
```

## Estructura del script

| Sección | Contenido |
|---|---|
| 0–1 | Instalación e imports, inicialización de GEE |
| 2 | Utilidades (normalización de nombres, VIF, ADF, auditoría de W) |
| 3–6 | Carga de geometrías, PIB, Internet y NTL |
| 7 | Construcción del panel |
| 8 | Matriz W, Moran, modelos espaciales e impactos |
| 9–10 | Funciones y interfaz del dashboard (Gradio, luego Streamlit) |

## Observaciones sobre el código

- El script contiene **dos dashboards** (Gradio y Streamlit) y repite la sección 9 y la instalación de dependencias. Conviene dividirlo en dos archivos.
- `demo.launch(share=True)` bloquea la ejecución, por lo que el código de Streamlit que sigue no se ejecuta en la misma sesión.
- El PIB, Internet y NTL dependen de URLs externas que pueden cambiar de formato o dejar de estar disponibles.
- El análisis de corte transversal usa solo 2 años (`t` y `t-1`) con ~32 departamentos, así que los resultados deben interpretarse con cautela.

## Fuentes de datos

- **PIB**: https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx
- **Internet fijo**: https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv
- **Luces nocturnas**: `NOAA/VIIRS/DNB/ANNUAL_V21` (Google Earth Engine)
- **Geometrías**: https://github.com/caticoa3/colombia_mapa

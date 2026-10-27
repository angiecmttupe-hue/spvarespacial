# Colombia Spatial Intelligence

Análisis **Spatial VAR** de la relación entre conectividad digital y dinámica económica en los departamentos de Colombia, con dashboard interactivo (Gradio y Streamlit).

Generado originalmente desde un cuaderno de Google Colab (`Taller.ipynb`).

## ¿Qué hace?

1. **Descarga y limpia datos oficiales**
   - **PIB departamental**: DANE (`anex-PIBDep-TotalDep-2025pr.xlsx`, hoja "Cuadro 1").
   - **Accesos a internet fijo**: MinTIC / datos.gov.co (dataset `n48w-gutb`).
   - **Luces nocturnas (NTL)**: NOAA/VIIRS `DNB/ANNUAL_V21`, extraídas con Google Earth Engine (2015–2024).
   - **Geometrías**: GeoJSON de departamentos (MGN 2018).
2. **Construye un panel** departamento × año (desde 2017, años comunes a las tres fuentes) y aplica logaritmos: `ln_pib`, `ln_internet`, `ln_ntl`.
3. **Análisis espacial (ESDA)**
   - Matriz de pesos espaciales **Queen**, estandarizada por filas.
   - **I de Moran global** para cada variable en el último año disponible.
4. **Selección de modelo espacial** por AIC, para dos ecuaciones (PIB e Internet):

   | Modelo | Descripción |
   |--------|-------------|
   | OLS    | Línea base con diagnósticos espaciales |
   | SAR    | Rezago espacial en Y (ρ) |
   | SEM    | Dependencia espacial en el error |
   | SAC    | Rezago + error (GM_Combo) |
   | SDM    | ρ + rezagos espaciales de X |

   Regresores: `ln_pib_lag`, `ln_internet_lag` (año t-1) y `ln_ntl` (año t).
5. **Descomposición de impactos (LeSage-Pace)**: efectos directo, indirecto (spillover) y total.
6. **Dashboard** con 7 pestañas:
   Mapa · Topografía 3D · Autocorrelación (Moran) · Series por departamento · Modelos Spatial VAR · Impactos LeSage-Pace · Fuentes.

## Estructura del script (`app.py`)

| Sección | Contenido |
|---------|-----------|
| 0 | Instalación de dependencias (`!pip`, solo Colab) |
| 1 | Imports y autenticación de Google Earth Engine |
| 2 | Utilidades: normalización de nombres, ADF, VIF, auditoría de la matriz W |
| 3 | Geometrías de departamentos |
| 4 | PIB DANE |
| 5 | Internet |
| 6 | Luces nocturnas VIIRS (GEE) y exportación a CSV |
| 7 | Construcción del panel |
| 8 | Matriz W, Moran y modelos espaciales |
| 9 | Funciones de visualización (Plotly) |
| 10 | Interfaz Gradio y aplicación Streamlit |

## Requisitos

- Python 3.10+
- Una cuenta de Google con acceso a **Google Earth Engine** y un proyecto de GEE propio.
- Las dependencias de `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Cómo ejecutarlo

### En Google Colab (forma original)
1. Sube `app.py` o pega su contenido en un cuaderno.
2. Ejecuta las celdas en orden y autentícate en Earth Engine cuando se solicite.
3. Se lanza Gradio con enlace público (`share=True`).

### En local
El script contiene elementos exclusivos de Colab que hay que ajustar primero (ver siguiente sección). Después:

```bash
# Dashboard Streamlit
streamlit run app.py
```

## Ajustes necesarios para ejecutarlo fuera de Colab

- **Eliminar el bloque `!pip install ...`** (sintaxis de Jupyter/Colab) e instalar con `requirements.txt`.
- **Eliminar o condicionar `from google.colab import files`** y las llamadas a `files.download(...)`; basta con guardar los CSV con `to_csv`.
- **Cambiar `CACHE_DIR`** (`/content/cache_datos_reales`) por una ruta local, por ejemplo `Path("cache_datos_reales")`.
- **Reemplazar el ID de proyecto de GEE** (`ee.Initialize(project="...")`) por el tuyo.
- **Elegir una sola interfaz**: el script lanza Gradio (`demo.launch(share=True)`) *antes* de definir la app de Streamlit, por lo que el bloqueo de Gradio impide que Streamlit se ejecute. Conserva la interfaz que vayas a usar.
- Las funciones `ui_*` (Gradio) y `crear_*` (Streamlit) son equivalentes; puedes dejar solo un conjunto.
- La sección 9 aparece dos veces; la numeración de secciones es heredada del cuaderno.

## Salidas

- `ntl_departamentos.csv`: luces nocturnas medias por departamento y año.
- `internet_departamentos.csv`: accesos a internet fijo por departamento y año.
- Caché de descargas en `cache_datos_reales/`.

## Fuentes de datos

- PIB: https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx
- Internet: https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv
- NTL: NOAA/VIIRS/DNB/ANNUAL_V21 (Google Earth Engine)
- Geometrías: https://github.com/caticoa3/colombia_mapa

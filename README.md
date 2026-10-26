# Colombia Spatial Intelligence

**Spatial VAR** · Conectividad digital ↔ dinámica económica · Luces nocturnas VIIRS

Pipeline de análisis espacial para los departamentos de Colombia, con dashboard interactivo (Gradio y Streamlit). Originado en el cuaderno de Colab *Taller 4.1*.

## ¿Qué hace?

1. **Geometrías**: descarga el GeoJSON de departamentos (MGN 2018) y normaliza los nombres.
2. **PIB departamental**: descarga el anexo del DANE (`anex-PIBDep-TotalDep-2025pr.xlsx`, hoja *Cuadro 1*) y lo pasa a formato largo.
3. **Internet fijo**: descarga accesos por departamento desde datos.gov.co (MinTIC, dataset `n48w-gutb`).
4. **Luces nocturnas (NTL)**: extrae el promedio anual por departamento de `NOAA/VIIRS/DNB/ANNUAL_V21` vía Google Earth Engine (2015–2024).
5. **Panel**: une las tres fuentes (años ≥ 2017) y calcula logaritmos: `ln_pib`, `ln_internet`, `ln_ntl`.
6. **Análisis espacial**:
   - Matriz de pesos **Queen** (fila estandarizada).
   - **Moran global** de cada variable en el último año.
   - Modelos para `ln_pib` y `ln_internet`: **OLS, SAR, SEM, SAC, SDM**.
   - Selección del mejor modelo por **AIC**.
   - Descomposición de impactos (directo, indirecto, total) estilo **LeSage & Pace**.
7. **Dashboard** con 7 pestañas: Mapa, Topografía 3D, Moran, Series por departamento, Modelos, Impactos y Fuentes.

### Especificación del modelo

- Variables explicativas (`X`): `ln_pib` rezagado (t-1), `ln_internet` rezagado (t-1) y `ln_ntl` (t).
- Variables dependientes: `ln_pib` (t) y `ln_internet` (t).

## Requisitos

- Python 3.10+
- Cuenta de Google Earth Engine con un proyecto de Google Cloud habilitado.
- Dependencias: ver `requirements.txt`.

```bash
pip install -r requirements.txt
```

## Uso

El script está pensado para **Google Colab**. Si lo ejecutas ahí, funciona tal cual. Si lo ejecutas en local, ajusta lo siguiente:

| Elemento | Qué hacer |
|---|---|
| Líneas `!pip install ...` | Quitarlas e instalar con `requirements.txt`. |
| `from google.colab import files` y `files.download(...)` | Eliminarlas (solo existen en Colab). |
| `CACHE_DIR = Path("/content/cache_datos_reales")` | Cambiar a una ruta local, por ejemplo `Path("cache_datos_reales")`. |
| `ee.Initialize(project="...")` | Reemplazar por tu propio ID de proyecto de GEE. |

### Dashboard

El archivo contiene **dos interfaces** para los mismos datos:

- **Gradio** (sección 10): se lanza con `demo.launch(share=True)` y genera un enlace público.
- **Streamlit** (sección 10, segunda parte): se ejecuta con `streamlit run app.py`.

> Nota: Streamlit debe ejecutarse con `streamlit run`; en un script que ya lanzó Gradio, conviene separar cada interfaz en su propio archivo.

## Fuentes de datos

- **PIB**: DANE, <https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx>
- **Internet**: MinTIC / datos.gov.co, <https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv>
- **NTL**: NOAA/VIIRS/DNB/ANNUAL_V21 (Google Earth Engine)
- **Geometrías**: <https://raw.githubusercontent.com/caticoa3/colombia_mapa/master/co_2018_MGN_DPTO_POLITICO.geojson>

## Salidas

- `ntl_departamentos.csv`: luces nocturnas por departamento y año.
- `internet_departamentos.csv`: accesos de internet por departamento y año.

## Aspectos a tener en cuenta

- Con ~32 departamentos y un solo corte transversal para los modelos, la muestra es pequeña; interpreta los resultados con cautela.
- `tabulate` se importa pero no estaba en el `pip install` original; aquí se incluye en `requirements.txt`.
- Las URL del DANE y datos.gov.co pueden cambiar con el tiempo.

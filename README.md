# Colombia Spatial Intelligence

**Spatial VAR** · Conectividad digital ↔ dinámica económica · Luces nocturnas VIIRS

Pipeline de análisis espacial para los departamentos de Colombia, con un dashboard interactivo en **Streamlit**. Originado en el cuaderno de Colab *Taller 4.1* y adaptado para correr como app web.

## ¿Qué hace?

1. **Geometrías**: descarga el GeoJSON de departamentos (MGN 2018) y normaliza los nombres.
2. **PIB departamental**: lee el anexo del DANE (`anex-PIBDep-TotalDep-2025pr.xlsx`, hoja *Cuadro 1*) y lo pasa a formato largo.
3. **Internet fijo**: accesos por departamento desde datos.gov.co (MinTIC, dataset `n48w-gutb`).
4. **Luces nocturnas (NTL)**: promedio anual por departamento de `NOAA/VIIRS/DNB/ANNUAL_V21` (Google Earth Engine, 2015–2024).
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

## Estructura del proyecto

```
.
├── app.py                      # App Streamlit (pipeline + dashboard)
├── requirements.txt            # Dependencias
├── ntl_departamentos.csv       # Luces nocturnas por depto y año (recomendado)
├── internet_departamentos.csv  # Accesos de internet por depto y año (recomendado)
└── cache_datos_reales/         # Se crea sola; guarda descargas (DANE, datos.gov.co)
```

Los dos CSV son opcionales pero **muy recomendables**: si existen, la app los usa directamente y evita consultar Earth Engine y descargar millones de filas de datos.gov.co.

## Instalación y uso

Requiere Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

> No ejecutes `python app.py`: Streamlit necesita `streamlit run`.

La primera carga puede tardar (descarga de datos y estimación de modelos). Después, el resultado queda en caché y la navegación entre pestañas es inmediata.

## Datos de luces nocturnas (NTL)

La app busca `ntl_departamentos.csv` junto a `app.py`. Si no existe, intenta extraer los datos de Google Earth Engine con una **cuenta de servicio**, que debe configurarse en los secrets de Streamlit (`.streamlit/secrets.toml` o el panel de *Secrets* del servicio donde despliegues):

```toml
[gee_service_account]
type = "service_account"
project_id = "tu-proyecto"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "tu-cuenta@tu-proyecto.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

La cuenta de servicio debe tener acceso a Earth Engine. Si no configuras esto ni subes el CSV, la app muestra un mensaje de error explicando qué falta.

## Despliegue

Funciona en Streamlit Community Cloud u otro servicio que ejecute Streamlit. Sube al repositorio `app.py`, `requirements.txt` y los dos CSV.

## Fuentes de datos

- **PIB**: DANE, <https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx>
- **Internet**: MinTIC / datos.gov.co, <https://www.datos.gov.co/api/v3/views/n48w-gutb/query.csv>
- **NTL**: NOAA/VIIRS/DNB/ANNUAL_V21 (Google Earth Engine)
- **Geometrías**: <https://raw.githubusercontent.com/caticoa3/colombia_mapa/master/co_2018_MGN_DPTO_POLITICO.geojson>

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `SyntaxError` en `!pip install` | Se usó el script original de Colab | Usar el `app.py` actual; las dependencias van en `requirements.txt`. |
| "No se pudieron cargar los datos" (Earth Engine) | Falta `ntl_departamentos.csv` y no hay secrets de GEE | Subir el CSV o configurar `gee_service_account`. |
| Falla la descarga del PIB o Internet | URL cambiada o bloqueo del servidor | Descargar el archivo manualmente y ponerlo junto a `app.py` (el Excel del DANE) o usar `internet_departamentos.csv`. |

## Aspectos a tener en cuenta

- Con ~32 departamentos y un solo corte transversal para los modelos, la muestra es pequeña; interpreta los resultados con cautela.
- Las URL del DANE y datos.gov.co pueden cambiar con el tiempo.

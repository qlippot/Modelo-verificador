# Modelo-verificador

Herramientas deterministas (sin IA) para el **Modelo de Datos Geográfico ICANH V4**, pensadas como núcleo de un
servidor MCP o de una WebApp:

| Herramienta | Qué hace | Escribe |
|---|---|---|
| **1. Verificar** | Revisa un Modelo contra el catálogo y las plantillas V4: formato, coherencia interna e información faltante | Nada |
| **2. Codificar** | Lee una base de datos de materiales (.xlsx), asigna `ID_ACT_ARQ`, `ID_UNI_EX` e IDs de materiales, y entrega la BD codificada | Una copia de la BD y, si se pide, una **copia** del Modelo |

Fuera de alcance: lectura de fichas, trazado de polígonos o estructuras, ortoplanos y georreferenciación.

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[raster,dev]"
```

`rasterio` es opcional: sin él no se revisa el CRS ni la extensión de los ortoplanos.

## Uso (CLI)

```bash
modelo-verificador verificar "ruta/Modelo" -o verificacion.json
modelo-verificador verificar "ruta/Modelo" --modulos formato --completo
modelo-verificador codificar BD.xlsx config.json "ruta/Modelo" --bd-salida "BD - codificada.xlsx" -o asignaciones.json
modelo-verificador codificar BD.xlsx config.json "ruta/Modelo" --escribir-en "ruta/Modelo_staging"
modelo-verificador id R0125A220005DI00001OB0001
modelo-verificador dominio ESTRUCTURAS TIPO_OBJEC
```

`verificar` termina con código 1 si hay ERRORES (útil en CI). Todo sale en JSON.

## Uso (Python, para MCP / WebApp)

```python
from modelo_verificador.verificar import verificar_todo
from modelo_verificador.codificar import codificar, escribir_bd, escribir_modelo
from modelo_verificador import ids

res = verificar_todo("ruta/Modelo")                 # {conteo, apto, modulos: {formato, coherencia, faltantes}}
cod = codificar("BD.xlsx", "config.json", "ruta/Modelo")
escribir_bd(cod, "BD.xlsx", "BD - codificada.xlsx")
ids.analizar("R0125A220005PI00001C0001")
```

## Herramienta 1 — Verificar

Cada hallazgo tiene `nivel` (ERROR / AVISO / INFO), `capa`, `regla` y `detalle`. Hay tres módulos:

- **formato** (`verificar/formato.py`): campos y geometría frente a la plantilla V4, `.prj` CTM12, obligatorios vacíos,
  valores fuera de dominio (hoja DOMINIOS del catálogo), textos que exceden el campo DBF **en bytes UTF-8**,
  formato, longitud y unicidad de todos los IDs, `ID_ACT_ARQ` / `ID_UNI_EX` inexistentes, y profundidades negativas,
  invertidas o 0-0.
- **coherencia** (`verificar/coherencia.py`): contención polígono general ⊃ específico ⊃ actividad ⊃ estructura o punto,
  geometrías inválidas, solapes entre actividades, fechas, ANCHO/LARGO frente a la geometría, MAT_ARQUEO frente al
  contenido, NMERO_UNE, PROFUN_MAX, unidades sin uso o compartidas, ortoplanos (nombre `<ID_ACT>_<ID_UNI>.tif`,
  EPSG 9377, cobertura, obligatorios en Corte / Cuadrícula / Trinchera con materiales) y conteos del Metadato.
- **faltantes** (`verificar/faltantes.py`): ortoplanos requeridos, obligatorios y condicionales de actividades, unidades
  sin descripción o profundidad, campos de materiales mayormente vacíos, y filas del Metadato sin diligenciar.

## Herramienta 2 — Codificar

Todo lo decide un JSON de configuración (ver `ejemplos/config_codificacion.ejemplo.json`):

- **actividades**: correspondencias `exactas` (etiqueta de la BD → `ID_ACT_ARQ`, sin distinguir mayúsculas ni espacios),
  `patrones` regex (`"^trinchera\\s*(\\d+)$" → "R…PI{1:05d}"`) y `por_defecto` para filas sin actividad. El ID
  resultante debe existir en ACTIVIDADES; si no, la fila queda «Sin resolver».
- **unidades**: se reutilizan las existentes por su etiqueta estable `<PIxxxxx>-<ESTRATO>:` al inicio de la descripción;
  las que faltan se crean con el siguiente consecutivo (`NP` en Implementación, `ND` en Aprobación PMA). Los estratos
  de `superficie` crean unidades TIPO «Superficie» (0-0). `fijas` fuerza una unidad concreta.
- **hojas**: por cada hoja de la BD, su `capa`, columnas de ID, actividad, estrato, `profundidad` (`rango` «a-b» o
  `ini`/`fin`), `coordenadas` opcionales (si no hay, el punto va al centroide de la actividad) y `campos`:
  columna directa, `{"valor"}`, `{"columna", "mapa", "defecto"}`, `{"concatenar"}` o `{"segun_cantidad"}`.
- Profundidad: la de la BD, si no la de la descripción de la unidad (`Profundidad: a - b cm`), y si no
  `sin_profundidad` (por defecto 0-0), con una nota en la fila.
- **modo**: `reemplazar` reescribe cada capa configurada solo con la BD, numerando desde 0001 por actividad.
  `agregar` continúa el consecutivo de los IDs existentes.
- Es idempotente: con la misma BD y configuración, una segunda corrida produce los mismos IDs y 0 unidades nuevas.

Salidas: asignaciones por fila (JSON), «BD codificada» (copia con columnas `ID_ACT_ARQ`, `ID_UNI_EX`, `ID(s) Modelo`,
`Estado` y `Notas`, más las hojas «Unidades nuevas» y «Resumen codificación»), y la escritura opcional en una copia del
Modelo. ACTIVIDADES nunca se modifica: las que pasarían a `MAT_ARQUEO = Positivo` se listan en el reporte.

Flujo recomendado: copiar el Modelo a staging → `codificar --escribir-en staging` → `verificar staging` con 0 ERRORES →
revisar → reemplazar el Modelo.

## Reglas de IDs (catálogo V4)

`modelo_verificador/ids.py` documenta y aplica todas las reglas: polígono específico (12), zonificación `ZO` (18),
actividad `DI`/`PI` (19), unidad mínima `ND`/`NP` (18), y los prefijos de cada capa de materiales (C, B, M, L, S, E, R,
T, V, OB, OBC, OA, H, IH, EM, MA, A) con sus longitudes.

## Referencia

- `referencia/Catalogo_de_objetos_modelo_de_datos_geografico_ICANH.xls`: catálogo oficial. **El catálogo manda.**
- `referencia/plantillas_V4/`: plantillas oficiales vacías (estructura de campos, tipos, CRS). Otra ubicación:
  variable de entorno `MODELO_VERIFICADOR_REF`.

## Datos

Este repositorio no contiene datos de proyectos. Las pruebas usan datos sintéticos (`datos_sinteticos/`, por construir).

```bash
.venv/bin/pytest
```

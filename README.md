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

En macOS, si el comando `modelo-verificador` responde `No module named 'modelo_verificador'`, es porque el archivo `.pth`
de la instalación editable quedó oculto, y Python 3.13+ ignora los `.pth` ocultos. Se corrige con:

```bash
chflags nohidden .venv/lib/python3.*/site-packages/*.pth
```

## Uso (CLI)

```bash
modelo-verificador verificar "ruta/Modelo" -o verificacion.json
modelo-verificador verificar "ruta/Modelo" --fase diagnostico
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

res = verificar_todo("ruta/Modelo", fase="registro")  # {conteo, apto, grupos, modulos: {formato, coherencia, faltantes, fase}}
cod = codificar("BD.xlsx", "config.json", "ruta/Modelo")
escribir_bd(cod, "BD.xlsx", "BD - codificada.xlsx")
ids.analizar("R0125A220005PI00001C0001")
```

## Servidor MCP

`modelo_verificador/mcp_server.py` expone las dos herramientas y las utilidades como un servidor MCP (stdio, SDK
oficial `mcp` 2.x). Todo es determinista: el servidor no llama a ningún modelo.

| Herramienta | Qué hace | Escribe |
|---|---|---|
| `verificar_modelo` | Verificación completa (formato, coherencia, faltantes) | — |
| `resumen_modelo` | Capas, actividades (con sus materiales), unidades y rásteres | — |
| `inspeccionar_bd` | Hojas, encabezados y filas de muestra de una BD .xlsx | — |
| `ejemplo_config` | Configuración de ejemplo del codificador | — |
| `validar_config` | Valida una configuración contra la BD y el Modelo, sin codificar | — |
| `crear_copia_staging` | Copia el Modelo a una carpeta nueva | Carpeta nueva |
| `codificar_bd` | Asigna códigos; opcionalmente escribe la BD codificada y una copia del Modelo | Solo salidas pedidas |
| `analizar_id` · `generar_id` · `siguiente_id` | Reglas de IDs del catálogo; siguiente consecutivo libre en un Modelo | — |
| `listar_capas` · `campos_capa` · `dominio` | Consulta del catálogo V4 | — |

Protecciones:
- Cada herramienta declara sus anotaciones (solo lectura / destructiva).
- `codificar_bd` nunca escribe sobre el Modelo leído ni sobre la BD original, y no sobrescribe una salida existente
  salvo con `sobrescribir_salida=True`.
- Con la variable `MODELO_VERIFICADOR_RAIZ`, toda ruta fuera de esa carpeta se rechaza.
- Los errores previstos (ruta inexistente, hoja o columna faltante, configuración inválida) llegan al cliente con su
  mensaje.

Flujo típico desde un asistente: `inspeccionar_bd` + `resumen_modelo` → escribir la configuración →
`validar_config` → `crear_copia_staging` → `codificar_bd(escribir_en=…)` → `verificar_modelo` sobre la copia.

### Configurar un cliente

Instalar con el extra `mcp` (`pip install -e ".[raster,mcp]"`). Conviene lanzarlo con `python -m` y `PYTHONPATH`, que
no depende del `.pth` de la instalación editable (ver la nota de macOS más arriba). Reemplazar `<ruta>` por la carpeta
del repositorio.

Claude Code:

```bash
claude mcp add modelo-verificador --env PYTHONPATH=<ruta> -- <ruta>/.venv/bin/python -m modelo_verificador.mcp_server
```

Claude Desktop (`claude_desktop_config.json`) u otro cliente con el mismo formato (`ejemplos/mcp.ejemplo.json`):

```json
{
  "mcpServers": {
    "modelo-verificador": {
      "command": "<ruta>/.venv/bin/python",
      "args": ["-m", "modelo_verificador.mcp_server"],
      "env": {"PYTHONPATH": "<ruta>", "MODELO_VERIFICADOR_RAIZ": "<carpeta de trabajo>"}
    }
  }
}
```

## WebApp (HTML) — «Autoverificador»

Una sola interfaz (`web/plantilla.html`) con dos motores intercambiables. Ambos ejecutan el mismo código Python
(`servicios.py`), así que dan los mismos resultados.

- **En navegador (recomendado, y el que se publica en GitHub Pages):** un único `.html` autocontenido que ejecuta el
  paquete con Pyodide. No necesita instalar nada.

  ```bash
  .venv/bin/python web/construir_navegador.py
  ```

  Genera `web/dist/modelo-verificador.html` (≈1,4 MB), que también se abre con doble clic.
- **Local:** un servidor Python en este equipo.

  ```bash
  PYTHONPATH=. .venv/bin/python -m modelo_verificador web
  ```

  Abre `http://127.0.0.1:8765/`. Opciones: `--puerto`, `--no-abrir`.

Flujo de la interfaz:
1. **Portada:** se elige la fase (Registro / Diagnóstico / Implementación) y se sube la carpeta del Modelo (botón o
   arrastrar). La fase elegida se recuerda.
2. **Resultado:** la verificación corre sola. Errores primero, luego avisos; las notas informativas quedan plegadas.
   Cada fila se abre para ver qué significa la regla, cómo corregirla y los casos. Cambiar de fase vuelve a verificar.
3. **Codificar materiales** (panel lateral): se suben la BD (.xlsx) y la configuración (.json); al tener ambas se
   codifica y se muestran los cambios (registros nuevos, unidades nuevas, avisos) y el estado de cada fila. Se descargan
   la BD codificada y el Modelo codificado (.zip), y la copia se puede verificar con un clic.

Las herramientas de códigos (analizar un ID, siguiente código libre, catálogo V4) están en el enlace de la portada.
Para probar con los datos sintéticos, abra la página con `?ejemplo` al final de la dirección.
Arriba a la derecha de la portada se puede poner un enlace propio: `ENLACE_EXTERNO` al inicio del script de la plantilla.

| | Local | En navegador |
|---|---|---|
| Instalación | Repositorio + Python + dependencias | Ninguna (abrir la página) |
| Primer arranque | Inmediato | ≈9 s (descarga Pyodide del CDN; luego queda en caché) |
| Verificar el ejemplo | ≈0,4 s | ≈1,8 s |
| CRS / extensión de ortoplanos | Sí (rasterio) | No por ahora (aparece como nota) |
| Dónde están los datos | Carpeta temporal local, se borra al salir | Memoria del navegador; nada se sube |

Protecciones del modo local:
- Escucha solo en 127.0.0.1, con un token aleatorio por ejecución y un Host local obligatorio.
- Ninguna ruta puede salir de la carpeta de sesión.
- Solo se pueden invocar los servicios de una lista cerrada.

En ambos modos, los archivos elegidos nunca se modifican: todo resultado es una copia descargable.

### Publicar en GitHub Pages

`.github/workflows/pages.yml` corre las pruebas, construye la página y la publica como `index.html` en cada push a
`main`. Una sola vez: subir el repositorio a GitHub (público, para Pages gratuito) y en **Settings → Pages → Source**
elegir **GitHub Actions**. La página es estática: los Modelos que se suban se procesan en el navegador de cada persona y
no llegan a GitHub.

## Herramienta 1 — Verificar

Cada hallazgo tiene `nivel` (ERROR / AVISO / INFO), `capa`, `regla` y `detalle`. El resultado incluye además `grupos`:
los hallazgos agrupados por regla, ordenados por gravedad y con una explicación sencilla (`ayuda`,
`verificar/explicaciones.py`). Hay tres módulos, más uno opcional por fase:

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
- **fase** (`verificar/fase.py`, con `fase=`): según el catálogo (hojas TEMAS / GRUPOS, dominio Dom_FASE).
  *Registro* revisa solo la Zona de Estudio; los campos «posterior a la Fase de Registro» aún no se exigen.
  *Diagnóstico* exige esos campos y la Zonificación, y avisa de actividades con código PI. *Implementación* revisa todo
  y exige FECHA_PMA y CODIGO_PMA. En todas, avisa si el campo FASE de los polígonos no corresponde a la fase elegida.

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

Este repositorio no contiene datos de proyectos. Las pruebas usan los datos sintéticos de `datos_sinteticos/`:
un Modelo correcto, otro con un error sembrado por regla, y una BD de materiales con su configuración y los
resultados esperados. Ver `datos_sinteticos/README.md`.

```bash
.venv/bin/pytest
```

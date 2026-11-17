# Datos sintéticos

Todo es **ficticio**: registro `R0000A00`, polígono específico `R0000A000001`, coordenadas CTM12 inventadas
(origen 4 880 000 E, 2 070 000 N). Nunca poner aquí datos reales de proyectos.

Se regeneran de forma determinista con:

```bash
.venv/bin/python datos_sinteticos/generar.py
```

| Archivo | Contenido |
|---|---|
| `modelo_minimo/` | Modelo V4 completo y correcto, hecho sobre las plantillas oficiales. Pasa la verificación con **0 ERRORES y 0 AVISOS** |
| `modelo_con_errores/` | El mismo Modelo con **un error sembrado por regla** y carpetas sin tildes, como en muchos Modelos reales |
| `esperado_errores.json` | Hallazgos que debe producir `modelo_con_errores/`, agrupados por mutación |
| `bd_materiales.xlsx` | Base de datos de materiales (hojas Cerámica, Metales y Óseos) con casos difíciles |
| `config.json` | Configuración del codificador para esa BD |
| `esperado_codificacion.json` | Códigos esperados fila por fila, escritos a mano |
| `generar.py` | Generador: `datos_base()`, `MUTACIONES`, `BD` y `CONFIG` definen todo lo anterior |

## modelo_minimo

- Polígono general y un polígono específico de 200 × 200 m. Zonificación en dos zonas (Alto, Bajo).
- Seis actividades (fase Implementación, `PI00001`–`PI00006`):

  | ID | Tipo | Tamaño | Resultado |
  |---|---|---|---|
  | PI00001 | Corte 1 | 2 × 2 m | Positivo |
  | PI00002 | Corte 2 | 2 × 2 m | Positivo |
  | PI00003 | Trinchera | 1 × 20 m | Positivo |
  | PI00004 | Pozo de sondeo | 0,5 × 0,5 m | Negativo |
  | PI00005 | Recolección superficial | 10 × 10 m | Positivo |
  | PI00006 | Monitoreo | 5 × 5 m | Negativo |

- Siete unidades mínimas (`NP0001`–`NP0007`), con la etiqueta `PIxxxxx-Ex:` y «Profundidad: a - b cm».
  Esta etiqueta es la que el codificador usa para reutilizar unidades.
- Materiales: 7 cerámicas, 2 metales, 1 óseo animal y 1 vidrio (puntos), más 2 estructuras (polígonos).
  Todos están dentro de su actividad y usan valores de dominio del catálogo.
- Tres ortoplanos GeoTIFF en EPSG:9377 (`<ID_ACT>_<ID_UNI>.tif`), uno por cada Corte o Trinchera con materiales.
- Metadato diligenciado: capas entregadas = SI, con sus conteos; capas no entregadas = NO. Contacto ficticio.

## modelo_con_errores: mutaciones

ID de material mal formado · valores fuera de dominio (metales y zonificación) · punto fuera de su actividad ·
`ID_UNI_EX` inexistente · ID duplicado · profundidad invertida · FECHA_INI > FECHA_FIN · año 1925 ·
actividad fuera de los polígonos · ANCHO_CM con un cero de más · actividad Negativo con materiales ·
estructura fuera de su actividad · unidad sin descripción · ortoplano faltante · ráster con nombre inválido ·
fila del Metadato sin diligenciar · carpetas sin tildes (no es un error: comprueba que se encuentren igual).

La prueba exige que el conjunto de ERRORES sea **exactamente** el de `esperado_errores.json`. Si se agrega una regla
o una mutación, hay que actualizar ese archivo.

## bd_materiales.xlsx: casos que cubre

Variantes de mayúsculas y espacios («CORTE  1») · estrato en minúscula · correspondencia exacta y por patrón regex ·
actividad sin correspondencia («Trinchera 7») · patrón que apunta a una actividad inexistente («Pozo 9») ·
fila sin actividad (va a `por_defecto`) · fila sin estrato (SE) · estrato RS (unidad Superficie) · estratos nuevos
(unidades NP0008–NP0011) · profundidad en rango, en un solo valor, en dos columnas o ausente (se toma de la unidad o
queda 0-0) · coordenadas en la BD · texto largo con tildes truncado a 254 bytes · valores mapeados a dominio
(«BUENO» → Bueno, «izq» → Izquierda) · fila sin código (se ignora) · actividad Negativo que recibe materiales.

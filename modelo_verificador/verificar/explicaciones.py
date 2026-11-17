"""Explicaciones en lenguaje sencillo de cada regla: qué significa y cómo corregirla.

`explicar(regla)` devuelve el texto de la primera expresión que coincide (o "" si no hay).
"""
import re

_REGLAS = [
    (r"^Obligatorio vacío", "El catálogo exige este campo y está vacío. Diligéncielo en la tabla de atributos de la capa."),
    (r"^Obligatorio después del Registro", "Este campo es opcional en el Registro pero obligatorio desde el Diagnóstico (p. ej. el código de registro REGIS_AUTO o el ID del polígono)."),
    (r"^Fuera de dominio", "El valor no está en la lista cerrada del catálogo. Copie el valor exacto (con tildes y mayúsculas) de la hoja DOMINIOS."),
    (r"^Texto excede", "El texto es más largo de lo que admite el campo. Los límites se cuentan en bytes: cada tilde o ñ ocupa 2."),
    (r"^Estructura de campos distinta", "La capa no tiene los mismos campos que la plantilla V4. Copie la plantilla oficial y pegue los registros en ella."),
    (r"^Tipo de geometría distinto", "La capa usa otro tipo de geometría (punto, línea o polígono) que la plantilla V4."),
    (r"^Falta \.prj|^Sistema de referencia|^CRS del ortoplano", "El archivo debe estar en MAGNA-SIRGAS / Origen-Nacional (CTM12, EPSG:9377). Reproyecte o asigne el sistema correcto."),
    (r"ID duplicado", "Dos registros comparten el mismo código. Cada ID debe ser único en su capa."),
    (r"formato / longitud|no empieza por su", "El código no sigue la estructura del catálogo. Revise la longitud y que empiece por el código de su elemento padre (polígono → actividad → material)."),
    (r"^ID_[A-Z_]+: ", "El código del material no sigue la estructura ID_ACT_ARQ + prefijo de la capa + 4 dígitos."),
    (r"inexistente", "El registro apunta a un código que no existe en la capa o tabla de referencia. Corrija el código o cree el elemento que falta."),
    (r"fuera de(l| su)", "La geometría se sale del polígono que la contiene. Ajuste el dibujo o el código del polígono asignado."),
    (r"Solape entre actividades", "Dos actividades del mismo tipo se superponen. Revise si son la misma excavación o si alguna está mal dibujada."),
    (r"Geometría inválida|sin geometría", "La forma tiene errores (auto-intersecciones, sin vértices). Repárela con la herramienta de geometrías de su SIG."),
    (r"Área mínima", "La geometría es tan pequeña que probablemente es un error de digitalización."),
    (r"FECHA_INI > FECHA_FIN|Fecha vacía|Fecha futura|anterior a 2000", "Revise las fechas de inicio y fin de la actividad."),
    (r"MAT_ARQUEO", "El campo MAT_ARQUEO (Positivo / Negativo) no coincide con los materiales registrados para la actividad."),
    (r"NMERO_UNE", "NMERO_UNE debe ser el número de unidades mínimas de excavación usadas por la actividad."),
    (r"PROFUN|Profundidad", "Las profundidades deben ser positivas, en centímetros, con inicio ≤ fin y coherentes con la actividad."),
    (r"ANCHO_CM/LARGO_CM", "Las medidas declaradas no coinciden con el tamaño del polígono dibujado."),
    (r"Cuadrícula sin CORTE", "Toda cuadrícula debe indicar el corte al que pertenece."),
    (r"^Ortoplano faltante|^Ningún ortoplano", "Cortes, cuadrículas y trincheras con materiales necesitan un ortoplano GeoTIFF por unidad, nombrado <ID_ACT_ARQ>_<ID_UNI_EX>.tif."),
    (r"[Oo]rtoplano", "Revise el nombre, la ubicación y el sistema de referencia del ortoplano en la carpeta Raster."),
    (r"GeoTIFF", "La carpeta Raster solo debe contener ortoplanos en GeoTIFF (.tif)."),
    (r"Unidad (sin|compartida)|Descripción", "Revise la tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL: cada unidad necesita una descripción real con su profundidad («Profundidad: a - b cm»)."),
    (r"^No existe la tabla|^TIPO|^DESCRIPCIÓN", "Revise la tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL (.xlsx)."),
    (r"Material sin unidad", "Cada material debe indicar en ID_UNI_EX la unidad mínima donde se halló."),
    (r"mayormente vacío", "La mayoría de registros dejan este campo vacío o «sin identificar». No es un error, pero empobrece el reporte."),
    (r"[Mm]etadato|Sin diligenciar|Conteo de la capa", "Complete el Metadato (.xlsx): cada hoja de una capa entregada debe tener sus filas de obligación diligenciadas y el conteo de registros."),
    (r"FASE del polígono", "El campo FASE de los polígonos específicos no coincide con la fase que eligió. Actualícelo o elija otra fase."),
    (r"Actividad de Implementación", "El código tiene PI (Implementación) pero eligió Diagnóstico. Las actividades de diagnóstico usan DI."),
    (r"Implementación sin PMA", "En Implementación el PMA ya está aprobado: diligencie la fecha y el código (radicado) del PMA."),
    (r"Falta la capa de la fase", "Esta capa se entrega en la fase elegida y no se encontró en la carpeta."),
    (r"Capa vacía o inexistente", "No se encontró la capa o no tiene registros."),
    (r"rasterio|Plantillas V4 no encontradas", "Parte de la revisión no se hizo en este equipo; el resto del informe es válido."),
]
_COMP = [(re.compile(p), t) for p, t in _REGLAS]


def explicar(regla):
    for p, t in _COMP:
        if p.search(regla):
            return t
    return ""

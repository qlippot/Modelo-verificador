"""Herramienta 2 — Lectura de bases de datos de materiales y asignación de códigos del Modelo ICANH V4.

Flujo (sin IA, todo determinista y guiado por un archivo de configuración JSON):
  1. leer las hojas de la BD (.xlsx) indicadas en la configuración;
  2. resolver la actividad de cada fila (tabla de correspondencias exactas + patrones regex) contra las
     actividades del Modelo;
  3. resolver la unidad mínima (reutiliza unidades existentes; crea las que falten con el siguiente consecutivo);
  4. generar los IDs de materiales (ID_ACT_ARQ + prefijo de capa + consecutivo por actividad);
  5. mapear columnas de la BD a campos DBF de la plantilla V4 (truncado por bytes, tipos numéricos);
  6. entregar: asignaciones (JSON), «BD codificada» (.xlsx: copia con columnas de códigos) y, opcionalmente,
     escribir las capas y unidades nuevas en una COPIA del Modelo.

    from modelo_verificador.codificar import codificar, escribir_bd, escribir_modelo
    res = codificar("BD.xlsx", "config.json", "Modelo/")
    escribir_bd(res, "BD.xlsx", "BD - codificada.xlsx")
    escribir_modelo(res, "Modelo_staging/")      # nunca sobre el Modelo original
"""
from .motor import codificar, cargar_config
from .salidas import escribir_bd, escribir_modelo

__all__ = ["codificar", "cargar_config", "escribir_bd", "escribir_modelo"]

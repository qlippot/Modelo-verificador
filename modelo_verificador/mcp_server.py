"""Servidor MCP (stdio) de Modelo-verificador: herramientas deterministas, sin IA, para el Modelo de Datos ICANH V4.

Ejecutar:   python -m modelo_verificador.mcp_server        (o: modelo-verificador-mcp)

Variable de entorno opcional:
  MODELO_VERIFICADOR_RAIZ   Si se define, todas las rutas deben estar dentro de esa carpeta.

La lógica vive en `servicios.py` (compartida con la WebApp); aquí solo se registran las herramientas.
"""
import functools

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__, servicios

INSTRUCCIONES = """\
Herramientas para el Modelo de Datos Geográfico ICANH V4 (arqueología preventiva, Colombia). Todo es determinista.
Dos herramientas principales:
1. verificar_modelo: revisa una carpeta de Modelo (shapefiles + Unidad Mínima + Metadato + Raster) contra el catálogo
   y las plantillas oficiales V4. Solo lee. Hallazgos ERROR / AVISO / INFO; «apto» = 0 ERRORES.
2. codificar_bd: lee una base de datos de materiales (.xlsx) y asigna ID_ACT_ARQ, ID_UNI_EX e IDs de materiales según
   una configuración JSON. Para preparar la configuración: inspeccionar_bd (columnas), resumen_modelo (actividades y
   unidades), ejemplo_config, y validar_config antes de codificar.
Flujo seguro para escribir: crear_copia_staging → codificar_bd(escribir_en=<copia>) → verificar_modelo(<copia>).
Nunca se escribe sobre el Modelo leído ni sobre la BD original.
Utilidades: analizar_id, generar_id, siguiente_id, listar_capas, campos_capa, dominio.
"""

servidor = MCPServer(name="modelo-verificador", title="Modelo-verificador ICANH V4", version=__version__,
                     instructions=INSTRUCCIONES)

_LECTURA = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
_ESCRITURA = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False)
_CREA = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


def herramienta(anotaciones):
    """Registra una herramienta; los errores previstos (rutas, configuración, datos) llegan al cliente con su mensaje."""
    def deco(fn):
        @functools.wraps(fn)
        def envuelta(*a, **k):
            try:
                return fn(*a, **k)
            except ToolError:
                raise
            except (ValueError, KeyError, FileNotFoundError, NotADirectoryError, PermissionError) as e:
                raise ToolError(str(e).strip("'\"")) from e
        return servidor.tool(annotations=anotaciones)(envuelta)
    return deco



for _nombre, _anot in [("verificar_modelo", _LECTURA), ("resumen_modelo", _LECTURA), ("inspeccionar_bd", _LECTURA),
                       ("ejemplo_config", _LECTURA), ("validar_config", _LECTURA), ("crear_copia_staging", _CREA),
                       ("codificar_bd", _ESCRITURA), ("analizar_id", _LECTURA), ("generar_id", _LECTURA),
                       ("siguiente_id", _LECTURA), ("listar_capas", _LECTURA), ("campos_capa", _LECTURA),
                       ("dominio", _LECTURA)]:
    herramienta(_anot)(getattr(servicios, _nombre))


def main():
    servidor.run("stdio")


if __name__ == "__main__":
    main()

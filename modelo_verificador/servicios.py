"""Servicios deterministas compartidos por el servidor MCP, la WebApp local y la versión en navegador (Pyodide).

Cada función recibe y devuelve datos serializables a JSON. Rutas:
  - por defecto, absolutas o relativas al directorio actual, confinadas a MODELO_VERIFICADOR_RAIZ si está definida;
  - dentro de `en_base(carpeta)` (WebApp), relativas a esa carpeta de sesión y sin poder salir de ella.
"""
import os
import json
import shutil
import zipfile
import contextlib
from typing import Any, Literal

import openpyxl

from . import ids as _ids, catalogo as _cat, rutas
from .modelo import Modelo
from .texto import s
from .verificar import verificar_todo
from .codificar import codificar, cargar_config, escribir_bd, escribir_modelo

_BASE = None


@contextlib.contextmanager
def en_base(carpeta):
    """Resuelve todas las rutas relativas a `carpeta` (sesión de la WebApp) y prohíbe salir de ella."""
    global _BASE
    anterior, _BASE = _BASE, os.path.realpath(carpeta)
    try:
        yield _BASE
    finally:
        _BASE = anterior


def _mostrar(r):
    """Ruta para mensajes y resultados: relativa a la sesión si hay base (no expone rutas del equipo)."""
    return os.path.relpath(r, _BASE) if _BASE else r


def _ruta(p, existe=True, tipo=None):
    """Ruta absoluta validada y confinada (a la sesión web, o a MODELO_VERIFICADOR_RAIZ si está definida)."""
    if not p or not str(p).strip():
        raise ValueError("Ruta vacía")
    p = os.path.expanduser(str(p))
    if _BASE:
        r = os.path.realpath(os.path.join(_BASE, p))
        if os.path.commonpath([r, _BASE]) != _BASE:
            raise ValueError(f"Ruta fuera de la sesión: {p}")
    else:
        r = os.path.realpath(p)
        raiz = os.environ.get("MODELO_VERIFICADOR_RAIZ")
        if raiz:
            raiz = os.path.realpath(os.path.expanduser(raiz))
            if os.path.commonpath([r, raiz]) != raiz:
                raise ValueError(f"La ruta está fuera de la carpeta permitida (MODELO_VERIFICADOR_RAIZ): {r}")
    if existe and not os.path.exists(r):
        raise ValueError(f"No existe: {_mostrar(r)}")
    if existe and tipo == "dir" and not os.path.isdir(r):
        raise ValueError(f"No es una carpeta: {_mostrar(r)}")
    if existe and tipo == "file" and not os.path.isfile(r):
        raise ValueError(f"No es un archivo: {_mostrar(r)}")
    return r


def _config(config):
    """Configuración como ruta a .json o como objeto JSON."""
    if isinstance(config, dict):
        return cargar_config(config)
    if isinstance(config, str) and config.strip().startswith("{"):
        return cargar_config(json.loads(config))
    return cargar_config(_ruta(config, tipo="file"))


# ------------------------------------------------------------------ herramienta 1: verificar
def verificar_modelo(ruta_modelo: str,
                     modulos: list[Literal["formato", "coherencia", "faltantes"]] = ["formato", "coherencia", "faltantes"],
                     completo: bool = False, ejemplos: int = 5) -> dict[str, Any]:
    """Verifica un Modelo de Datos ICANH V4 (solo lectura).

    Módulos: «formato» (estructura vs. plantilla V4, CRS, obligatorios, dominios, longitudes en bytes, formato y
    unicidad de IDs, vínculos, profundidades), «coherencia» (contención entre polígonos, solapes, fechas, medidas vs.
    geometría, MAT_ARQUEO vs. contenido, ortoplanos, conteos del Metadato) y «faltantes» (ortoplanos requeridos,
    campos vacíos, unidades sin descripción, Metadato sin diligenciar).
    Devuelve conteo por nivel, «apto» (0 ERRORES) y, por módulo, un resumen agrupado por regla con `ejemplos`
    casos. `completo=True` añade la lista de todos los hallazgos.
    """
    res = verificar_todo(_ruta(ruta_modelo, tipo="dir"), tuple(modulos), completo, ejemplos)
    res["modelo"] = _mostrar(res["modelo"])
    return res


def resumen_modelo(ruta_modelo: str) -> dict[str, Any]:
    """Inventario de un Modelo: capas presentes con su número de registros, polígonos específicos, actividades
    (ID, tipo, MAT_ARQUEO, materiales por capa) y unidades mínimas (ID, tipo, inicio de la descripción).
    Útil para escribir la tabla de correspondencias de actividades de la configuración del codificador."""
    M = Modelo(_ruta(ruta_modelo, tipo="dir"))
    capas = {c: len(M.registros(c)) for c in M.capas_presentes()}
    por_act = {}
    for L in M.capas_materiales():
        for rec, _ in M.registros(L):
            por_act.setdefault(rec.get("ID_ACT_ARQ"), {}).setdefault(rutas.norm(L), 0)
            por_act[rec.get("ID_ACT_ARQ")][rutas.norm(L)] += 1
    acts = [dict(id=a, tipo=v["rec"].get("TIPO_ACT"), corte=v["rec"].get("CORTE"), mat_arqueo=v["rec"].get("MAT_ARQUEO"),
                 fecha_ini=str(v["rec"].get("FECHA_INI")), fecha_fin=str(v["rec"].get("FECHA_FIN")),
                 materiales=por_act.get(a, {})) for a, v in sorted(M.actividades().items())]
    unis = [dict(id=u, tipo=t, descripcion=str(d or "")[:90]) for _, u, t, d in M.unidades()]
    pes = [r.get("ID_POL_ESP") for r, _ in M.registros("POLIGONOS ESPECIFICOS")]
    rd = M.carpeta_raster()
    return dict(modelo=_mostrar(M.raiz), capas=capas, poligonos_especificos=pes, actividades=acts, unidades=unis,
                rasteres=sorted(f for f in os.listdir(rd) if not f.startswith(".")) if rd else [],
                metadato=_mostrar(M.ruta_metadato()) if M.ruta_metadato() else None)


# ------------------------------------------------------------------ herramienta 2: codificar
def inspeccionar_bd(ruta_bd: str, filas_muestra: int = 3, fila_encabezado: int = 1) -> dict[str, Any]:
    """Estructura de una base de datos .xlsx: por hoja, encabezados, número de filas con datos y algunas filas de
    muestra. Primer paso para escribir la configuración del codificador (qué columna es el ID, la actividad, el
    estrato, la profundidad…)."""
    wb = openpyxl.load_workbook(_ruta(ruta_bd, tipo="file"), read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < fila_encabezado:
            out[ws.title] = dict(encabezados=[], filas=0, muestra=[])
            continue
        hdr = [s(x) for x in rows[fila_encabezado - 1]]
        datos = [r for r in rows[fila_encabezado:] if any(v not in (None, "") for v in r)]
        out[ws.title] = dict(encabezados=[h for h in hdr if h], filas=len(datos),
                             muestra=[{h: (s(v) if v is not None else None) for h, v in zip(hdr, r) if h} for r in datos[:filas_muestra]])
    return dict(bd=ruta_bd, hojas=out)


def ejemplo_config() -> dict[str, Any]:
    """Ejemplo comentado de la configuración JSON del codificador (actividades exactas/patrones/por_defecto,
    unidades, hojas con columnas y campos: columna directa, {"valor"}, {"columna","mapa","defecto"},
    {"concatenar"}, {"segun_cantidad"}; profundidad {"rango"} o {"ini","fin"}; coordenadas {"x","y"};
    modo «reemplazar» o «agregar»)."""
    p = os.path.join(os.path.dirname(rutas.REFERENCIA), "ejemplos", "config_codificacion.ejemplo.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validar_config(config: dict[str, Any] | str, ruta_bd: str | None = None, ruta_modelo: str | None = None) -> dict[str, Any]:
    """Valida una configuración del codificador (ruta a .json, texto JSON u objeto) sin codificar nada.
    Con `ruta_bd`: comprueba que existan las hojas y columnas referidas. Con `ruta_modelo`: que los ID_ACT_ARQ de las
    correspondencias exactas y por_defecto existan en ACTIVIDADES. Devuelve `valida` y la lista de problemas."""
    problemas = []
    try:
        cfg = _config(config)
    except Exception as e:
        return dict(valida=False, problemas=[f"Configuración inválida: {e}"])
    if ruta_bd:
        wb = openpyxl.load_workbook(_ruta(ruta_bd, tipo="file"), read_only=True)
        for hoja, h in cfg.get("hojas", {}).items():
            if hoja not in wb.sheetnames:
                problemas.append(f"La BD no tiene la hoja «{hoja}» (hojas: {wb.sheetnames})")
                continue
            fh = h.get("fila_encabezado", cfg["fila_encabezado"])
            hdr = next(wb[hoja].iter_rows(min_row=fh, max_row=fh, values_only=True), ())
            hdr = {s(x) for x in hdr if x is not None}
            cols = [h["id_bd"], h["actividad"], h.get("estrato")]
            pc = h.get("profundidad") or {}
            cols += [pc.get("rango"), pc.get("ini"), pc.get("fin")]
            co = h.get("coordenadas") or {}
            cols += [co.get("x"), co.get("y")]
            for spec in h.get("campos", {}).values():
                if isinstance(spec, str):
                    cols.append(spec)
                elif isinstance(spec, dict):
                    cols += [spec.get("columna"), spec.get("segun_cantidad")] + [c for _, c in spec.get("concatenar", [])]
            for c in sorted({c for c in cols if c}):
                if c not in hdr:
                    problemas.append(f"Hoja «{hoja}»: no existe la columna «{c}»")
    if ruta_modelo:
        acts = Modelo(_ruta(ruta_modelo, tipo="dir")).actividades()
        a = cfg.get("actividades", {})
        for etq, ida in a.get("exactas", {}).items():
            if ida not in acts:
                problemas.append(f"Correspondencia «{etq}» → {ida}: no existe en ACTIVIDADES")
        if a.get("por_defecto") and a["por_defecto"] not in acts:
            problemas.append(f"por_defecto {a['por_defecto']}: no existe en ACTIVIDADES")
    from .codificar.motor import _campos_plantilla
    for hoja, h in cfg.get("hojas", {}).items():
        nombres = [c[0] for c in _campos_plantilla(h["capa"])]
        for fld in h.get("campos", {}):
            if fld not in nombres:
                problemas.append(f"Hoja «{hoja}»: el campo «{fld}» no existe en la plantilla de {h['capa']}")
    return dict(valida=not problemas, problemas=problemas, modo=cfg["modo"], hojas={k: v["capa"] for k, v in cfg.get("hojas", {}).items()})


def crear_copia_staging(ruta_modelo: str, destino: str) -> dict[str, Any]:
    """Copia completa de un Modelo a una carpeta NUEVA (no debe existir), para escribir en ella con codificar_bd
    sin tocar el original."""
    src = _ruta(ruta_modelo, tipo="dir")
    dst = _ruta(destino, existe=False)
    if os.path.exists(dst):
        raise ValueError(f"El destino ya existe: {dst}")
    if os.path.commonpath([src, dst]) == src:
        raise ValueError("El destino no puede estar dentro del Modelo original")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".DS_Store"))
    return dict(origen=_mostrar(src), copia=_mostrar(dst), archivos=sum(len(f) for _, _, f in os.walk(dst)))


def codificar_bd(ruta_bd: str, config: dict[str, Any] | str, ruta_modelo: str,
                 ruta_bd_salida: str | None = None, escribir_en: str | None = None,
                 incluir_asignaciones: bool = True, sobrescribir_salida: bool = False) -> dict[str, Any]:
    """Codifica una BD de materiales: por cada fila, resuelve la actividad (ID_ACT_ARQ), la unidad mínima (ID_UNI_EX;
    reutiliza o crea) y genera los IDs de materiales (ID_ACT_ARQ + prefijo + consecutivo por actividad).

    Lee `ruta_modelo` (nunca lo modifica). Sin `ruta_bd_salida` ni `escribir_en` no escribe nada.
    - `ruta_bd_salida`: escribe la «BD codificada» (copia .xlsx con columnas de códigos + hojas «Unidades nuevas» y
      «Resumen codificación»). No puede ser la BD original; si existe, requiere `sobrescribir_salida=True`.
    - `escribir_en`: carpeta de una COPIA del Modelo (ver crear_copia_staging) donde se escriben las capas de
      materiales configuradas y las unidades nuevas. En modo «reemplazar» esas capas se reescriben solo con la BD.
    Devuelve el reporte (filas ok/sin resolver, unidades nuevas, truncados, actividades que pasarían a Positivo) y,
    si `incluir_asignaciones`, el detalle por fila."""
    bd = _ruta(ruta_bd, tipo="file")
    modelo = _ruta(ruta_modelo, tipo="dir")
    res = codificar(bd, _config(config), modelo)
    out = dict(reporte=res["reporte"], unidades_nuevas=list(res["unidades_nuevas"].values()))
    if ruta_bd_salida:
        dst = _ruta(ruta_bd_salida, existe=False)
        if os.path.exists(dst) and not sobrescribir_salida:
            raise ValueError(f"Ya existe {dst}; usar sobrescribir_salida=True para reemplazarlo")
        out["bd_codificada"] = _mostrar(escribir_bd(res, bd, dst))
    if escribir_en:
        dst = _ruta(escribir_en, tipo="dir")
        if dst == modelo or os.path.commonpath([dst, modelo]) in (dst, modelo):
            raise ValueError("escribir_en debe ser una copia separada del Modelo leído (ver crear_copia_staging)")
        out["escritura"] = escribir_modelo(res, dst)
    if incluir_asignaciones:
        out["asignaciones"] = [{k: a[k] for k in ("hoja", "fila", "id_bd", "estado", "ID_ACT_ARQ", "ID_UNI_EX", "ids_modelo", "notas")}
                               for a in res["asignaciones"]]
    return out


# ------------------------------------------------------------------ utilidades de IDs y catálogo
def analizar_id(codigo: str, capa: str | None = None) -> dict[str, Any]:
    """Identifica y descompone un código del Modelo (polígono, zonificación, actividad DI/PI, unidad ND/NP o material
    de cualquier capa) y lista sus errores de formato/longitud según el catálogo V4. `capa` fuerza la lectura como
    material de esa capa (p. ej. CERAMICAS)."""
    return _ids.analizar(codigo, capa=rutas.norm(capa) if capa else None)


def generar_id(tipo: Literal["poligono", "zonificacion", "actividad", "unidad", "material",
                             "actividad_intervencion", "unidad_intervencion"],
               base: str, numero: int, fase: Literal["PI", "DI"] = "PI", capa: str | None = None) -> dict[str, Any]:
    """Construye un código a partir de su base y consecutivo.
    base: registro (8, p. ej. R0125A22) para poligono / *_intervencion; polígono específico (12) para zonificacion,
    actividad y unidad; ID_ACT_ARQ (19) para material (requiere `capa`). fase: PI (Implementación) / DI (Aprobación PMA)."""
    b = base.strip()
    if tipo == "poligono":
        c = _ids.poligono(b, numero)
    elif tipo == "zonificacion":
        c = _ids.zonificacion(b, numero)
    elif tipo == "actividad":
        c = _ids.actividad(b, numero, fase)
    elif tipo == "unidad":
        c = _ids.unidad(b, numero, fase)
    elif tipo == "actividad_intervencion":
        c = _ids.actividad_intervencion(b, numero)
    elif tipo == "unidad_intervencion":
        c = _ids.unidad_intervencion(b, numero)
    else:
        if not capa:
            raise ValueError("tipo «material» requiere `capa`")
        c = _ids.material(b, rutas.norm(capa), numero)
    return _ids.analizar(c, capa=rutas.norm(capa) if tipo == "material" else None)


def siguiente_id(ruta_modelo: str, tipo: Literal["poligono", "zonificacion", "actividad", "unidad", "material"],
                 base: str, fase: Literal["PI", "DI"] = "PI", capa: str | None = None) -> dict[str, Any]:
    """Siguiente código libre en un Modelo, tras el mayor consecutivo existente con esa base.
    base: registro (8) para poligono; polígono específico (12) para zonificacion / actividad / unidad;
    ID_ACT_ARQ (19) para material (requiere `capa`)."""
    M = Modelo(_ruta(ruta_modelo, tipo="dir"))
    b = base.strip()
    if tipo == "poligono":
        exist, pref, ancho = [r.get("ID_POL_ESP") for r, _ in M.registros("POLIGONOS ESPECIFICOS")], b, 4
    elif tipo == "zonificacion":
        exist, pref, ancho = [r.get("ID_ZON_ARQ") for r, _ in M.registros("ZONIFICACION ARQUEOLOGICA")], b + "ZO", 4
    elif tipo == "actividad":
        exist, pref, ancho = list(M.actividades()), b + fase, 5
    elif tipo == "unidad":
        exist, pref, ancho = [u for _, u, _, _ in M.unidades()], b + ("NP" if fase == "PI" else "ND"), 4
    else:
        if not capa:
            raise ValueError("tipo «material» requiere `capa`")
        m = _ids.MATERIALES[rutas.norm(capa)]
        exist = [r.get(m.campo) for r, _ in M.registros(m.capa)]
        pref, ancho = b + m.prefijo, 4
    n = _ids.siguiente(exist, pref, ancho)
    return dict(siguiente=f"{pref}{n:0{ancho}d}", consecutivo=n, existentes_con_esa_base=n - 1 if n > 1 else 0)


def listar_capas() -> dict[str, Any]:
    """Capas y tablas del catálogo V4, y para las de materiales su campo ID, prefijo y longitud."""
    return dict(capas=_cat.cargar().capas(),
                materiales={m.capa: dict(campo=m.campo, prefijo=m.prefijo, longitud=m.longitud) for m in _ids.MATERIALES.values()})


def campos_capa(capa: str) -> dict[str, Any]:
    """Campos de una capa según el catálogo: nombre, etiqueta, tipo, longitud, obligación y si tiene dominio."""
    cat = _cat.cargar()
    c = cat.capa(capa)
    if not c:
        raise ValueError(f"Capa «{capa}» no está en el catálogo. Capas: {cat.capas()}")
    return dict(capa=rutas.norm(capa), campos=[dict(campo=a.nombre, etiqueta=a.etiqueta, tipo=a.tipo, longitud=a.longitud,
                                                    obligacion=a.obligacion, obligatorio=a.obligatorio, dominio=a.con_dominio)
                                               for a in c.values() if a.tipo])


def dominio(capa: str, campo: str) -> dict[str, Any]:
    """Valores permitidos (hoja DOMINIOS del catálogo) para un campo con dominio, p. ej. ESTRUCTURAS / TIPO_OBJEC."""
    vals = _cat.cargar().dominio(capa, campo)
    if not vals:
        raise ValueError(f"{capa}.{campo} no tiene dominio en el catálogo (o no existe)")
    return dict(capa=rutas.norm(capa), campo=campo, valores=vals)



# ------------------------------------------------------------------ solo WebApp (sesión)
def borrar(ruta: str) -> dict[str, Any]:
    """Borra un archivo o carpeta DENTRO de la sesión web (no disponible fuera de ella)."""
    if not _BASE:
        raise ValueError("borrar solo está disponible dentro de una sesión de la WebApp")
    r = _ruta(ruta, existe=False)
    if r == _BASE:
        raise ValueError("No se puede borrar la sesión completa")
    if os.path.isdir(r):
        shutil.rmtree(r)
    elif os.path.exists(r):
        os.remove(r)
    return dict(borrado=_mostrar(r))


def empaquetar(carpeta: str, destino_zip: str) -> dict[str, Any]:
    """Comprime una carpeta en un .zip (para descargar la copia del Modelo codificada)."""
    src = _ruta(carpeta, tipo="dir")
    dst = _ruta(destino_zip, existe=False)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    nombre = os.path.basename(src.rstrip("/"))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for d, _, fs in os.walk(src):
            for f in sorted(fs):
                if f != ".DS_Store":
                    p = os.path.join(d, f)
                    z.write(p, os.path.join(nombre, os.path.relpath(p, src)))
    return dict(zip=_mostrar(dst), bytes=os.path.getsize(dst))


def cargar_ejemplo(destino: str = "ejemplo") -> dict[str, Any]:
    """Copia los datos sintéticos del repositorio (Modelos, BD y config) a `destino` para probar sin datos reales."""
    src = os.path.join(os.path.dirname(rutas.REFERENCIA), "datos_sinteticos")
    if not os.path.isdir(os.path.join(src, "modelo_minimo")):
        raise ValueError("Los datos sintéticos no están disponibles en esta instalación")
    dst = _ruta(destino, existe=False)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for n in ("modelo_minimo", "modelo_con_errores"):
        shutil.copytree(os.path.join(src, n), os.path.join(dst, n), ignore=shutil.ignore_patterns(".DS_Store"))
    for n in ("bd_materiales.xlsx", "config.json"):
        shutil.copy(os.path.join(src, n), os.path.join(dst, n))
    return dict(carpeta=_mostrar(dst), modelos=["modelo_minimo", "modelo_con_errores"], bd="bd_materiales.xlsx", config="config.json")


PUBLICAS = ["verificar_modelo", "resumen_modelo", "inspeccionar_bd", "ejemplo_config", "validar_config",
            "crear_copia_staging", "codificar_bd", "analizar_id", "generar_id", "siguiente_id",
            "listar_capas", "campos_capa", "dominio"]
WEB = PUBLICAS + ["borrar", "empaquetar", "cargar_ejemplo"]


def llamar(nombre, argumentos, base):
    """Ejecuta un servicio dentro de la sesión `base`. Devuelve {"ok": True, "resultado": …} o {"ok": False, "error": …}."""
    if nombre not in WEB:
        return dict(ok=False, error=f"Servicio desconocido: {nombre}")
    try:
        with en_base(base):
            return dict(ok=True, resultado=globals()[nombre](**(argumentos or {})))
    except (ValueError, KeyError, FileNotFoundError, NotADirectoryError, PermissionError, TypeError) as e:
        return dict(ok=False, error=str(e).strip("'\""))


def llamar_json(nombre, argumentos_json, base):
    """Versión texto→texto de `llamar` (puente con JavaScript en Pyodide)."""
    return json.dumps(llamar(nombre, json.loads(argumentos_json or "{}"), base), ensure_ascii=False, default=str)

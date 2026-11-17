"""Motor de codificación: BD de materiales → asignaciones con IDs del Modelo (no escribe nada)."""
import re
import json
import collections

import openpyxl
import shapefile

from .. import ids as _ids, rutas
from ..modelo import Modelo
from ..texto import s, num, tiene, ajustar, rango_profundidad, par_profundidad, profundidad_en_descripcion

DEFAULTS = dict(modo="reemplazar", sin_profundidad=[0, 0], fila_encabezado=1,
                unidades=dict(superficie=["RS", "SUPERFICIE"], sin_estrato="SE", tipo="Unidad estratigráfica", fijas={}))


def cargar_config(cfg):
    if isinstance(cfg, str):
        with open(cfg, encoding="utf-8") as f:
            cfg = json.load(f)
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in cfg.items():
        if k == "unidades":
            out["unidades"].update(v)
        elif not k.startswith("_"):
            out[k] = v
    if out["modo"] not in ("reemplazar", "agregar"):
        raise ValueError("modo debe ser 'reemplazar' o 'agregar'")
    for hoja, h in out.get("hojas", {}).items():
        capa = rutas.norm(h.get("capa", ""))
        if capa not in _ids.MATERIALES:
            raise ValueError(f"Hoja «{hoja}»: capa «{h.get('capa')}» no es una capa de materiales del catálogo")
        h["capa"] = capa
        for k in ("id_bd", "actividad"):
            if not h.get(k):
                raise ValueError(f"Hoja «{hoja}»: falta «{k}» (nombre de columna)")
    return out


def _clave(t):
    return re.sub(r"\s+", " ", s(t)).lower()


def _estrato(t):
    return re.sub(r"\s+", "", s(t)).upper()


class _Resolvedor:
    def __init__(self, cfg, M):
        a = cfg.get("actividades", {})
        self.exactas = {_clave(k): v for k, v in a.get("exactas", {}).items()}
        self.patrones = [(re.compile(p["regex"], re.I), p["id"]) for p in a.get("patrones", [])]
        self.defecto = a.get("por_defecto")
        self.ACT = M.actividades()

    def actividad(self, raw):
        """-> (id_act | None, nota)"""
        v = s(raw)
        if _ids.es_valido(v, "actividad"):
            ida = v
        elif _clave(v) in self.exactas:
            ida = self.exactas[_clave(v)]
        else:
            ida = None
            for rx, plantilla in self.patrones:
                m = rx.match(v)
                if m:
                    g = [int(x) if x and x.isdigit() else x for x in m.groups()]
                    ida = plantilla.format(None, *g)
                    break
            if ida is None and self.defecto and not tiene(v):
                return (self.defecto, f"Sin actividad en la BD → {self.defecto} (por_defecto)") if self.defecto in self.ACT \
                    else (None, f"por_defecto {self.defecto} no existe en el Modelo")
        if ida is None:
            return None, f"Actividad «{v}» sin correspondencia en la configuración"
        if ida not in self.ACT:
            return None, f"«{v}» → {ida}, que no existe en ACTIVIDADES del Modelo"
        return ida, ""


class _Unidades:
    """Reutiliza o crea unidades mínimas. Etiqueta estable «<PIxxxxx>-<ESTRATO>:» al inicio de la descripción."""

    def __init__(self, cfg, M):
        self.cfg = cfg["unidades"]
        self.sup = {_estrato(x) for x in self.cfg["superficie"]}
        self.fijas = {k: v for k, v in self.cfg.get("fijas", {}).items()}
        self.existentes = {uid: (tipo, str(desc or "")) for _, uid, tipo, desc in M.unidades() if uid}
        self.por_etiqueta = {}
        for uid, (_, d) in self.existentes.items():
            m = re.match(r"^([^:]{1,60}?)\s*:", d)
            if m:
                self.por_etiqueta.setdefault(m.group(1).strip(), uid)
        self.contador = _ids.Contador(self.existentes, ancho=4)
        self.contador_int = _ids.Contador(self.existentes, ancho=9)
        self.nuevas = {}     # uid -> dict(id, tipo, descripcion, profundidad, etiqueta, materiales)

    def resolver(self, id_act, act_bd, estrato_raw, capa):
        """-> (uid, (ini, fin) | None, nota)"""
        e = _estrato(estrato_raw) if tiene(estrato_raw) else self.cfg["sin_estrato"]
        if _ids.es_valido(e, "unidad"):
            if e in self.existentes:
                return e, profundidad_en_descripcion(self.existentes[e][1]), ""
            return None, None, f"Unidad {e} no existe en la tabla UNIDAD MÍNIMA"
        for k in (f"{id_act}|{e}", f"{_clave(act_bd)}|{e.lower()}", f"{s(act_bd)}|{e}"):
            if k in self.fijas:
                u = self.fijas[k]
                d = self.existentes.get(u, ("", ""))[1]
                return u, profundidad_en_descripcion(d), f"unidad fija por configuración ({k})"
        corto = id_act[12:] if id_act[8] != "I" else id_act[8:]
        etiqueta = f"{corto}-{e}"
        if etiqueta in self.por_etiqueta:
            u = self.por_etiqueta[etiqueta]
            d = self.existentes.get(u, ("", self.nuevas.get(u, {}).get("descripcion", "")))[1]
            if u in self.nuevas:
                self.nuevas[u]["materiales"].add(capa)
            return u, profundidad_en_descripcion(d), ""
        sup = e in self.sup
        if id_act[8] == "I":
            uid = self.contador_int.nuevo(id_act[:8] + "N")
        else:
            uid = self.contador.nuevo(id_act[:12] + ("ND" if id_act[12:14] == "DI" else "NP"))
        tipo = "Superficie" if sup else self.cfg["tipo"]
        desc = (f"{etiqueta}: Recolección de materiales en superficie. Profundidad: 0 - 0 cm." if sup else
                f"{etiqueta}: Estrato «{s(estrato_raw) or 'sin estrato'}» registrado en la base de datos; sin descripción.")
        self.nuevas[uid] = dict(id=uid, tipo=tipo, descripcion=desc, profundidad=(0, 0) if sup else None,
                                etiqueta=etiqueta, actividad=id_act, materiales={capa})
        self.por_etiqueta[etiqueta] = uid
        return uid, ((0, 0) if sup else None), "unidad nueva"


def _valor(spec, fila):
    """Valor de un campo según su especificación en la configuración."""
    if isinstance(spec, str):
        return fila.get(spec)
    if "valor" in spec:
        return spec["valor"]
    if "concatenar" in spec:
        partes = []
        for et, col in spec["concatenar"]:
            v = s(fila.get(col))
            if tiene(v):
                partes.append(f"{et}: {v}" if et else v)
        return spec.get("separador", " | ").join(partes) or spec.get("defecto")
    if "segun_cantidad" in spec:
        n = num(fila.get(spec["segun_cantidad"])) or 1
        return spec.get("uno", "Unidad") if n <= 1 else spec.get("varios", "Conjunto")
    v = fila.get(spec.get("columna"))
    if "mapa" in spec:
        m = {_clave(k): x for k, x in spec["mapa"].items()}
        v = m.get(_clave(v), v if spec.get("conservar_no_mapeados", False) else None)
    if not tiene(v):
        v = spec.get("defecto")
    return v


def _campos_plantilla(capa):
    tpl = rutas.plantilla(capa)
    if not tpl:
        raise FileNotFoundError(f"No se encontró la plantilla V4 de {capa} en {rutas.PLANTILLAS}")
    r = shapefile.Reader(tpl, encoding="utf-8")
    f = [tuple(x[:4]) for x in r.fields[1:]]
    r.close()
    return f


def _convertir(v, tipo, largo, dec):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None if tipo in ("N", "F", "D") else ""
    if tipo == "C":
        return ajustar(v, int(largo))
    if tipo in ("N", "F"):
        x = num(v)
        if x is None:
            return None
        return int(round(x)) if int(dec) == 0 else round(x, int(dec))
    return v


def _leer_hoja(wb, nombre, fila_hdr):
    if nombre not in wb.sheetnames:
        raise KeyError(f"La BD no tiene la hoja «{nombre}» (hojas: {wb.sheetnames})")
    rows = list(wb[nombre].iter_rows(values_only=True))
    h = [s(x) for x in rows[fila_hdr - 1]] if len(rows) >= fila_hdr else []
    for i, r in enumerate(rows[fila_hdr:], start=fila_hdr + 1):
        r = list(r) + [None] * (len(h) - len(r))
        yield i, {h[j]: r[j] for j in range(len(h)) if h[j]}, h


def codificar(bd, config, modelo):
    """Devuelve dict con 'asignaciones', 'registros' (por capa), 'unidades_nuevas', 'reporte'. No escribe archivos."""
    cfg = cargar_config(config)
    M = modelo if isinstance(modelo, Modelo) else Modelo(modelo)
    RA, UN = _Resolvedor(cfg, M), _Unidades(cfg, M)
    ACT = M.actividades()
    wb = openpyxl.load_workbook(bd, read_only=True, data_only=True)

    asign, registros = [], collections.defaultdict(list)
    rep = dict(filas=collections.Counter(), sin_resolver=collections.Counter(), sin_profundidad=collections.Counter(),
               truncados=collections.Counter(), columnas_faltantes={})
    for hoja, h in cfg.get("hojas", {}).items():
        capa = h["capa"]
        campos = _campos_plantilla(capa)
        nombres = [c[0] for c in campos]
        mat = _ids.MATERIALES[capa]
        faltan = set()
        for fila, d, hdr in _leer_hoja(wb, hoja, h.get("fila_encabezado", cfg["fila_encabezado"])):
            if not faltan and fila == h.get("fila_encabezado", cfg["fila_encabezado"]) + 1:
                usadas = [h["id_bd"], h["actividad"], h.get("estrato")] + [
                    (v if isinstance(v, str) else v.get("columna") or v.get("segun_cantidad")) for v in h.get("campos", {}).values()]
                faltan = {c for c in usadas if c and c not in hdr}
                if faltan:
                    rep["columnas_faltantes"][hoja] = sorted(faltan)
            if not tiene(d.get(h["id_bd"])):
                continue
            a = dict(hoja=hoja, fila=fila, id_bd=s(d.get(h["id_bd"])), capa=capa, actividad_bd=s(d.get(h["actividad"])),
                     estrato_bd=s(d.get(h.get("estrato"))) if h.get("estrato") else "",
                     estado="ok", ID_ACT_ARQ="", ID_UNI_EX="", ids_modelo=[], notas=[])
            asign.append(a)
            ida, nota = RA.actividad(d.get(h["actividad"]))
            if nota:
                a["notas"].append(nota)
            if not ida:
                a["estado"] = "sin_resolver"
                rep["sin_resolver"][f"{hoja} | {a['actividad_bd'] or '(vacío)'}"] += 1
                rep["filas"]["sin_resolver"] += 1
                continue
            a["ID_ACT_ARQ"] = ida
            prof_u = None
            if "ID_UNI_EX" in nombres:
                uid, prof_u, nu = UN.resolver(ida, a["actividad_bd"], d.get(h.get("estrato")) if h.get("estrato") else "", capa)
                if not uid:
                    a["estado"] = "sin_resolver"; a["notas"].append(nu)
                    rep["sin_resolver"][f"{hoja} | unidad"] += 1; rep["filas"]["sin_resolver"] += 1
                    continue
                a["ID_UNI_EX"] = uid
                if nu:
                    a["notas"].append(nu)
            rec = {}
            for fld, spec in h.get("campos", {}).items():
                if fld not in nombres:
                    raise ValueError(f"Hoja «{hoja}»: el campo «{fld}» no existe en la plantilla de {capa} ({nombres})")
                rec[fld] = _valor(spec, d)
            pc = h.get("profundidad")
            prof_bd = None
            if pc:
                prof_bd = rango_profundidad(d.get(pc["rango"])) if "rango" in pc else par_profundidad(d.get(pc.get("ini")), d.get(pc.get("fin")))
            prof = prof_bd or prof_u
            if "PROFUN_INI" in nombres:
                if prof is None:
                    prof = tuple(cfg["sin_profundidad"])
                    a["notas"].append(f"Sin profundidad en la BD ni en la unidad → {prof[0]}-{prof[1]}")
                    rep["sin_profundidad"][capa] += 1
                elif not prof_bd:
                    a["notas"].append("Profundidad tomada de la descripción de la unidad")
                rec["PROFUN_INI"], rec["PROFUN_FIN"] = prof
            xy = None
            co = h.get("coordenadas")
            if co and num(d.get(co["x"])) is not None and num(d.get(co["y"])) is not None:
                xy = (num(d.get(co["x"])), num(d.get(co["y"])))
            if xy is None:
                xy = ACT[ida]["centroide"]
                a["notas"].append("Punto en el centroide de la actividad")
            final = {}
            for (fld, tipo, largo, dec) in campos:
                v = rec.get(fld)
                cv = _convertir(v, tipo, largo, dec)
                if tipo == "C" and v is not None and cv != s(v):
                    rep["truncados"][f"{capa}.{fld}"] += 1
                final[fld] = cv
            final["ID_ACT_ARQ"] = ida
            if "ID_UNI_EX" in nombres:
                final["ID_UNI_EX"] = a["ID_UNI_EX"]
            registros[capa].append(dict(asig=len(asign) - 1, campos=final, xy=xy))
            rep["filas"]["ok"] += 1

    # IDs de materiales: consecutivo por actividad y capa
    existentes = M.ids_materiales() if cfg["modo"] == "agregar" else {}
    cont = _ids.Contador(existentes, ancho=4)
    for capa, items in registros.items():
        mat = _ids.MATERIALES[capa]
        for it in items:
            nid = cont.nuevo(it["campos"]["ID_ACT_ARQ"] + mat.prefijo)
            it["campos"][mat.campo] = nid
            asign[it["asig"]]["ids_modelo"].append(nid)

    nuevas = {u: dict(v, materiales=sorted(v["materiales"])) for u, v in UN.nuevas.items()}
    usadas = {a["ID_ACT_ARQ"] for a in asign if a["estado"] == "ok"}
    rep["actividades_a_positivo"] = sorted(a for a in usadas if ACT[a]["rec"].get("MAT_ARQUEO") != "Positivo")
    rep["capas"] = {c: len(v) for c, v in registros.items()}
    rep["unidades_nuevas"] = len(nuevas)
    rep = {k: dict(v) if isinstance(v, collections.Counter) else v for k, v in rep.items()}
    return dict(config=cfg, modelo=M.raiz, asignaciones=asign, registros=dict(registros), unidades_nuevas=nuevas, reporte=rep)

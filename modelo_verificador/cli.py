"""Interfaz de línea de comandos.

  modelo-verificador verificar <modelo_dir> [--modulos formato,coherencia,faltantes] [--completo] [-o salida.json]
  modelo-verificador codificar <bd.xlsx> <config.json> <modelo_dir> [--bd-salida X.xlsx] [--escribir-en staging_dir] [-o asignaciones.json]
  modelo-verificador id <codigo> [--capa CERAMICAS]
  modelo-verificador dominio <capa> <campo>
"""
import argparse
import json
import sys

from . import ids as _ids, catalogo as _cat
from .verificar import verificar_todo
from .codificar import codificar, escribir_bd, escribir_modelo


def _out(obj, path=None):
    txt = json.dumps(obj, ensure_ascii=False, indent=1, default=str)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
    else:
        print(txt)


def main(argv=None):
    p = argparse.ArgumentParser(prog="modelo-verificador", description="Verificación y codificación del Modelo de Datos ICANH V4")
    sp = p.add_subparsers(dest="cmd", required=True)

    v = sp.add_parser("verificar", help="Verifica un Modelo (formato, coherencia, faltantes)")
    v.add_argument("modelo")
    v.add_argument("--modulos", default="formato,coherencia,faltantes")
    v.add_argument("--completo", action="store_true", help="Incluye la lista completa de hallazgos")
    v.add_argument("--ejemplos", type=int, default=5)
    v.add_argument("-o", "--salida")

    c = sp.add_parser("codificar", help="Lee una BD de materiales y asigna códigos del Modelo")
    c.add_argument("bd"); c.add_argument("config"); c.add_argument("modelo")
    c.add_argument("--bd-salida", help="Ruta de la «BD codificada» (.xlsx)")
    c.add_argument("--escribir-en", help="Copia de staging del Modelo donde escribir capas y unidades")
    c.add_argument("-o", "--salida", help="JSON con asignaciones y reporte")

    i = sp.add_parser("id", help="Analiza un código ID")
    i.add_argument("codigo"); i.add_argument("--capa")

    d = sp.add_parser("dominio", help="Valores de dominio de un campo según el catálogo")
    d.add_argument("capa"); d.add_argument("campo")

    w = sp.add_parser("web", help="Abre la WebApp local en el navegador (servidor en 127.0.0.1)")
    w.add_argument("--puerto", type=int, default=8765)
    w.add_argument("--no-abrir", action="store_true", help="No abrir el navegador automáticamente")

    a = p.parse_args(argv)
    if a.cmd == "web":
        from .web import main as web_main
        web_main(a.puerto, not a.no_abrir)
        return 0
    if a.cmd == "verificar":
        res = verificar_todo(a.modelo, tuple(a.modulos.split(",")), a.completo, a.ejemplos)
        _out(res, a.salida)
        if a.salida:
            print(json.dumps(dict(conteo=res["conteo"], apto=res["apto"]), ensure_ascii=False))
        return 0 if res["apto"] else 1
    if a.cmd == "codificar":
        res = codificar(a.bd, a.config, a.modelo)
        if a.bd_salida:
            escribir_bd(res, a.bd, a.bd_salida)
        if a.escribir_en:
            res["reporte"]["escritura"] = escribir_modelo(res, a.escribir_en)
        if a.salida:
            _out(dict(asignaciones=res["asignaciones"], unidades_nuevas=res["unidades_nuevas"], reporte=res["reporte"]), a.salida)
        _out(res["reporte"])
        return 0
    if a.cmd == "id":
        _out(_ids.analizar(a.codigo, capa=a.capa))
        return 0
    if a.cmd == "dominio":
        _out(_cat.cargar().dominio(a.capa, a.campo))
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""Pruebas de extremo a extremo sobre los datos sintéticos (se regeneran en una carpeta temporal)."""
import os
import json
import shutil
import importlib.util

import pytest

from modelo_verificador.verificar import verificar_todo
from modelo_verificador.codificar import codificar, escribir_bd, escribir_modelo
from modelo_verificador.texto import bytes_utf8

DS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos_sinteticos")
_sp = importlib.util.spec_from_file_location("generar", os.path.join(DS, "generar.py"))
GEN = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(GEN)


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    return GEN.construir_todo(str(tmp_path_factory.mktemp("sinteticos")))


def _hallazgos(res):
    return [(m, h["nivel"], h["capa"], h["regla"]) for m, inf in res["modulos"].items() for h in inf["hallazgos"]]


def test_modelo_minimo_sin_errores_ni_avisos(datos):
    res = verificar_todo(os.path.join(datos, "modelo_minimo"), completo=True)
    malos = [h for h in _hallazgos(res) if h[1] != "INFO"]
    assert malos == [], malos
    assert res["apto"]


def test_errores_sembrados(datos):
    esp = json.load(open(os.path.join(DS, "esperado_errores.json"), encoding="utf-8"))["mutaciones"]
    assert set(esp) == set(GEN.MUTACIONES), "cada mutación debe tener su entrada en esperado_errores.json"
    res = verificar_todo(os.path.join(datos, "modelo_con_errores"), completo=True)
    hall = set(_hallazgos(res))
    esperados = {tuple(x) for v in esp.values() for x in v}
    errores = {h for h in hall if h[1] == "ERROR"}
    assert errores == {e for e in esperados if e[1] == "ERROR"}
    faltan = {e for e in esperados if e[1] == "AVISO"} - hall
    assert not faltan, faltan
    assert not res["apto"]


@pytest.fixture(scope="module")
def codificado(datos):
    return codificar(os.path.join(datos, "bd_materiales.xlsx"), os.path.join(datos, "config.json"), os.path.join(datos, "modelo_minimo"))


def test_codificacion_por_fila(codificado):
    esp = json.load(open(os.path.join(DS, "esperado_codificacion.json"), encoding="utf-8"))
    por_id = {a["id_bd"]: a for a in codificado["asignaciones"]}
    assert set(por_id) == set(esp["filas"])               # la fila sin código se ignora
    regs = {}
    for capa, items in codificado["registros"].items():
        for it in items:
            regs[codificado["asignaciones"][it["asig"]]["id_bd"]] = it["campos"]
    for idb, e in esp["filas"].items():
        a = por_id[idb]
        assert a["estado"] == e["estado"], (idb, a["notas"])
        if e["estado"] != "ok":
            continue
        assert (a["ID_ACT_ARQ"], a["ID_UNI_EX"], a["ids_modelo"]) == (e["ID_ACT_ARQ"], e["ID_UNI_EX"], e["ids"]), idb
        assert [regs[idb]["PROFUN_INI"], regs[idb]["PROFUN_FIN"]] == e["prof"], idb
    for idb, campos in esp["campos"].items():
        for k, v in campos.items():
            if k == "_OBSERVACI_bytes_max":
                assert bytes_utf8(regs[idb]["OBSERVACI"]) <= v and regs[idb]["OBSERVACI"].endswith("…")
            else:
                assert regs[idb][k] == v, (idb, k)
    rep = codificado["reporte"]
    for k, v in esp["reporte"].items():
        assert rep[k] == v, k


def test_coordenadas_y_centroide(codificado, datos):
    me1 = next(it for it in codificado["registros"]["METALES"] if it["campos"]["ID_METALES"].endswith("PI00001M0001"))
    assert me1["xy"] == (GEN.X0 + 21.0, GEN.Y0 + 21.0)


def test_escritura_idempotente_y_valida(codificado, datos, tmp_path):
    staging = str(tmp_path / "staging")
    shutil.copytree(os.path.join(datos, "modelo_minimo"), staging)
    escribir_modelo(codificado, staging)
    salida = str(tmp_path / "BD - codificada.xlsx")
    escribir_bd(codificado, os.path.join(datos, "bd_materiales.xlsx"), salida)
    assert os.path.exists(salida)
    # segunda corrida sobre la copia ya escrita: mismos códigos, ninguna unidad nueva
    otra = codificar(os.path.join(datos, "bd_materiales.xlsx"), os.path.join(datos, "config.json"), staging)
    assert [a["ids_modelo"] for a in otra["asignaciones"]] == [a["ids_modelo"] for a in codificado["asignaciones"]]
    assert [a["ID_UNI_EX"] for a in otra["asignaciones"]] == [a["ID_UNI_EX"] for a in codificado["asignaciones"]]
    assert otra["unidades_nuevas"] == {}
    # lo escrito por el codificador es formalmente válido
    res = verificar_todo(staging, modulos=("formato",), completo=True)
    errores = [h for h in _hallazgos(res) if h[1] == "ERROR"]
    assert errores == [], errores


def test_no_escribe_sobre_el_modelo_leido(codificado, datos):
    with pytest.raises(ValueError):
        escribir_modelo(codificado, os.path.join(datos, "modelo_minimo"))

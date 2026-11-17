"""Verificación por fase del PAP (Registro / Diagnóstico / Implementación) y explicaciones de reglas."""
import pytest

from modelo_verificador.verificar import verificar_todo
from modelo_verificador.verificar.fase import normalizar
from modelo_verificador.verificar.explicaciones import explicar


def reglas(r, modulo=None):
    return {g["regla"] for g in r["grupos"] if modulo is None or g["modulo"] == modulo}


def test_registro_solo_zona_de_estudio(datos):
    r = verificar_todo(f"{datos}/modelo_con_errores", fase="registro")
    capas = {g["capa"] for g in r["grupos"]}
    assert capas <= {"POLIGONO GENERAL", "POLIGONOS ESPECIFICOS", "METADATO", "-"}
    assert r["fase_nombre"] == "Registro"
    # el polígono sintético dice «Implementación de PMA»
    assert "FASE del polígono no corresponde a la fase elegida" in reglas(r, "fase")


def test_diagnostico_marca_actividades_pi(datos):
    r = verificar_todo(f"{datos}/modelo_minimo", fase="diagnostico")
    assert "Actividad de Implementación (PI) en una entrega de Diagnóstico" in reglas(r, "fase")
    assert r["apto"]


def test_implementacion_coincide_con_todo(datos):
    a = verificar_todo(f"{datos}/modelo_con_errores", fase="implementacion")
    b = verificar_todo(f"{datos}/modelo_con_errores")
    assert a["conteo"] == b["conteo"] and not reglas(a, "fase")


def test_grupos_ordenados_y_explicados(datos):
    r = verificar_todo(f"{datos}/modelo_con_errores")
    niveles = [g["nivel"] for g in r["grupos"]]
    assert niveles == sorted(niveles, key=["ERROR", "AVISO", "INFO"].index)
    assert sum(g["n"] for g in r["grupos"]) == sum(r["conteo"].values())
    assert all(g["ayuda"] for g in r["grupos"] if g["nivel"] == "ERROR")


def test_normalizar():
    assert normalizar("Diagnóstico") == "diagnostico" and normalizar("IMPLEMENTACION") == "implementacion"
    assert normalizar(None) is None
    with pytest.raises(ValueError):
        normalizar("otra")
    assert explicar("Fuera de dominio: FASE")

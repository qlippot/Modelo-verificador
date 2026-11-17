"""Servidor MCP: herramientas vía cliente MCP en proceso, y una llamada real por stdio."""
import os
import sys
import json

import anyio
import pytest

pytest.importorskip("mcp")
from mcp import StdioServerParameters  # noqa: E402
from mcp.client.client import Client  # noqa: E402

from modelo_verificador.mcp_server import servidor  # noqa: E402
from conftest import RAIZ, DS, GEN  # noqa: E402

PE = GEN.PE


def llamar(*pasos, server=servidor):
    """Ejecuta [(herramienta, argumentos), ...] en una sola sesión y devuelve los resultados."""
    async def run():
        async with Client(server) as c:
            return [await c.call_tool(n, a) for n, a in pasos]
    return anyio.run(run)


def ok(r):
    assert not r.is_error, r.content[0].text if r.content else r
    return r.structured_content


def test_herramientas_y_anotaciones():
    async def run():
        async with Client(servidor) as c:
            return (await c.list_tools()).tools
    tools = {t.name: t for t in anyio.run(run)}
    assert set(tools) == {"verificar_modelo", "resumen_modelo", "inspeccionar_bd", "ejemplo_config", "validar_config",
                          "crear_copia_staging", "codificar_bd", "analizar_id", "generar_id", "siguiente_id",
                          "listar_capas", "campos_capa", "dominio"}
    for n in ("verificar_modelo", "resumen_modelo", "inspeccionar_bd", "validar_config", "analizar_id", "siguiente_id"):
        assert tools[n].annotations.read_only_hint is True, n
    assert tools["codificar_bd"].annotations.destructive_hint is True
    assert tools["crear_copia_staging"].annotations.read_only_hint is False
    esquema = tools["verificar_modelo"].input_schema
    assert esquema["required"] == ["ruta_modelo"] and "modulos" in esquema["properties"]
    assert "ruta_bd" in tools["codificar_bd"].input_schema["required"]


def test_verificar(datos):
    limpio, errores = llamar(("verificar_modelo", {"ruta_modelo": os.path.join(datos, "modelo_minimo")}),
                             ("verificar_modelo", {"ruta_modelo": os.path.join(datos, "modelo_con_errores"), "completo": True}))
    assert ok(limpio)["apto"] and ok(limpio)["conteo"].get("ERROR", 0) == 0
    e = ok(errores)
    esperados = json.load(open(os.path.join(DS, "esperado_errores.json"), encoding="utf-8"))["mutaciones"]
    n_err = len({tuple(x) for v in esperados.values() for x in v if x[1] == "ERROR"})
    assert not e["apto"] and e["conteo"]["ERROR"] == n_err
    assert "hallazgos" in e["modulos"]["formato"]


def test_flujo_completo_de_codificacion(datos, tmp_path):
    bd, cfg, modelo = (os.path.join(datos, x) for x in ("bd_materiales.xlsx", "config.json", "modelo_minimo"))
    staging, salida = str(tmp_path / "staging"), str(tmp_path / "BD codificada.xlsx")
    insp, val, copia, cod, ver, rechazo, repetida = llamar(
        ("inspeccionar_bd", {"ruta_bd": bd}),
        ("validar_config", {"config": cfg, "ruta_bd": bd, "ruta_modelo": modelo}),
        ("crear_copia_staging", {"ruta_modelo": modelo, "destino": staging}),
        ("codificar_bd", {"ruta_bd": bd, "config": cfg, "ruta_modelo": modelo, "ruta_bd_salida": salida, "escribir_en": staging}),
        ("verificar_modelo", {"ruta_modelo": staging, "modulos": ["formato"]}),
        ("codificar_bd", {"ruta_bd": bd, "config": cfg, "ruta_modelo": modelo, "escribir_en": modelo}),
        ("crear_copia_staging", {"ruta_modelo": modelo, "destino": staging}),
    )
    assert ok(insp)["hojas"]["Cerámica"]["encabezados"][:3] == ["Código", "Actividad", "Estrato"]
    assert ok(val) ["valida"], ok(val)["problemas"]
    assert ok(copia)["copia"] == os.path.realpath(staging)
    c = ok(cod)
    assert c["reporte"]["filas"] == {"ok": 12, "sin_resolver": 2}
    assert os.path.exists(salida) and c["escritura"]["CERAMICAS"]["nuevos"] == 7
    assert {a["id_bd"]: a["ids_modelo"] for a in c["asignaciones"]}["OS-002"] == [f"{PE}PI00002OA0002"]
    assert ok(ver)["apto"]
    assert rechazo.is_error and "copia separada" in rechazo.content[0].text
    assert repetida.is_error and "ya existe" in repetida.content[0].text


def test_config_en_linea_y_problemas(datos):
    cfg = json.load(open(os.path.join(datos, "config.json"), encoding="utf-8"))
    cfg["hojas"]["Metales"]["campos"]["NO_EXISTE"] = "Tipo"
    cfg["hojas"]["Óseos"]["estrato"] = "Columna fantasma"
    cfg["actividades"]["exactas"]["Corte 99"] = f"{PE}PI00099"
    (r,) = llamar(("validar_config", {"config": cfg, "ruta_bd": os.path.join(datos, "bd_materiales.xlsx"),
                                      "ruta_modelo": os.path.join(datos, "modelo_minimo")}))
    v = ok(r)
    assert not v["valida"]
    txt = " | ".join(v["problemas"])
    assert "NO_EXISTE" in txt and "Columna fantasma" in txt and "PI00099" in txt
    (malo,) = llamar(("validar_config", {"config": {"modo": "otro"}}))
    assert ok(malo)["valida"] is False


def test_ids(datos):
    m = os.path.join(datos, "modelo_minimo")
    act, uni, cer, gen, ana, dom, err = llamar(
        ("siguiente_id", {"ruta_modelo": m, "tipo": "actividad", "base": PE}),
        ("siguiente_id", {"ruta_modelo": m, "tipo": "unidad", "base": PE}),
        ("siguiente_id", {"ruta_modelo": m, "tipo": "material", "base": f"{PE}PI00001", "capa": "Cerámicas"}),
        ("generar_id", {"tipo": "material", "base": f"{PE}PI00003", "numero": 12, "capa": "OSEOS ANIMALES"}),
        ("analizar_id", {"codigo": f"{PE}PI0001C0001"}),
        ("dominio", {"capa": "ESTRUCTURAS", "campo": "TIPO_OBJEC"}),
        ("dominio", {"capa": "ESTRUCTURAS", "campo": "DESCRIPCIO"}),
    )
    assert ok(act)["siguiente"] == f"{PE}PI00007"
    assert ok(uni)["siguiente"] == f"{PE}NP0008"
    assert ok(cer)["siguiente"] == f"{PE}PI00001C0003"
    assert ok(gen)["codigo"] == f"{PE}PI00003OA0012" and ok(gen)["valido"]
    assert ok(ana)["valido"] is False
    assert "Muros" in ok(dom)["valores"]
    assert err.is_error and "no tiene dominio" in err.content[0].text


def test_raiz_permitida(datos, monkeypatch, tmp_path):
    monkeypatch.setenv("MODELO_VERIFICADOR_RAIZ", str(tmp_path))
    (r,) = llamar(("verificar_modelo", {"ruta_modelo": os.path.join(datos, "modelo_minimo")}))
    assert r.is_error and "fuera de la carpeta permitida" in r.content[0].text


def test_stdio_real():
    params = StdioServerParameters(command=sys.executable, args=["-m", "modelo_verificador.mcp_server"],
                                   env={"PYTHONPATH": RAIZ})

    async def run():
        async with Client(params) as c:
            return await c.call_tool("analizar_id", {"codigo": "R0125A220005DI00001OBC0001"})
    r = anyio.run(run)
    assert ok(r)["capa"] == "OBJETOS COMPUESTOS"

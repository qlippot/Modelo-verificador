"""WebApp: servidor local (subida, servicios, descargas, protecciones) y construcción de la versión en navegador."""
import io
import os
import json
import base64
import zipfile
import threading
import urllib.request
import urllib.error

import pytest

from modelo_verificador import servicios
from modelo_verificador.web import crear_servidor
from conftest import RAIZ


@pytest.fixture()
def srv(tmp_path):
    s = crear_servidor(puerto=0, sesion=str(tmp_path / "sesion"))
    os.makedirs(s.sesion, exist_ok=True)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def pedir(s, metodo, ruta, cuerpo=None, token=True, host=None, tipo=None):
    url = f"http://127.0.0.1:{s.server_address[1]}{ruta}"
    req = urllib.request.Request(url, data=cuerpo, method=metodo)
    if token:
        req.add_header("X-MV-Token", s.token)
    if host:
        req.add_header("Host", host)
    if tipo:
        req.add_header("Content-Type", tipo)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def llamar(s, nombre, **args):
    st, b = pedir(s, "POST", "/api/llamar", json.dumps({"nombre": nombre, "argumentos": args}).encode(), tipo="application/json")
    assert st == 200
    return json.loads(b)


def test_pagina_con_token(srv):
    st, html = pedir(srv, "GET", "/", token=False)
    assert st == 200 and srv.token.encode() in html and b'"modo": "local"' in html


def test_subir_modelo_y_verificar(srv, datos):
    origen = os.path.join(datos, "modelo_minimo")
    for d, _, fs in os.walk(origen):
        for f in fs:
            p = os.path.join(d, f)
            rel = "modelo/" + os.path.relpath(p, origen).replace(os.sep, "/")
            st, _ = pedir(srv, "PUT", "/api/archivo?ruta=" + urllib.request.quote(rel), open(p, "rb").read())
            assert st == 204, rel
    r = llamar(srv, "verificar_modelo", ruta_modelo="modelo")
    assert r["ok"] and r["resultado"]["apto"] and r["resultado"]["modelo"] == "modelo"


def test_codificar_y_descargar(srv):
    assert llamar(srv, "cargar_ejemplo")["ok"]
    cfg = json.load(open(os.path.join(srv.sesion, "ejemplo", "config.json"), encoding="utf-8"))
    assert llamar(srv, "crear_copia_staging", ruta_modelo="ejemplo/modelo_minimo", destino="salidas/copia")["ok"]
    r = llamar(srv, "codificar_bd", ruta_bd="ejemplo/bd_materiales.xlsx", config=cfg, ruta_modelo="ejemplo/modelo_minimo",
               ruta_bd_salida="salidas/bd.xlsx", escribir_en="salidas/copia")
    assert r["ok"] and r["resultado"]["reporte"]["filas"]["ok"] == 12 and r["resultado"]["bd_codificada"] == "salidas/bd.xlsx"
    assert llamar(srv, "empaquetar", carpeta="salidas/copia", destino_zip="salidas/copia.zip")["ok"]
    st, z = pedir(srv, "GET", "/api/archivo?ruta=salidas/copia.zip")
    assert st == 200 and any(n.endswith("CERAMICAS.shp") for n in zipfile.ZipFile(io.BytesIO(z)).namelist())


def test_protecciones(srv):
    assert pedir(srv, "POST", "/api/llamar", b"{}", token=False, tipo="application/json")[0] == 403
    assert pedir(srv, "GET", "/api/archivo?ruta=x", host="evil.example")[0] == 403
    assert pedir(srv, "GET", "/api/archivo?ruta=../../etc/passwd")[0] == 400
    assert pedir(srv, "PUT", "/api/archivo?ruta=../fuera.txt", b"x")[0] == 400
    assert pedir(srv, "POST", "/api/llamar", b"{}")[0] == 415
    assert llamar(srv, "os.system")["ok"] is False
    r = llamar(srv, "verificar_modelo", ruta_modelo="/etc")
    assert not r["ok"] and "fuera de la sesión" in r["error"]
    assert "fuera de la sesión" in llamar(srv, "borrar", ruta="../x")["error"]
    assert not llamar(srv, "borrar", ruta=".")["ok"]


def test_borrar_fuera_de_sesion_no_permitido():
    with pytest.raises(ValueError):
        servicios.borrar("algo")


def test_construir_navegador(tmp_path):
    import importlib.util
    sp = importlib.util.spec_from_file_location("construir", os.path.join(RAIZ, "web", "construir_navegador.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    salida, _, _ = m.construir(str(tmp_path / "mv.html"))
    html = open(salida, encoding="utf-8").read()
    assert '"modo": "navegador"' in html and "/*MV_PAQUETE*/" not in html and "pyodide/v0.28.3" in html
    b64 = html.split('id="mv-paquete">', 1)[1].split("</script>", 1)[0]
    nombres = zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))).namelist()
    assert "modelo_verificador/servicios.py" in nombres and "modelo_verificador/mcp_server.py" not in nombres
    assert any(n.startswith("referencia/plantillas_V4/") for n in nombres)
    assert "datos_sinteticos/config.json" in nombres

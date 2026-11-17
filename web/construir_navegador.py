"""Construye la versión «en navegador»: un único .html autocontenido que ejecuta el paquete con Pyodide.

Uso:  python web/construir_navegador.py [salida.html]      (por defecto web/dist/modelo-verificador.html)

Incrusta (zip en base64): el paquete modelo_verificador (.py), referencia/ (catálogo y plantillas V4),
ejemplos/config_codificacion.ejemplo.json y los datos sintéticos. Pyodide y sus paquetes se descargan del CDN
en la primera apertura; los datos del usuario no salen del navegador.
"""
import io
import os
import sys
import json
import base64
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/"
INCLUIR = [
    ("modelo_verificador", lambda f: f.endswith(".py") and f != "mcp_server.py" and f != "web.py"),
    ("referencia", lambda f: f != ".DS_Store"),
    ("ejemplos", lambda f: f == "config_codificacion.ejemplo.json"),
    ("datos_sinteticos/modelo_minimo", lambda f: f != ".DS_Store"),
    ("datos_sinteticos/modelo_con_errores", lambda f: f != ".DS_Store"),
]
SUELTOS = ["datos_sinteticos/bd_materiales.xlsx", "datos_sinteticos/config.json"]


def paquete():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for carpeta, filtro in INCLUIR:
            for d, ds, fs in os.walk(os.path.join(RAIZ, carpeta)):
                ds[:] = [x for x in ds if x != "__pycache__"]
                for f in sorted(fs):
                    if filtro(f):
                        p = os.path.join(d, f)
                        z.write(p, os.path.relpath(p, RAIZ))
        for p in SUELTOS:
            z.write(os.path.join(RAIZ, p), p)
    return buf.getvalue()


def construir(salida=None):
    salida = salida or os.path.join(RAIZ, "web", "dist", "modelo-verificador.html")
    with open(os.path.join(RAIZ, "web", "plantilla.html"), encoding="utf-8") as f:
        html = f.read()
    z = paquete()
    cfg = "window.MV = " + json.dumps({"modo": "navegador", "pyodide": PYODIDE}) + ";"
    html = html.replace("/*MV_CONFIG*/", cfg, 1).replace("/*MV_PAQUETE*/", base64.b64encode(z).decode("ascii"), 1)
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(html)
    return salida, len(z), len(html.encode("utf-8"))


if __name__ == "__main__":
    s, nz, nh = construir(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"{s}  (paquete {nz / 1e6:.2f} MB, html {nh / 1e6:.2f} MB)")

"""WebApp local: servidor HTTP mínimo (biblioteca estándar) que sirve web/plantilla.html y ejecuta los servicios.

    modelo-verificador web [--puerto 8765] [--no-abrir]

Seguridad: escucha solo en 127.0.0.1; cada petición a /api exige el token aleatorio de esta ejecución (cabecera
X-MV-Token) y un Host local; los archivos viven en una carpeta de sesión temporal que se borra al salir, y ninguna
ruta puede salir de ella.
"""
import os
import json
import shutil
import secrets
import tempfile
import threading
import webbrowser
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from . import servicios

PLANTILLA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "plantilla.html")
MAX_SUBIDA = 512 * 1024 * 1024   # 512 MB por archivo


def pagina(token):
    with open(PLANTILLA, encoding="utf-8") as f:
        html = f.read()
    cfg = "window.MV = " + json.dumps({"modo": "local", "token": token}) + ";"
    return html.replace("/*MV_CONFIG*/", cfg, 1).encode("utf-8")


def crear_servidor(puerto=8765, sesion=None):
    token = secrets.token_urlsafe(24)
    sesion = os.path.realpath(sesion or tempfile.mkdtemp(prefix="modelo-verificador-"))
    candado = threading.Lock()       # los servicios usan un estado global de sesión: una llamada a la vez

    class Manejador(BaseHTTPRequestHandler):
        server_version = "ModeloVerificador"

        def log_message(self, fmt, *a):   # silencioso salvo errores
            pass

        def _responder(self, codigo, cuerpo=b"", tipo="text/plain; charset=utf-8", extra=None):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def _autorizado(self):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in ("127.0.0.1", "localhost"):
                self._responder(403, b"Host no permitido")
                return False
            if not secrets.compare_digest(self.headers.get("X-MV-Token", ""), token):
                self._responder(403, b"Token invalido")
                return False
            return True

        def _ruta_sesion(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rel = (q.get("ruta") or [""])[0]
            with servicios.en_base(sesion):
                return servicios._ruta(rel, existe=False)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._responder(200, pagina(token), "text/html; charset=utf-8",
                                       {"Content-Security-Policy": "default-src 'self' 'unsafe-inline' blob:; img-src 'self' data:"})
            if u.path == "/api/archivo":
                if not self._autorizado():
                    return
                try:
                    p = self._ruta_sesion()
                except ValueError as e:
                    return self._responder(400, str(e).encode())
                if not os.path.isfile(p):
                    return self._responder(404, b"No existe")
                with open(p, "rb") as f:
                    datos = f.read()
                nombre = urllib.parse.quote(os.path.basename(p))
                return self._responder(200, datos, "application/octet-stream",
                                       {"Content-Disposition": f"attachment; filename*=UTF-8''{nombre}"})
            self._responder(404, b"No encontrado")

        def do_PUT(self):
            if urllib.parse.urlparse(self.path).path != "/api/archivo":
                return self._responder(404, b"No encontrado")
            if not self._autorizado():
                return
            n =int(self.headers.get("Content-Length") or 0)
            if n > MAX_SUBIDA:
                return self._responder(413, b"Archivo demasiado grande")
            try:
                p = self._ruta_sesion()
            except ValueError as e:
                return self._responder(400, str(e).encode())
            if p == sesion:
                return self._responder(400, b"Ruta invalida")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                restante = n
                while restante:
                    trozo = self.rfile.read(min(restante, 1 << 20))
                    if not trozo:
                        break
                    f.write(trozo)
                    restante -= len(trozo)
            self._responder(204)

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/api/llamar":
                return self._responder(404, b"No encontrado")
            if not self._autorizado():
                return
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._responder(415, b"Se espera JSON")
            try:
                pet = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except json.JSONDecodeError:
                return self._responder(400, b"JSON invalido")
            with candado:
                res = servicios.llamar(pet.get("nombre"), pet.get("argumentos") or {}, sesion)
            self._responder(200, json.dumps(res, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    srv = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    srv.sesion, srv.token = sesion, token
    return srv


def main(puerto=8765, abrir=True):
    srv = crear_servidor(puerto)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Modelo-verificador en {url}  (Ctrl+C para salir)")
    if abrir:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        shutil.rmtree(srv.sesion, ignore_errors=True)
        print("Sesión cerrada; archivos temporales borrados.")

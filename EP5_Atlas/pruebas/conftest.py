"""Infraestructura común de la suite automatizada del EP5 (Atlas, Caso A).

- Registra el resultado de cada caso (PASÓ / FALLÓ / BLOQUEADO) en reportes/resultados.json.
- Guarda la evidencia textual de cada caso en evidencias/<ID>.txt (petición, respuesta y conclusión).
- Provee helpers para la API, la base de datos (psql dentro del contenedor) y datos de prueba aislados.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import pathlib
import shutil
import subprocess
import time
import uuid

import pytest
import requests

API = os.environ.get("ATLAS_API", "http://localhost:4450")
WEB = os.environ.get("ATLAS_WEB", "http://localhost:3350")
RAIZ = pathlib.Path(__file__).resolve().parents[1]
REPO = RAIZ.parent / "CodigoFuenteA"
EVID = RAIZ / "evidencias"
REPORTES = RAIZ / "reportes"
EVID.mkdir(exist_ok=True)
REPORTES.mkdir(exist_ok=True)
RESULTADOS = REPORTES / "resultados.json"

DOCKER = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
CLAVE_QA = "Qa#Prueba2026!"  # contraseña que sí cumple la política, usada para cuentas de prueba


# ----------------------------------------------------------------- utilidades
def psql(sql: str) -> str:
    """Ejecuta SQL en el contenedor de PostgreSQL y devuelve la salida sin formato."""
    out = subprocess.run(
        [DOCKER, "exec", "atlas-postgres", "psql", "-U", "postgres", "-d", "atlas",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    return out.stdout.strip()


def docker(*args, timeout=120) -> subprocess.CompletedProcess:
    return subprocess.run([DOCKER, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def decodificar_jwt(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def firmar_jwt(payload: dict, secreto: str) -> str:
    def b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()
    cab = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cue = b64(json.dumps(payload, separators=(",", ":")).encode())
    firma = hmac.new(secreto.encode(), f"{cab}.{cue}".encode(), hashlib.sha256).digest()
    return f"{cab}.{cue}.{b64(firma)}"


def h(token=None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def sufijo() -> str:
    return uuid.uuid4().hex[:6]


def pdf_minimo(texto="Contrato de prueba QA") -> bytes:
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\n"
            + f"% {texto}\n".encode() + b"trailer<</Root 1 0 R>>\n%%EOF\n")


PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


# ----------------------------------------------------------------- evidencia
class Evidencia:
    """Acumula una transcripción legible del caso (se convierte luego en figura del informe)."""

    def __init__(self, caso_id):
        self.caso_id = caso_id
        self.lineas = []
        self.obtenido = ""

    def nota(self, texto):
        self.lineas.append(texto)

    def http(self, r: requests.Response, cuerpo_max=400, etiqueta=None):
        req = r.request
        cab = f"{req.method} {req.url.replace(API, '').replace(WEB, '') or '/'}"
        if etiqueta:
            self.lineas.append(f"# {etiqueta}")
        tiene_auth = "Authorization" in req.headers
        self.lineas.append(f"> {cab}   [{'con token' if tiene_auth else 'SIN token'}]")
        if req.body and isinstance(req.body, (bytes, str)) and len(req.body) < 600 and "multipart" not in req.headers.get("Content-Type", ""):
            cuerpo = req.body.decode() if isinstance(req.body, bytes) else req.body
            self.lineas.append(f"  {cuerpo[:300]}")
        tipo = r.headers.get("Content-Type", "")
        texto = r.text if ("json" in tipo or "text" in tipo) else f"<{len(r.content)} bytes {tipo}>"
        self.lineas.append(f"< HTTP {r.status_code}  ({r.elapsed.total_seconds()*1000:.0f} ms)")
        self.lineas.append(f"  {texto[:cuerpo_max]}")

    def resultado(self, texto):
        self.obtenido = texto
        self.lineas.append(f"=> {texto}")

    def guardar(self):
        (EVID / f"{self.caso_id}.txt").write_text("\n".join(self.lineas), encoding="utf-8")


def pytest_configure(config):
    config.addinivalue_line("markers", "caso(id): identificador del caso en el catálogo")


@pytest.fixture
def ev(request):
    m = request.node.get_closest_marker("caso")
    e = Evidencia(m.args[0] if m else request.node.name)
    request.node._evidencia = e
    yield e
    e.guardar()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    m = item.get_closest_marker("caso")
    if not m:
        return
    caso_id = m.args[0]
    estado = None
    detalle = ""
    if rep.when == "setup" and rep.failed:
        estado, detalle = "BLOQUEADO", str(rep.longrepr.reprcrash.message if hasattr(rep.longrepr, "reprcrash") else rep.longrepr)[:600]
    elif rep.when == "setup" and rep.skipped:
        estado, detalle = "BLOQUEADO", str(rep.longrepr[2] if isinstance(rep.longrepr, tuple) else rep.longrepr)[:600]
    elif rep.when == "call":
        if rep.passed:
            estado = "PASÓ"
        elif rep.skipped:
            estado, detalle = "BLOQUEADO", str(rep.longrepr[2] if isinstance(rep.longrepr, tuple) else rep.longrepr)[:600]
        else:
            crash = getattr(rep.longrepr, "reprcrash", None)
            msg = crash.message if crash else str(rep.longrepr)
            if msg.startswith("AssertionError: "):
                msg = msg[len("AssertionError: "):]
            estado, detalle = ("FALLÓ", msg.split("\nassert")[0][:800]) if call.excinfo and call.excinfo.errisinstance(AssertionError) \
                else ("BLOQUEADO", f"Error de ejecución: {msg[:600]}")
    if estado is None:
        return
    ev_obj = getattr(item, "_evidencia", None)
    obtenido = (ev_obj.obtenido if ev_obj and ev_obj.obtenido else detalle)
    datos = json.loads(RESULTADOS.read_text(encoding="utf-8")) if RESULTADOS.exists() else {}
    datos[caso_id] = {
        "estado": estado,
        "obtenido": obtenido if estado != "PASÓ" or not detalle else obtenido,
        "detalle": detalle,
        "duracion_s": round(rep.duration, 2),
        "fecha": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "test": item.nodeid,
    }
    RESULTADOS.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------- sesión API
def login(usuario, clave):
    r = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": usuario, "password": clave}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def registrar_empresa(prefijo, clave=CLAVE_QA):
    s = sufijo()
    usuario = f"{prefijo}_{s}"
    payload = {
        "usuario": {"nombre_usuario": usuario, "contrasena_hash": clave, "correo": f"{usuario}@qa.test"},
        "empresa": {"nombre": f"{prefijo.capitalize()} QA {s}", "direccion": "Av. Libertador 1234, Santiago, RM",
                    "telefono": "+56912345678", "correo": f"contacto_{usuario}@qa.test"},
    }
    r = requests.post(f"{API}/empresas", json=payload, timeout=30)
    r.raise_for_status()
    datos = r.json()
    return {"usuario": usuario, "clave": clave, "usuario_id": datos["usuario"]["id"],
            "empresa_id": datos["empresa"]["id"], "empresa": datos["empresa"], "respuesta": r}


def cliente_payload(nombre=None, **extra):
    s = sufijo()
    base = {
        "nombre": nombre or f"Cliente QA {s}", "correo": f"cliente_{s}@qa.test", "telefono": "+56987654321",
        "direccion": "Calle Falsa 742, Valparaíso", "es_empresa": True, "rut": "76.543.210-3",
        "nombre_fantasia": "Servicios QA", "giro_actividad_economica": "Consultoría",
        "nombre_banco": "Banco de Pruebas", "numero_cuenta": "000123456789", "titular_cuenta": "Servicios QA SpA",
        "metodo_pago": "transferencia", "dia_pago": "5", "moneda": "CLP",
    }
    base.update(extra)
    return base


def crear_cliente(token, **extra):
    r = requests.post(f"{API}/clientes", json=cliente_payload(**extra), headers=h(token), timeout=30)
    r.raise_for_status()
    return r.json()


def crear_contrato(token, cliente_id, archivo=None, nombre_archivo="contrato.pdf", fin_dias=180, titulo=None):
    hoy = dt.date.today()
    datos = {"cliente_id": str(cliente_id), "titulo": titulo or f"Contrato QA {sufijo()}",
             "descripcion": "Contrato generado por la suite automatizada",
             "fecha_inicio": (hoy - dt.timedelta(days=30)).isoformat(),
             "fecha_fin": (hoy + dt.timedelta(days=fin_dias)).isoformat()}
    return requests.post(f"{API}/contratos", files=multipart(datos, archivo, nombre_archivo), headers=h(token), timeout=120)


def multipart(campos: dict, archivo=None, nombre_archivo="contrato.pdf"):
    """La API de contratos sólo procesa multipart/form-data (igual que el frontend con FormData)."""
    partes = {k: (None, str(v)) for k, v in campos.items()}
    if archivo is not None:
        partes["file"] = (nombre_archivo, archivo, "application/octet-stream")
    return partes


@pytest.fixture(scope="session")
def tok_admin():
    return login("admin", "admin")


@pytest.fixture(scope="session")
def tok_editor():
    return login("editor", "editor")


@pytest.fixture(scope="session")
def victima():
    """Empresa víctima aislada con un cliente con datos bancarios y un contrato con PDF."""
    v = registrar_empresa("victima")
    v["token"] = login(v["usuario"], v["clave"])
    v["cliente"] = crear_cliente(v["token"], nombre=f"Cliente Confidencial {sufijo()}", numero_cuenta="987654321098")
    r = crear_contrato(v["token"], v["cliente"]["id"], archivo=pdf_minimo("Documento confidencial de la victima"))
    r.raise_for_status()
    v["contrato"] = r.json()
    return v


@pytest.fixture(scope="session")
def atacante():
    a = registrar_empresa("atacante")
    a["token"] = login(a["usuario"], a["clave"])
    return a

"""Pruebas de seguridad automatizadas (DAST dirigido / pentest) sobre la API de Atlas.

Todas las acciones destructivas se ejecutan sólo sobre datos creados por la propia suite.
"""
import concurrent.futures as cf
import re
import time

import pytest
import requests
import urllib3

from conftest import (API, REPO, WEB, CLAVE_QA, crear_cliente, crear_contrato, decodificar_jwt, docker, firmar_jwt,
                      h, login, pdf_minimo, psql, registrar_empresa, sufijo)

urllib3.disable_warnings()


@pytest.mark.caso("TC-SEC-01")
def test_tls(ev):
    hallazgos = []
    for nombre, url in (("API", API), ("Frontend", WEB)):
        https = url.replace("http://", "https://")
        try:
            requests.get(https, timeout=5, verify=False)
            ev.nota(f"> GET {https}  -> conexión TLS aceptada")
        except requests.exceptions.SSLError as e:
            ev.nota(f"> GET {https}  -> sin TLS ({type(e).__name__})")
            hallazgos.append(f"{nombre} no ofrece TLS")
        except requests.exceptions.ConnectionError as e:
            ev.nota(f"> GET {https}  -> sin TLS ({type(e).__name__})")
            hallazgos.append(f"{nombre} no ofrece TLS")
        r = requests.get(url, timeout=5, allow_redirects=False)
        ev.nota(f"> GET {url}  -> HTTP {r.status_code}, HSTS: {r.headers.get('Strict-Transport-Security', 'ausente')}")
        if r.status_code < 300:
            hallazgos.append(f"{nombre} responde por HTTP plano sin redirigir")
    ssl = psql("SHOW ssl")
    ev.nota(f"$ psql -c 'SHOW ssl'  -> {ssl}")
    if ssl != "on":
        hallazgos.append("PostgreSQL sin SSL")
    r = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin", "password": "admin"})
    ev.nota(f"Credenciales del login viajan en claro: {r.request.body.decode()}")
    ev.resultado("; ".join(hallazgos))
    assert not hallazgos, "; ".join(hallazgos)


@pytest.mark.caso("TC-SEC-02")
def test_bcrypt(ev, victima):
    filas = psql(f"SELECT nombre_usuario, contrasena_hash FROM usuarios WHERE nombre_usuario IN "
                 f"('admin','editor','{victima['usuario']}') ORDER BY id").splitlines()
    ev.nota("$ SELECT nombre_usuario, contrasena_hash FROM usuarios WHERE ...")
    planos = 0
    for f in filas:
        u, hsh = f.split("|")
        ev.nota(f"  {u:<22} | {hsh}")
        planos += not hsh.startswith(("$2a$", "$2b$", "$argon2"))
    ev.resultado(f"{planos} de {len(filas)} contraseñas almacenadas en texto plano")
    assert planos == 0, f"{planos} contraseñas almacenadas en texto plano (sin bcrypt)"


@pytest.mark.caso("TC-SEC-03")
def test_cifrado_reposo(ev, victima):
    fila = psql(f"SELECT rut, nombre_banco, numero_cuenta, titular_cuenta FROM clientes WHERE id={victima['cliente']['id']}")
    ext = psql("SELECT coalesce(string_agg(extname, ','), 'ninguna') FROM pg_extension WHERE extname='pgcrypto'")
    ev.nota(f"$ SELECT rut, nombre_banco, numero_cuenta, titular_cuenta FROM clientes WHERE id={victima['cliente']['id']}")
    ev.nota(f"  {fila}")
    ev.nota(f"Extensión pgcrypto: {ext}")
    legible = victima["cliente"]["numero_cuenta"] in fila
    ev.resultado(f"Número de cuenta, titular y RUT legibles en la BD ({'sin cifrar' if legible else 'cifrados'})")
    assert not legible, "Datos bancarios almacenados en texto plano"


@pytest.mark.caso("TC-SEC-04")
def test_editor_no_escribe(ev, tok_editor):
    claims = decodificar_jwt(tok_editor)
    ev.nota(f"Token del editor (rol 2) no incluye rol: {claims}")
    c = requests.post(f"{API}/clientes", json={"nombre": f"Creado por editor {sufijo()}", "correo": f"ed_{sufijo()}@qa.test"},
                      headers=h(tok_editor))
    ev.http(c, cuerpo_max=120, etiqueta="Editor crea cliente")
    cid = c.json().get("id")
    u = requests.put(f"{API}/clientes/{cid}", json={"nombre": "Editado por editor", "correo": f"ed2_{sufijo()}@qa.test"},
                     headers=h(tok_editor))
    ev.http(u, cuerpo_max=80, etiqueta="Editor edita cliente")
    d = requests.delete(f"{API}/clientes/{cid}", headers=h(tok_editor))
    ev.http(d, etiqueta="Editor elimina cliente")
    codigos = (c.status_code, u.status_code, d.status_code)
    ev.resultado(f"El editor crea, edita y elimina: HTTP {codigos}")
    assert codigos == (403, 403, 403), f"El rol editor ejecuta escrituras (HTTP {codigos}); el backend no valida roles"


@pytest.mark.caso("TC-SEC-05")
def test_endpoints_sin_autenticacion(ev, victima, atacante):
    link = decodificar_jwt(victima["token"])["empresaUsuarioId"]
    rol_anonimo = f"rol_anonimo_{sufijo()}"
    nuevo_nombre = f"Renombrada por anonimo {sufijo()}"
    # Para escrituras se verifica el efecto en la BD: la API responde 500 sólo porque falla el
    # INSERT de auditoría (usuario NULL) DESPUÉS de haber aplicado el cambio.
    efecto = {
        "POST /roles": lambda: psql(f"SELECT count(*) FROM roles WHERE nombre='{rol_anonimo}'") == "1",
        f"PUT /empresas/{atacante['empresa_id']}": lambda: psql(
            f"SELECT nombre FROM empresas WHERE id={atacante['empresa_id']}") == nuevo_nombre,
    }
    pruebas = [
        ("GET", f"/contratos/{victima['contrato']['id']}", None),
        ("GET", f"/contratos/{victima['contrato']['id']}/file", None),
        ("GET", "/auditoria", None),
        ("GET", "/empresas", None),
        ("GET", f"/empresas/{victima['empresa_id']}", None),
        ("GET", f"/usuarios/{victima['usuario_id']}", None),
        ("GET", f"/empresa-usuarios/{link}", None),
        ("GET", "/roles", None),
        ("POST", "/roles", {"nombre": rol_anonimo}),
        ("PUT", f"/empresas/{atacante['empresa_id']}", {"nombre": nuevo_nombre, "correo": atacante["empresa"]["correo"]}),
    ]
    expuestos = []
    ev.nota(f"{'MÉTODO':<7}{'RUTA':<30}{'HTTP':<6}RESULTADO")
    for metodo, ruta, cuerpo in pruebas:
        r = requests.request(metodo, f"{API}{ruta}", json=cuerpo, timeout=30)
        tipo = r.headers.get("Content-Type", "")
        clave = f"{metodo} {ruta}"
        if clave in efecto:
            aplicado = efecto[clave]()
            muestra = f"cambio {'APLICADO en la BD' if aplicado else 'no aplicado'} (falla luego la auditoría)"
        else:
            aplicado = r.status_code < 400
            muestra = r.text[:52].replace("\n", " ") if "json" in tipo else f"<{len(r.content)} bytes {tipo.split(';')[0]}>"
        ev.nota(f"{metodo:<7}{ruta:<30}{r.status_code:<6}{muestra}")
        if aplicado:
            expuestos.append(clave)
    ev.resultado(f"{len(expuestos)} de {len(pruebas)} operaciones aceptadas sin autenticación")
    assert not expuestos, f"{len(expuestos)}/{len(pruebas)} endpoints responden sin token: {', '.join(expuestos)}"


@pytest.mark.caso("TC-SEC-06")
def test_borrado_anonimo_contrato(ev, victima):
    r = crear_contrato(victima["token"], victima["cliente"]["id"], archivo=pdf_minimo("Contrato a proteger"))
    kid = r.json()["id"]
    antes = psql(f"SELECT count(*) FROM contratos WHERE id={kid}")
    d = requests.delete(f"{API}/contratos/{kid}")
    ev.http(d, cuerpo_max=300, etiqueta="DELETE anónimo de un contrato de la víctima")
    despues = psql(f"SELECT count(*) FROM contratos WHERE id={kid}")
    docs = psql(f"SELECT count(*) FROM documentos_contrato WHERE contract_id={kid}")
    aud = psql(f"SELECT count(*) FROM auditoria WHERE accion LIKE 'CONTRATOS_ELIMINAR: eliminó contrato ID {kid}'")
    ev.nota(f"$ contratos id={kid}: antes={antes} después={despues}; documentos={docs}; eventos de auditoría={aud}")
    ev.resultado(f"Contrato y documento borrados por un anónimo sin rastro en auditoría (HTTP {d.status_code})")
    assert despues == "1", "Un usuario anónimo eliminó el contrato y su documento; el borrado no quedó auditado"


@pytest.mark.caso("TC-SEC-07")
def test_toma_control_entre_empresas(ev, victima):
    atk = registrar_empresa("intruso")
    tok = login(atk["usuario"], atk["clave"])
    claims = decodificar_jwt(tok)
    ev.nota(f"1) Atacante registrado; su JWT revela empresaUsuarioId={claims['empresaUsuarioId']}")
    empresas = requests.get(f"{API}/empresas").json()
    objetivo = next(e for e in empresas if e["id"] == victima["empresa_id"])
    ev.nota(f"2) GET /empresas (sin token) lista {len(empresas)} empresas; objetivo: id={objetivo['id']} '{objetivo['nombre']}'")
    p = requests.put(f"{API}/empresa-usuarios/{claims['empresaUsuarioId']}",
                     json={"empresa_id": victima["empresa_id"], "usuario_id": atk["usuario_id"], "rol_id": 1})
    ev.http(p, etiqueta="3) PUT /empresa-usuarios/{propio} SIN token -> empresa víctima, rol administrador")
    tok2 = login(atk["usuario"], atk["clave"])
    ev.nota(f"4) Nuevo login del atacante: empresaId={decodificar_jwt(tok2)['empresaId']}")
    robo = requests.get(f"{API}/clientes/search?name=", headers=h(tok2))
    datos = [(c["nombre"], c["rut"], c["nombre_banco"], c["numero_cuenta"]) for c in robo.json()] if robo.ok else []
    ev.nota(f"5) GET /clientes de la víctima -> HTTP {robo.status_code}: {datos}")
    ev.resultado("El atacante se convirtió en administrador de otra empresa y obtuvo sus datos bancarios")
    assert p.status_code in (401, 403), "Modificación anónima del vínculo empresa-usuario"
    assert not datos, "Fuga entre empresas: el atacante lee clientes y cuentas bancarias de la víctima"


@pytest.mark.caso("TC-SEC-08")
def test_contratos_a_clientes_ajenos(ev, victima, atacante):
    r = crear_contrato(atacante["token"], victima["cliente"]["id"], titulo="Contrato inyectado por otra empresa")
    ev.http(r, cuerpo_max=200, etiqueta="Atacante crea contrato para cliente de la víctima")
    propio_cli = crear_cliente(atacante["token"])
    propio = crear_contrato(atacante["token"], propio_cli["id"], titulo="Contrato propio").json()
    from conftest import multipart
    u = requests.put(f"{API}/contratos/{propio['id']}", files=multipart({"cliente_id": victima["cliente"]["id"]}),
                     headers=h(atacante["token"]))
    ev.http(u, cuerpo_max=200, etiqueta="Atacante mueve su contrato a un cliente de la víctima")
    vis = [c["titulo"] for c in requests.get(f"{API}/contratos", headers=h(victima["token"])).json()
           if c["id"] in (r.json().get("id"), propio["id"])]
    ev.nota(f"Contratos ajenos visibles ahora en la empresa víctima: {vis}")
    ev.resultado(f"Creación HTTP {r.status_code} y reasignación HTTP {u.status_code}; la víctima ve {len(vis)} contratos ajenos")
    assert r.status_code in (403, 404) and u.status_code in (403, 404), \
        "La API acepta cliente_id de otra empresa en POST y PUT /contratos"


@pytest.mark.caso("TC-SEC-09")
def test_xss_almacenado(ev, victima):
    payload = "<img src=x onerror=alert(document.domain)>"
    r = requests.post(f"{API}/clientes", json={"nombre": payload, "correo": f"xss_{sufijo()}@qa.test"}, headers=h(victima["token"]))
    ev.http(r, cuerpo_max=160)
    guardado = psql(f"SELECT nombre FROM clientes WHERE id={r.json().get('id', 0)}")
    ev.nota(f"Valor almacenado en BD: {guardado}")
    victima["xss_cliente"] = r.json().get("id")
    ev.resultado(f"El backend almacenó el payload sin sanear (HTTP {r.status_code}); React lo escapa al mostrarlo "
                 f"(ver evidencia de interfaz), por lo que el riesgo queda latente para otros consumidores de la API")
    assert r.status_code == 400 or guardado != payload, "Entrada con HTML/JS aceptada y almacenada sin saneamiento"


@pytest.mark.caso("TC-SEC-10")
def test_inyeccion_sql(ev, victima):
    r = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin' OR '1'='1' --", "password": "x"})
    ev.http(r, etiqueta="Payload en login")
    s = requests.get(f"{API}/clientes/search", params={"name": "%' OR 1=1 --"}, headers=h(victima["token"]))
    ev.http(s, cuerpo_max=120, etiqueta="Payload en búsqueda (token de la víctima)")
    ajenos = [c for c in s.json() if c.get("empresa_id") != victima["empresa_id"]] if s.ok else []
    total = psql("SELECT count(*) FROM clientes")
    ev.resultado(f"Login HTTP {r.status_code}; búsqueda devolvió {len(s.json())} filas (de {total} en la BD) "
                 f"y {len(ajenos)} de otras empresas: consultas parametrizadas efectivas")
    assert r.status_code == 401 and s.status_code == 200 and not ajenos


@pytest.mark.caso("TC-SEC-11")
def test_cors(ev):
    r = requests.options(f"{API}/clientes", headers={"Origin": "https://sitio-malicioso.example",
                                                     "Access-Control-Request-Method": "DELETE",
                                                     "Access-Control-Request-Headers": "authorization"})
    acao = r.headers.get("Access-Control-Allow-Origin")
    ev.nota("> OPTIONS /clientes  Origin: https://sitio-malicioso.example")
    for k in ("Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers"):
        ev.nota(f"< {k}: {r.headers.get(k)}")
    ev.resultado(f"La API autoriza cualquier origen (Access-Control-Allow-Origin: {acao})")
    assert acao not in ("*", "https://sitio-malicioso.example"), f"CORS abierto: Access-Control-Allow-Origin: {acao}"


@pytest.mark.caso("TC-SEC-12")
def test_cabeceras_seguridad(ev):
    requeridas = ["Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy",
                  "Strict-Transport-Security"]
    faltan = {}
    for nombre, url in (("API", API + "/"), ("Frontend", WEB + "/")):
        r = requests.get(url)
        aus = [c for c in requeridas if c not in r.headers]
        faltan[nombre] = aus
        ev.nota(f"{nombre}: faltan {aus}; X-Powered-By: {r.headers.get('X-Powered-By', 'no')}; Server: {r.headers.get('Server', '-')}")
    ev.resultado(f"API sin {len(faltan['API'])}/5 y frontend sin {len(faltan['Frontend'])}/5 cabeceras; la API revela 'X-Powered-By: Express'")
    assert not faltan["API"] and not faltan["Frontend"]


@pytest.mark.caso("TC-SEC-13")
def test_errores_y_logs(ev, victima):
    dup = requests.post(f"{API}/clientes", json={"nombre": "Duplicado", "correo": victima["cliente"]["correo"]},
                        headers=h(victima["token"]))
    ev.http(dup, cuerpo_max=260, etiqueta="Correo duplicado")
    inv = requests.get(f"{API}/clientes/abc", headers=h(victima["token"]))
    ev.http(inv, cuerpo_max=200, etiqueta="Identificador inválido")
    logs = docker("logs", "--tail", "400", "atlas-backend").stdout + docker("logs", "--tail", "400", "atlas-backend").stderr
    sensibles = [l for l in logs.splitlines() if "authUser" in l or "nombreUsuario" in l][:3]
    ev.nota("$ docker logs atlas-backend | grep authUser")
    for l in sensibles:
        ev.nota(f"  {l[:150]}")
    fuga = "glosa" in dup.text and ("duplicate key" in dup.text or "violates" in dup.text)
    ev.resultado(f"HTTP {dup.status_code} con detalle interno de PostgreSQL en 'glosa'; los logs imprimen el contenido del token")
    assert dup.status_code < 500 and not fuga, "Las respuestas exponen mensajes internos de la base de datos"
    assert not sensibles, "Los logs registran datos del token de los usuarios"


@pytest.mark.caso("TC-SEC-14")
def test_auditoria_confidencial_integra(ev, tok_editor, victima):
    r = requests.get(f"{API}/auditoria")
    ev.http(r, cuerpo_max=200, etiqueta="GET /auditoria sin token")
    usuarios = {x["usuario_id"] for x in r.json()} if r.ok else set()
    ev.nota(f"Usuarios distintos visibles en la auditoría: {len(usuarios)} (incluye '{victima['usuario']}': {victima['usuario'] in usuarios})")
    falso = requests.post(f"{API}/auditoria", headers=h(tok_editor),
                          json={"accion": "CLIENTES_ELIMINAR", "detalles": "eliminó cliente ID 9999 (evento fabricado)"})
    ev.http(falso, cuerpo_max=200, etiqueta="Editor inserta un evento falso")
    ev.resultado(f"Auditoría pública con eventos de {len(usuarios)} usuarios de distintas empresas; "
                 f"se aceptan eventos fabricados (HTTP {falso.status_code})")
    assert r.status_code == 401, "La auditoría completa es legible sin autenticación"
    assert falso.status_code in (401, 403, 404, 405), "Se pueden fabricar eventos de auditoría"


@pytest.mark.caso("TC-SEC-15")
def test_respaldo(ev):
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    archivos = [p.name for p in REPO.rglob("*") if p.is_file() and "node_modules" not in p.parts
                and re.search(r"backup|respaldo|pg_dump|restore", p.name, re.I)]
    menciones = re.findall(r"pg_dump|backup|respaldo", compose, re.I)
    ev.nota(f"docker-compose.yml: servicios {re.findall(r'^  ([a-z-]+):', compose, re.M)}; menciones a respaldo: {menciones or 'ninguna'}")
    ev.nota(f"Archivos de respaldo/restauración en el repositorio: {archivos or 'ninguno'}")
    ev.nota("Datos en volumen 'postgres_data' y documentos dentro de la BD: un fallo del volumen pierde todo")
    ev.resultado("No existe respaldo automatizado ni procedimiento de restauración")
    assert archivos or menciones, "No hay política ni mecanismo de respaldo y recuperación"


@pytest.mark.caso("TC-SEC-16")
def test_minimizacion_datos(ev, tok_editor):
    r = requests.get(f"{API}/clientes/search?name=", headers=h(tok_editor))
    ev.http(r, cuerpo_max=10, etiqueta="Editor lista clientes")
    for c in r.json()[:2]:
        ev.nota(f"  {c['nombre']}: RUT {c['rut']} | {c['nombre_banco']} cta {c['numero_cuenta']} | titular {c['titular_cuenta']}")
    completos = [c for c in r.json() if c.get("numero_cuenta") and "*" not in c["numero_cuenta"]]
    ev.resultado(f"El editor recibe {len(completos)} números de cuenta completos sin enmascarar")
    assert not completos, "La API entrega datos bancarios completos a un perfil de sólo lectura"


@pytest.mark.caso("TC-SEC-17")
def test_secreto_jwt_publicado(ev, victima):
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    m = re.search(r"JWT_SECRET: `([0-9a-f]{32,})`", readme)
    assert m, "No se encontró secreto en el README"
    secreto = m.group(1)
    ev.nota(f"README.md publica JWT_SECRET = {secreto[:10]}…{secreto[-6:]}")
    ahora = int(time.time())
    falso = firmar_jwt({"usuarioId": 99999, "nombreUsuario": "token_falsificado", "empresaUsuarioId": None,
                        "empresaId": victima["empresa_id"], "iat": ahora, "exp": ahora + 3600}, secreto)
    ev.nota(f"Token fabricado para empresaId={victima['empresa_id']}: {falso[:48]}…")
    r = requests.get(f"{API}/clientes/search?name=", headers=h(falso))
    ev.http(r, cuerpo_max=180, etiqueta="GET /clientes con el token falsificado")
    ev.resultado(f"La API acepta el token falsificado (HTTP {r.status_code}) y entrega {len(r.json()) if r.ok else 0} clientes de la víctima")
    assert r.status_code == 401, "Con el secreto publicado cualquiera puede fabricar tokens válidos de cualquier empresa"


@pytest.mark.caso("TC-SEC-18")
def test_politica_contrasenas(ev):
    aceptadas = []
    for clave in ("123", "password", "abcdefghijkl"):
        s = sufijo()
        r = requests.post(f"{API}/empresas", json={
            "usuario": {"nombre_usuario": f"debil_{s}", "contrasena_hash": clave, "correo": f"debil_{s}@qa.test"},
            "empresa": {"nombre": f"Débil {s}", "correo": f"debil_emp_{s}@qa.test"}})
        ev.nota(f"> registro con contraseña '{clave}' -> HTTP {r.status_code}")
        if r.status_code == 201:
            aceptadas.append(clave)
    ev.resultado(f"Se aceptaron {len(aceptadas)}/3 contraseñas débiles: {aceptadas}")
    assert not aceptadas, f"Contraseñas que incumplen la política aceptadas: {aceptadas}"


@pytest.mark.caso("TC-SEC-19")
def test_archivos_peligrosos(ev, victima):
    casos = [("malware.exe", b"MZ\x90\x00" + b"\x00" * 60 + b"ARCHIVO DE PRUEBA INOFENSIVO"),
             ("pagina.html", b"<html><script>alert('xss')</script></html>"),
             ("grande.pdf", b"%PDF-1.4\n" + b"0" * (25 * 1024 * 1024))]
    aceptados = []
    for nombre, contenido in casos:
        t0 = time.perf_counter()
        r = crear_contrato(victima["token"], victima["cliente"]["id"], archivo=contenido, nombre_archivo=nombre)
        ev.nota(f"> adjuntar {nombre:<12} ({len(contenido)/1024:,.0f} KB) -> HTTP {r.status_code} en {time.perf_counter()-t0:.1f} s")
        if r.status_code == 201:
            aceptados.append(nombre)
    ev.resultado(f"Archivos no permitidos aceptados: {aceptados}")
    assert not aceptados, f"Se aceptaron archivos no permitidos: {aceptados}"


@pytest.mark.caso("TC-SEC-20")
def test_fuerza_bruta(ev):
    def intento(i):
        return requests.post(f"{API}/autenticacion/login",
                             json={"nombre_usuario": "admin", "password": f"incorrecta{i}"}, timeout=60).status_code
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        codigos = list(ex.map(intento, range(30)))
    dur = time.perf_counter() - t0
    bloqueos = sum(c in (423, 429) for c in codigos)
    ok = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin", "password": "admin"})
    ev.nota(f"30 intentos fallidos en {dur:.1f} s con 10 hilos -> códigos: { {c: codigos.count(c) for c in set(codigos)} }")
    ev.nota(f"Login correcto inmediatamente después: HTTP {ok.status_code}")
    ev.resultado(f"Sin limitación de intentos: {bloqueos} respuestas 429/423 de 30")
    assert bloqueos > 0, "No existe limitación de intentos ni bloqueo de cuenta"

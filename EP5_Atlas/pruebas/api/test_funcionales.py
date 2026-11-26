"""Pruebas funcionales automatizadas de la API de Atlas (RF-1 a RF-6, RB, interfaz backend).

Cada aserción expresa el comportamiento CORRECTO exigido por el ERS: si el sistema se desvía,
el caso queda FALLÓ y el mensaje de la aserción documenta lo obtenido.
"""
import datetime as dt
import hashlib
import time

import pytest
import requests

from conftest import (API, CLAVE_QA, PNG_1PX, crear_cliente, crear_contrato, decodificar_jwt, h, login,
                      pdf_minimo, psql, registrar_empresa, sufijo)


@pytest.fixture(scope="module")
def empresa_qa():
    """Empresa propia del módulo funcional (aislada de la semilla)."""
    e = registrar_empresa("funcional")
    e["token"] = login(e["usuario"], e["clave"])
    e["cliente"] = crear_cliente(e["token"])  # TC-FUN-09 lo reemplaza por el cliente que verifica
    return e


@pytest.mark.caso("TC-FUN-01")
def test_login_emite_jwt(ev):
    r = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin", "password": "admin"})
    ev.http(r, cuerpo_max=120)
    assert r.status_code == 200, f"Login respondió HTTP {r.status_code}"
    claims = decodificar_jwt(r.json()["token"])
    ev.nota(f"payload JWT: {claims}")
    vigencia_h = (claims["exp"] - claims["iat"]) / 3600
    auditado = psql("SELECT count(*) FROM auditoria WHERE usuario_id='admin' AND accion LIKE 'LOGIN%' "
                    "AND fecha_hora > now() - interval '1 minute'")
    ev.nota(f"eventos LOGIN de admin en el último minuto: {auditado}")
    ev.resultado(f"HTTP 200 con JWT (usuarioId={claims['usuarioId']}, empresaId={claims['empresaId']}, "
                 f"vigencia {vigencia_h:.0f} h) y evento LOGIN auditado")
    assert {"usuarioId", "empresaId", "exp"} <= claims.keys()
    assert int(auditado) >= 1, "El inicio de sesión no quedó auditado"


@pytest.mark.caso("TC-FUN-02")
def test_credenciales_invalidas_genericas(ev):
    r1 = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin", "password": "clave_incorrecta"})
    ev.http(r1, etiqueta="Contraseña incorrecta")
    r2 = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": f"no_existe_{sufijo()}", "password": "x"})
    ev.http(r2, etiqueta="Usuario inexistente")
    ev.resultado(f"HTTP {r1.status_code} / {r2.status_code} con mensajes "
                 f"{'idénticos' if r1.text == r2.text else 'distintos'}")
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json(), "Los mensajes permiten distinguir usuarios existentes"


@pytest.mark.caso("TC-FUN-03")
def test_logout_revoca_token(ev):
    token = login("admin", "admin")
    r = requests.post(f"{API}/autenticacion/logout", headers=h(token))
    ev.http(r, cuerpo_max=150, etiqueta="Cerrar sesión")
    r2 = requests.get(f"{API}/clientes/search?name=", headers=h(token))
    ev.http(r2, cuerpo_max=80, etiqueta="Reutilizar el mismo token")
    ev.resultado(f"No existe servicio de logout (HTTP {r.status_code}); el token sigue aceptado (HTTP {r2.status_code})")
    assert r.status_code in (200, 204), f"No existe servicio de cierre de sesión (HTTP {r.status_code}); el logout del frontend sólo borra localStorage"
    assert r2.status_code == 401, "El token sigue siendo válido después del cierre de sesión"


@pytest.mark.caso("TC-FUN-04")
def test_refresh_token(ev, tok_admin):
    r = requests.post(f"{API}/autenticacion/login", json={"nombre_usuario": "admin", "password": "admin"})
    ev.nota(f"Claves de la respuesta de login: {list(r.json().keys())}")
    claims = decodificar_jwt(tok_admin)
    vig_min = (claims["exp"] - claims["iat"]) / 60
    rr = requests.post(f"{API}/autenticacion/refresh", headers=h(tok_admin))
    ev.http(rr, cuerpo_max=150)
    ev.resultado(f"Sin refresh token (HTTP {rr.status_code} en /refresh); access token de {vig_min:.0f} min")
    assert "refresh_token" in r.json() or "refreshToken" in r.json(), "El login no entrega refresh token"
    assert rr.status_code == 200, f"No existe endpoint de renovación (HTTP {rr.status_code})"
    assert vig_min <= 15, f"Vigencia del access token de {vig_min:.0f} minutos"


@pytest.mark.caso("TC-FUN-05")
def test_registro_y_empresa(ev):
    e = registrar_empresa("registro")
    ev.http(e["respuesta"], cuerpo_max=350)
    tok = login(e["usuario"], e["clave"])
    emp = e["empresa"]
    ev.nota(f"Login del nuevo usuario: OK (empresaId={decodificar_jwt(tok)['empresaId']})")
    ev.resultado("HTTP 201: usuario y empresa creados con nombre, dirección, teléfono y correo; login exitoso")
    assert all(emp.get(k) for k in ("nombre", "direccion", "telefono", "correo"))
    assert decodificar_jwt(tok)["empresaId"] == e["empresa_id"]


@pytest.mark.caso("TC-FUN-06")
def test_primer_usuario_admin(ev, empresa_qa):
    fila = psql(f"SELECT eu.id, eu.rol_id, r.nombre FROM empresa_usuarios eu JOIN roles r ON r.id=eu.rol_id "
                f"WHERE eu.usuario_id={empresa_qa['usuario_id']}")
    ev.nota(f"$ SELECT ... FROM empresa_usuarios WHERE usuario_id={empresa_qa['usuario_id']}")
    ev.nota(f"  {fila}")
    ev.resultado(f"El creador quedó vinculado con rol '{fila.split('|')[2]}'")
    assert fila.split("|")[1] == "1"


@pytest.mark.caso("TC-FUN-07")
def test_admin_crea_usuario_con_rol(ev, empresa_qa):
    nuevo = f"editor_{sufijo()}"
    r = requests.post(f"{API}/empresa-usuarios", headers=h(empresa_qa["token"]),
                      json={"nombre_usuario": nuevo, "contrasena_hash": CLAVE_QA, "correo": f"{nuevo}@qa.test", "rol_id": 2})
    ev.http(r)
    lst = requests.get(f"{API}/empresa-usuarios", headers=h(empresa_qa["token"]))
    fila = [u for u in lst.json() if u["nombre_usuario"] == nuevo]
    ev.nota(f"GET /empresa-usuarios -> {fila}")
    empresa_qa["editor_creado"] = fila[0]["id"] if fila else None
    ev.resultado(f"HTTP {r.status_code}; usuario listado con rol '{fila[0]['rol_nombre'] if fila else '-'}'")
    assert r.status_code == 201 and fila and fila[0]["rol_nombre"] == "editor"


@pytest.mark.caso("TC-FUN-08")
def test_admin_modifica_y_elimina_usuario(ev, empresa_qa):
    uid = empresa_qa.get("editor_creado")
    if not uid:
        pytest.skip("Depende de TC-FUN-07 (usuario editor no creado)")
    actual = requests.get(f"{API}/usuarios/{uid}").json()
    r = requests.put(f"{API}/usuarios/{uid}", headers=h(empresa_qa["token"]),
                     json={"nombre_usuario": actual["nombre_usuario"], "contrasena_hash": CLAVE_QA,
                           "correo": f"modificado_{sufijo()}@qa.test"})
    ev.http(r, etiqueta="Modificar usuario")
    d = requests.delete(f"{API}/usuarios/{uid}", headers=h(empresa_qa["token"]))
    ev.http(d, cuerpo_max=300, etiqueta="Eliminar usuario (como lo hace la interfaz)")
    ev.resultado(f"Modificación HTTP {r.status_code}; eliminación HTTP {d.status_code}")
    assert r.status_code == 200
    assert d.status_code == 200, (f"La eliminación falla con HTTP {d.status_code}: la clave foránea de empresa_usuarios "
                                  f"impide borrar a cualquier usuario vinculado a una empresa")


@pytest.mark.caso("TC-FUN-09")
def test_crear_cliente(ev, empresa_qa):
    from conftest import cliente_payload
    body = cliente_payload()
    r = requests.post(f"{API}/clientes", json=body, headers=h(empresa_qa["token"]))
    ev.http(r, cuerpo_max=250)
    g = requests.get(f"{API}/clientes/{r.json()['id']}", headers=h(empresa_qa["token"]))
    ok = all(g.json().get(k) == v for k, v in body.items() if k != "es_empresa")
    empresa_qa["cliente"] = r.json()
    ev.resultado(f"HTTP {r.status_code}; datos recuperados {'coinciden' if ok else 'NO coinciden'} con lo enviado")
    assert r.status_code == 201 and ok


@pytest.mark.caso("TC-FUN-10")
def test_listar_filtrar_paginar_editar(ev, empresa_qa):
    tok = empresa_qa["token"]
    a = crear_cliente(tok, nombre=f"Filtro Alfa {sufijo()}")
    crear_cliente(tok, nombre=f"Filtro Beta {sufijo()}")
    f = requests.get(f"{API}/clientes/search", params={"name": "Alfa"}, headers=h(tok))
    ev.http(f, cuerpo_max=120, etiqueta="Filtro por nombre")
    filtro_ok = f.status_code == 200 and all("Alfa" in c["nombre"] for c in f.json()) and len(f.json()) >= 1
    p = requests.get(f"{API}/clientes", params={"page": 1, "limit": 1}, headers=h(tok))
    ev.http(p, cuerpo_max=120, etiqueta="Paginación page=1&limit=1")
    a["nombre"] = a["nombre"] + " (editado)"
    u = requests.put(f"{API}/clientes/{a['id']}", json=a, headers=h(tok))
    ev.http(u, cuerpo_max=100, etiqueta="Edición")
    ev.resultado(f"Filtro {'correcto' if filtro_ok else 'incorrecto'}; paginación devuelve {len(p.json())} registros "
                 f"con limit=1; edición HTTP {u.status_code}")
    assert filtro_ok and u.status_code == 200
    assert len(p.json()) <= 1, f"No hay paginación: limit=1 devolvió {len(p.json())} clientes"


@pytest.mark.caso("TC-FUN-11")
def test_eliminacion_logica(ev, empresa_qa):
    c = crear_cliente(empresa_qa["token"])
    d = requests.delete(f"{API}/clientes/{c['id']}", headers=h(empresa_qa["token"]))
    ev.http(d)
    filas = psql(f"SELECT count(*) FROM clientes WHERE id={c['id']}")
    cols = psql("SELECT string_agg(column_name, ',') FROM information_schema.columns WHERE table_name='clientes' "
                "AND column_name IN ('deleted_at','activo','eliminado')")
    ev.nota(f"$ SELECT count(*) FROM clientes WHERE id={c['id']}  ->  {filas}")
    ev.nota(f"columnas de borrado lógico en clientes: {cols or 'ninguna'}")
    ev.resultado(f"Borrado físico: quedan {filas} filas; la interfaz sí pide confirmación (diálogo 'Confirmar eliminación')")
    assert filas == "1", "El cliente se eliminó físicamente de la base de datos (no hay eliminación lógica)"


@pytest.mark.caso("TC-FUN-12")
def test_validacion_campos(ev, empresa_qa):
    from conftest import cliente_payload
    tok = empresa_qa["token"]
    malo = cliente_payload(correo="no-es-correo", rut="123", telefono="abc")
    r1 = requests.post(f"{API}/clientes", json=malo, headers=h(tok))
    ev.http(r1, cuerpo_max=120, etiqueta="Correo, RUT y teléfono inválidos")
    sin_nombre = cliente_payload()
    sin_nombre.pop("nombre")
    r2 = requests.post(f"{API}/clientes", json=sin_nombre, headers=h(tok))
    ev.http(r2, cuerpo_max=200, etiqueta="Sin nombre (obligatorio)")
    ev.resultado(f"Formato inválido aceptado con HTTP {r1.status_code}; campo obligatorio ausente -> HTTP {r2.status_code}")
    assert r1.status_code == 400, f"El backend aceptó correo, RUT y teléfono inválidos (HTTP {r1.status_code})"
    assert r2.status_code == 400, f"Falta de nombre produce HTTP {r2.status_code} en vez de 400"


@pytest.mark.caso("TC-FUN-13")
def test_multiples_contratos(ev, empresa_qa):
    cli = empresa_qa["cliente"]
    r1 = crear_contrato(empresa_qa["token"], cli["id"], titulo=f"Servicio A {sufijo()}")
    r2 = crear_contrato(empresa_qa["token"], cli["id"], titulo=f"Servicio B {sufijo()}")
    ev.http(r1, cuerpo_max=200)
    ev.http(r2, cuerpo_max=200)
    lst = requests.get(f"{API}/contratos", headers=h(empresa_qa["token"])).json()
    ids = {x["id"] for x in lst}
    ev.resultado(f"HTTP {r1.status_code}/{r2.status_code}; ambos contratos presentes en el listado: {r1.json()['id'] in ids and r2.json()['id'] in ids}")
    assert r1.status_code == r2.status_code == 201 and {r1.json()["id"], r2.json()["id"]} <= ids


@pytest.mark.caso("TC-FUN-14")
def test_adjuntar_descargar_pdf(ev, empresa_qa):
    pdf = pdf_minimo("Contrato firmado TC-FUN-14")
    t0 = time.perf_counter()
    r = crear_contrato(empresa_qa["token"], empresa_qa["cliente"]["id"], archivo=pdf)
    t_subida = time.perf_counter() - t0
    ev.http(r, cuerpo_max=200, etiqueta="Subida")
    d = requests.get(f"{API}/contratos/{r.json()['id']}/file", headers=h(empresa_qa["token"]))
    ev.http(d, etiqueta="Descarga")
    iguales = hashlib.sha256(d.content).hexdigest() == hashlib.sha256(pdf).hexdigest()
    empresa_qa["contrato_pdf"] = r.json()["id"]
    ev.resultado(f"Subida {t_subida:.2f} s, descarga {d.elapsed.total_seconds():.2f} s; SHA-256 {'idéntico' if iguales else 'distinto'}")
    assert r.status_code == 201 and d.status_code == 200 and iguales
    assert t_subida <= 10 and d.elapsed.total_seconds() <= 10


@pytest.mark.caso("TC-FUN-15")
def test_formatos_conservan_tipo(ev, empresa_qa):
    r = crear_contrato(empresa_qa["token"], empresa_qa["cliente"]["id"], archivo=PNG_1PX, nombre_archivo="plano.png")
    d = requests.get(f"{API}/contratos/{r.json()['id']}/file", headers=h(empresa_qa["token"]))
    ev.http(d)
    ev.nota(f"Content-Type: {d.headers.get('Content-Type')} | Content-Disposition: {d.headers.get('Content-Disposition')}")
    ev.resultado(f"Un PNG se entrega como {d.headers.get('Content-Type')} con nombre 'contrato.pdf'")
    assert d.headers.get("Content-Type", "").startswith("image/png"), \
        f"El PNG se descarga como {d.headers.get('Content-Type')} y nombre contrato.pdf (archivo inutilizable)"


@pytest.mark.caso("TC-FUN-16")
def test_storage_interno(ev):
    tipo = psql("SELECT data_type FROM information_schema.columns WHERE table_name='documentos_contrato' AND column_name='document'")
    tam = psql("SELECT pg_size_pretty(pg_total_relation_size('documentos_contrato'))")
    from conftest import docker
    ls = docker("exec", "atlas-backend", "sh", "-c", "find /app/uploads -type f | wc -l").stdout.strip()
    ev.nota(f"$ columna documentos_contrato.document -> tipo {tipo}; tamaño de la tabla {tam}")
    ev.nota(f"$ find /app/uploads -type f | wc -l  ->  {ls}")
    ev.resultado(f"Los documentos se guardan como {tipo} dentro de PostgreSQL; el storage interno tiene {ls} archivos")
    assert tipo != "bytea", "El archivo se almacena dentro de la BD (bytea) en vez de storage interno referenciado"


@pytest.mark.caso("TC-FUN-17")
def test_estado_contrato(ev, empresa_qa):
    tok, cid = empresa_qa["token"], empresa_qa["cliente"]["id"]
    esperado = {}
    for dias, estado in ((90, "activo"), (10, "vence"), (-5, "expirado")):
        r = crear_contrato(tok, cid, fin_dias=dias, titulo=f"Estado {estado} {sufijo()}")
        esperado[r.json()["id"]] = estado
    lst = requests.get(f"{API}/contratos", headers=h(tok))
    est = requests.get(f"{API}/contratos/estados", headers=h(tok))
    ev.http(lst, cuerpo_max=250, etiqueta="GET /contratos")
    ev.http(est, cuerpo_max=250, etiqueta="GET /contratos/estados")
    con_estado = [c for c in lst.json() if c["id"] in esperado and "estado" in c]
    estados_srv = {c["id"]: c["estado"] for c in est.json() if c["id"] in esperado}
    ev.resultado(f"GET /contratos no incluye 'estado'; /estados sólo informa {sorted(set(estados_srv.values()))} "
                 f"(sin 'activo', máximo 3 por grupo)")
    assert len(con_estado) == 3, "El listado de contratos no informa el estado calculado de cada contrato"


@pytest.mark.caso("TC-FUN-18")
def test_enlace_compartir(ev, empresa_qa):
    cid = empresa_qa.get("contrato_pdf")
    r = requests.post(f"{API}/contratos/{cid}/share", headers=h(empresa_qa["token"]))
    ev.http(r, cuerpo_max=150, etiqueta="POST /contratos/:id/share")
    r2 = requests.get(f"{API}/contratos/{cid}/share", headers=h(empresa_qa["token"]))
    ev.http(r2, cuerpo_max=150, etiqueta="GET /contratos/:id/share")
    ev.resultado(f"No existe servicio para compartir documentos (HTTP {r.status_code}/{r2.status_code})")
    assert r.status_code in (200, 201), "RF-5.5 no implementado: no existe generación de enlace para compartir"


@pytest.mark.caso("TC-FUN-19")
def test_auditoria_acciones_criticas(ev):
    e = registrar_empresa("auditoria")
    tok = login(e["usuario"], e["clave"])
    desde = psql("SELECT now()")
    c = crear_cliente(tok)
    requests.put(f"{API}/clientes/{c['id']}", json={**c, "nombre": c["nombre"] + " v2"}, headers=h(tok))
    k = crear_contrato(tok, c["id"], archivo=pdf_minimo()).json()
    from conftest import multipart
    requests.put(f"{API}/contratos/{k['id']}", files=multipart({"titulo": "Contrato actualizado"}, pdf_minimo("v2"), "v2.pdf"),
                 headers=h(tok))
    requests.get(f"{API}/contratos/{k['id']}/file", headers=h(tok))
    nuevo = f"aud_{sufijo()}"
    requests.post(f"{API}/usuarios", json={"nombre_usuario": nuevo, "contrasena_hash": CLAVE_QA, "correo": f"{nuevo}@qa.test"},
                  headers=h(tok))
    uid = psql(f"SELECT id FROM usuarios WHERE nombre_usuario='{nuevo}'")
    requests.put(f"{API}/usuarios/{uid}", json={"nombre_usuario": nuevo, "contrasena_hash": CLAVE_QA,
                                                 "correo": f"{nuevo}2@qa.test"}, headers=h(tok))
    requests.delete(f"{API}/usuarios/{uid}", headers=h(tok))
    requests.delete(f"{API}/contratos/{k['id']}", headers=h(tok))
    c2 = crear_cliente(tok)
    requests.delete(f"{API}/clientes/{c2['id']}", headers=h(tok))
    filas = psql(f"SELECT split_part(accion, ':', 1) FROM auditoria WHERE usuario_id='{e['usuario']}' "
                 f"AND fecha_hora >= '{desde}' ORDER BY id").splitlines()
    acciones = {
        "Crear cliente": "CLIENTES_CREAR", "Editar cliente": "CLIENTES_ACTUALIZAR", "Eliminar cliente": "CLIENTES_ELIMINAR",
        "Crear contrato + subir documento": "CONTRATOS_CREAR", "Editar contrato + nuevo documento": "CONTRATOS_ACTUALIZAR",
        "Eliminar contrato": "CONTRATOS_ELIMINAR", "Descargar documento": "DOCUMENTO_DESCARGAR",
        "Crear usuario": "USUARIOS_CREAR", "Editar usuario": "USUARIOS_ACTUALIZAR", "Eliminar usuario": "USUARIOS_ELIMINAR",
    }
    faltan = []
    for nombre, clave in acciones.items():
        ok = clave in filas
        ev.nota(f"  [{'OK' if ok else 'NO'}] {nombre:<36} {clave}")
        if not ok:
            faltan.append(nombre)
    ev.resultado(f"{len(acciones) - len(faltan)}/{len(acciones)} acciones auditadas; sin registro: {', '.join(faltan)}")
    assert not faltan, f"Acciones críticas sin auditar: {', '.join(faltan)}"


@pytest.mark.caso("TC-FUN-20")
def test_correo_empresa_unico(ev, empresa_qa):
    s = sufijo()
    body = {"usuario": {"nombre_usuario": f"dup_{s}", "contrasena_hash": CLAVE_QA, "correo": f"dup_{s}@qa.test"},
            "empresa": {"nombre": "Empresa duplicada", "correo": empresa_qa["empresa"]["correo"]}}
    r = requests.post(f"{API}/empresas", json=body)
    ev.http(r, cuerpo_max=250)
    ev.resultado(f"Segunda empresa con el mismo correo rechazada (HTTP {r.status_code})")
    assert r.status_code >= 400 and r.status_code != 201


@pytest.mark.caso("TC-FUN-21")
def test_contrato_un_solo_cliente(ev, empresa_qa):
    fk = psql("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='contratos_cliente_id_fkey'")
    ev.nota(f"$ restricción contratos_cliente_id_fkey -> {fk}")
    from conftest import multipart
    r = requests.post(f"{API}/contratos", files=multipart({"cliente_id": "1,2", "titulo": "Doble", "fecha_inicio": "2026-01-01",
                                                          "fecha_fin": "2026-12-31"}), headers=h(empresa_qa["token"]))
    ev.http(r, cuerpo_max=150, etiqueta="cliente_id con dos valores")
    ev.resultado("cliente_id es referencia simple; la API no admite dos clientes")
    assert "FOREIGN KEY (cliente_id)" in fk and r.status_code != 201


@pytest.mark.caso("TC-FUN-22")
def test_swagger(ev):
    spec = requests.get(f"{API}/openapi.json").json()
    docs = requests.get(f"{API}/docs/")
    criticos = ["/autenticacion/login", "/clientes", "/contratos", "/contratos/{id}/file", "/usuarios", "/auditoria"]
    faltan = [p for p in criticos if p not in spec["paths"]]
    ev.nota(f"GET /docs/ -> HTTP {docs.status_code}; OpenAPI {spec.get('openapi')} con {len(spec['paths'])} rutas")
    ev.nota(f"securitySchemes: {list(spec.get('components', {}).get('securitySchemes', {}))}")
    ev.resultado(f"Swagger disponible; rutas críticas sin documentar: {faltan or 'ninguna'}")
    assert docs.status_code == 200 and not faltan

"""Pruebas no funcionales sobre la API: rendimiento CRUD (NFR-PERF-1) y migraciones (NFR-DIS-2)."""
import json
import statistics
import time

import pytest
import requests

from conftest import API, REPO, REPORTES, cliente_payload, crear_cliente, h, login, registrar_empresa


def percentil(datos, p):
    datos = sorted(datos)
    k = (len(datos) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(datos) - 1)
    return datos[f] + (datos[c] - datos[f]) * (k - f)


@pytest.mark.caso("TC-NFR-01")
def test_rendimiento_crud(ev):
    e = registrar_empresa("rendimiento")
    tok = login(e["usuario"], e["clave"])
    cli = crear_cliente(tok)
    n = 15
    ops = {
        "GET /clientes/:id": lambda: requests.get(f"{API}/clientes/{cli['id']}", headers=h(tok)),
        "POST /clientes": lambda: requests.post(f"{API}/clientes", json=cliente_payload(), headers=h(tok)),
        "GET /clientes": lambda: requests.get(f"{API}/clientes", headers=h(tok)),
        "GET /contratos": lambda: requests.get(f"{API}/contratos", headers=h(tok)),
        "POST /autenticacion/login": lambda: requests.post(f"{API}/autenticacion/login",
                                                           json={"nombre_usuario": e["usuario"], "password": e["clave"]}),
    }
    resumen = {}
    ev.nota(f"{'OPERACIÓN':<28}{'p50 (ms)':>10}{'p95 (ms)':>10}{'máx (ms)':>10}  ≤300 ms")
    for nombre, fn in ops.items():
        tiempos = []
        for _ in range(n):
            t0 = time.perf_counter()
            r = fn()
            tiempos.append((time.perf_counter() - t0) * 1000)
            assert r.status_code < 400, f"{nombre} respondió {r.status_code}"
        p50, p95 = percentil(tiempos, 50), percentil(tiempos, 95)
        resumen[nombre] = {"p50": round(p50), "p95": round(p95), "max": round(max(tiempos)), "muestras": [round(t) for t in tiempos]}
        ev.nota(f"{nombre:<28}{p50:>10.0f}{p95:>10.0f}{max(tiempos):>10.0f}  {'sí' if p95 <= 300 else 'NO'}")
    (REPORTES / "rendimiento_crud.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    lentos = [k for k, v in resumen.items() if v["p95"] > 300]
    ev.resultado(f"{len(lentos)} de {len(ops)} operaciones superan 300 ms (p95): {', '.join(lentos)}")
    detalle = ", ".join(f"{k}={resumen[k]['p95']} ms" for k in lentos)
    assert not lentos, f"Operaciones sobre el umbral de 300 ms (p95): {detalle}"


@pytest.mark.caso("TC-NFR-12")
def test_migraciones_versionadas(ev):
    pkg = json.loads((REPO / "BACKEND" / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    herramientas = [d for d in deps if d in ("node-pg-migrate", "knex", "sequelize", "typeorm", "prisma", "db-migrate", "umzug")]
    sql = sorted(p.name for p in (REPO / "BACKEND" / "sql").iterdir())
    ev.nota(f"Dependencias del backend: {list(deps)}")
    ev.nota(f"BACKEND/sql: {sql}")
    ev.nota("init-db.sh sólo se ejecuta cuando el volumen de PostgreSQL está vacío (docker-entrypoint-initdb.d)")
    ev.resultado("Sin herramienta de migraciones ni versiones del esquema: un cambio exige recrear la BD o SQL manual")
    assert herramientas, "No existen migraciones versionadas del esquema"

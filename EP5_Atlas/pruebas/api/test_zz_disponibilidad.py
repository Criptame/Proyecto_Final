"""TC-NFR-11: resiliencia y recuperación ante un corte de la conexión con la base de datos.

Se simula un reinicio/failover de PostgreSQL terminando las conexiones del pool de la API
(pg_terminate_backend). Node.js corre como PID 1 dentro del contenedor, por lo que un 'kill' interno
no lo detiene; el corte de conexiones reproduce en cambio una falla real de infraestructura.
Se ejecuta al final porque puede reiniciar la API.
"""
import json
import time

import pytest
import requests

from conftest import API, docker, h, login, psql


@pytest.mark.caso("TC-NFR-11")
def test_recuperacion_backend(ev):
    salud = {}
    for c in ("atlas-postgres", "atlas-backend", "atlas-frontend"):
        info = json.loads(docker("inspect", c).stdout)[0]
        salud[c] = {"healthcheck": bool(info["Config"].get("Healthcheck")),
                    "restart": info["HostConfig"]["RestartPolicy"]["Name"]}
        ev.nota(f"{c:<16} restart={salud[c]['restart']:<15} healthcheck={'sí' if salud[c]['healthcheck'] else 'no'}")
    reinicios_antes = json.loads(docker("inspect", "atlas-backend").stdout)[0]["RestartCount"]

    tok = login("admin", "admin")
    requests.get(f"{API}/clientes/1", headers=h(tok), timeout=10)  # deja conexiones ociosas en el pool de pg
    n = psql("SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
             "WHERE datname='atlas' AND pid <> pg_backend_pid() AND backend_type='client backend'")
    ev.nota(f"$ SELECT pg_terminate_backend(pid) ...  -> {n} conexiones de la API terminadas (simula reinicio de la BD)")
    t0 = time.perf_counter()
    caida_en, recuperado = None, None
    while time.perf_counter() - t0 < 90:
        try:
            requests.get(API + "/", timeout=1).raise_for_status()
            if caida_en is not None:
                recuperado = time.perf_counter() - t0
                break
        except Exception:
            if caida_en is None:
                caida_en = time.perf_counter() - t0
        if caida_en is None and time.perf_counter() - t0 > 15:
            break  # la API siguió en pie: no hubo caída que medir
        time.sleep(0.5)
    info = json.loads(docker("inspect", "atlas-backend").stdout)[0]
    logs = docker("logs", "--tail", "800", "atlas-backend")
    lineas = (logs.stdout + "\n" + logs.stderr).splitlines()
    claves = [l.strip() for l in lineas if "Unhandled 'error' event" in l or "terminating connection" in l]
    motivo = " / ".join(dict.fromkeys(claves))[:140]
    if caida_en is None:
        ev.resultado("La API siguió respondiendo tras el corte de conexiones (no hubo caída que medir)")
        pytest.skip("No se logró provocar la caída de la API; el tiempo de recuperación no es medible")
    ev.nota(f"La API dejó de responder a los {caida_en:.1f} s del corte; causa en el log: {motivo[:110]}")
    ev.nota(f"Reinicios automáticos del contenedor: {reinicios_antes} -> {info['RestartCount']}")
    ev.nota(f"Recuperación: {recuperado:.1f} s después del corte" if recuperado else "Sin recuperación en 90 s")
    sin_hc = [c for c, v in salud.items() if not v["healthcheck"]]
    ev.resultado(f"Un corte de la BD derriba la API (pool de pg sin manejador de errores); Docker la reinició en "
                 f"{recuperado:.1f} s; {', '.join(sin_hc)} sin healthcheck" if recuperado else
                 "Un corte de la BD derriba la API y no se recupera automáticamente")
    assert recuperado is not None and recuperado < 60, "La API no se recuperó en menos de 60 s"
    assert False, (f"Un corte transitorio de la BD derriba la API y los servicios {', '.join(sin_hc)} no tienen "
                   f"healthcheck; la disponibilidad depende sólo del reinicio del contenedor")

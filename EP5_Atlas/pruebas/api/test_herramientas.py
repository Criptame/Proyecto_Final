"""Interpreta los reportes de las herramientas de seguridad y carga ejecutadas por run_seguridad.ps1 / run_carga.ps1.

Si la herramienta no se ejecutó, el caso queda BLOQUEADO (no se inventan resultados).
"""
import json
import re

import pytest

from conftest import REPORTES, docker


def cargar(nombre):
    p = REPORTES / nombre
    if not p.exists() or p.stat().st_size == 0:
        pytest.skip(f"No existe {nombre}: la herramienta no se ejecutó")
    return json.loads(p.read_text(encoding="utf-8-sig"))


@pytest.mark.caso("TC-SEC-21")
def test_sca(ev):
    resumen, total_alto = {}, 0
    for proyecto in ("backend", "frontend"):
        d = cargar(f"npm_audit_{proyecto}.json")
        meta = d.get("metadata", {}).get("vulnerabilities", {})
        resumen[proyecto] = meta
        total_alto += meta.get("high", 0) + meta.get("critical", 0)
        ev.nota(f"npm audit {proyecto:<9} -> crítica {meta.get('critical', 0)}, alta {meta.get('high', 0)}, "
                f"moderada {meta.get('moderate', 0)}, baja {meta.get('low', 0)}")
        for nombre, v in list(d.get("vulnerabilities", {}).items()):
            if v.get("severity") in ("critical", "high"):
                titulos = [x.get("title", "") for x in v.get("via", []) if isinstance(x, dict)][:1]
                ev.nota(f"   · {nombre:<22} {v['severity']:<8} {titulos[0][:70] if titulos else '(dependencia transitiva)'}")
    t = cargar("trivy_fs.json")
    vulns = [v for r in t.get("Results", []) for v in (r.get("Vulnerabilities") or [])]
    sev = {s: sum(v["Severity"] == s for v in vulns) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    ev.nota(f"Trivy fs (CVE de dependencias) -> {sev}")
    ev.resultado(f"{total_alto} vulnerabilidades altas/críticas según npm audit; Trivy reporta {sev['CRITICAL']} críticas y {sev['HIGH']} altas")
    assert total_alto == 0 and sev["CRITICAL"] + sev["HIGH"] == 0, "Dependencias con CVE de severidad alta o crítica"


@pytest.mark.caso("TC-SEC-22")
def test_sast(ev):
    d = cargar("semgrep.json")
    res = d.get("results", [])
    por_sev = {}
    for r in res:
        por_sev[r["extra"]["severity"]] = por_sev.get(r["extra"]["severity"], 0) + 1
    ev.nota(f"Semgrep: {len(res)} hallazgos -> {por_sev}")
    vistos = set()
    for r in sorted(res, key=lambda x: {"ERROR": 0, "WARNING": 1}.get(x["extra"]["severity"], 2)):
        regla = r["check_id"].split(".")[-1]
        if regla in vistos:
            continue
        vistos.add(regla)
        ev.nota(f"  [{r['extra']['severity']}] {regla} -> {r['path'].removeprefix('/src/')}:{r['start']['line']}")
        if len(vistos) >= 9:
            break
    ev.resultado(f"{len(res)} hallazgos SAST ({por_sev.get('ERROR', 0)} de severidad ERROR)")
    assert por_sev.get("ERROR", 0) == 0, f"Semgrep reporta {por_sev.get('ERROR', 0)} hallazgos de severidad ERROR"


@pytest.mark.caso("TC-SEC-23")
def test_secretos(ev):
    d = cargar("gitleaks.json")
    ev.nota(f"Gitleaks: {len(d)} secretos detectados")
    for x in d[:8]:
        ev.nota(f"  {x['RuleID']:<24} {x['File'].removeprefix('/src/')}:{x['StartLine']}  {x['Secret'][:6]}…")
    ev.resultado(f"{len(d)} secretos expuestos en archivos del proyecto")
    assert not d, f"{len(d)} secretos expuestos en el repositorio"


@pytest.mark.caso("TC-SEC-24")
def test_dast_zap(ev):
    riesgos = {"3": "Alto", "2": "Medio", "1": "Bajo", "0": "Informativo"}
    medios_altos = 0
    for objetivo in ("frontend", "api"):
        d = cargar(f"zap_{objetivo}.json")
        alertas = [a for s in d.get("site", []) for a in s.get("alerts", [])]
        conteo = {}
        for a in alertas:
            conteo[riesgos[a["riskcode"]]] = conteo.get(riesgos[a["riskcode"]], 0) + 1
            medios_altos += a["riskcode"] in ("2", "3")
        ev.nota(f"ZAP baseline {objetivo}: {len(alertas)} alertas -> {conteo}")
        for a in sorted(alertas, key=lambda x: -int(x["riskcode"]))[:5]:
            ev.nota(f"  [{riesgos[a['riskcode']]}] {a['name']} (CWE-{a.get('cweid')})")
    ev.resultado(f"{medios_altos} alertas de riesgo medio o alto")
    assert medios_altos == 0, f"OWASP ZAP reporta {medios_altos} alertas de riesgo medio/alto"


@pytest.mark.caso("TC-SEC-25")
def test_contenedores_bd(ev):
    t = cargar("trivy_config.json")
    mis = [m for r in t.get("Results", []) for m in (r.get("Misconfigurations") or []) if m.get("Status") == "FAIL"]
    ev.nota(f"Trivy config: {len(mis)} configuraciones inseguras")
    for m in mis[:6]:
        ev.nota(f"  [{m['Severity']}] {m['ID']} {m['Title'][:70]}")
    r = docker("run", "--rm", "-e", "PGPASSWORD=postgres", "postgres:15-alpine", "psql", "-h", "host.docker.internal",
               "-p", "15432", "-U", "postgres", "-d", "atlas", "-t", "-A", "-c",
               "SELECT current_user || ' conectado; usuarios=' || (SELECT count(*) FROM usuarios)", timeout=180)
    ev.nota("$ psql -h <host> -p 15432 -U postgres (contraseña por defecto 'postgres')")
    ev.nota(f"  {r.stdout.strip() or r.stderr.strip()[:150]}")
    img = re.search(r"FROM (\S+)", (REPORTES.parent.parent / "CodigoFuenteA" / "BACKEND" / "Dockerfile").read_text())
    ev.nota(f"Imagen base del backend: {img.group(1) if img else '?'} (Node 18: fin de soporte abril 2025)")
    expuesta = "conectado" in r.stdout
    ev.resultado(f"BD accesible desde la red con credenciales por defecto: {'sí' if expuesta else 'no'}; "
                 f"{len(mis)} configuraciones inseguras en Dockerfile/compose")
    assert not expuesta and not mis, "Base de datos expuesta con credenciales por defecto y contenedores sin hardening"


@pytest.mark.caso("TC-NFR-03")
def test_carga_k6(ev):
    d = cargar("k6_resumen.json")
    m = d["metrics"]
    dur = m["http_req_duration"]["values"] if "values" in m["http_req_duration"] else m["http_req_duration"]
    fallos = m["http_req_failed"]["values"]["rate"] if "values" in m["http_req_failed"] else m["http_req_failed"]["value"]
    reqs = m["http_reqs"]["values"]["count"] if "values" in m["http_reqs"] else m["http_reqs"]["count"]
    vus = m["vus_max"]["values"]["max"] if "values" in m["vus_max"] else m["vus_max"]["max"]
    rps = m["http_reqs"]["values"]["rate"] if "values" in m["http_reqs"] else m["http_reqs"]["rate"]
    ev.nota(f"k6: {vus} usuarios virtuales, {reqs} peticiones ({rps:.1f} req/s)")
    ev.nota(f"  http_req_duration  p50={dur['med']:.0f} ms  p90={dur['p(90)']:.0f} ms  p95={dur['p(95)']:.0f} ms  máx={dur['max']:.0f} ms")
    ev.nota(f"  http_req_failed    {fallos*100:.2f} %")
    ev.resultado(f"Con {vus} usuarios concurrentes: p95 = {dur['p(95)']:.0f} ms y {fallos*100:.2f} % de errores")
    assert dur["p(95)"] < 300 and fallos < 0.01, f"p95 de {dur['p(95)']:.0f} ms bajo 200 usuarios (umbral 300 ms)"

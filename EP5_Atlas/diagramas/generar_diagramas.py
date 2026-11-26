"""Genera los diagramas del informe EP5 como HTML y los renderiza a PNG (2x) con Playwright.

Diseño vertical de 1000 px de ancho con fuentes de 17-19 px para que, insertados a 16 cm en el
informe (hoja Carta), el texto conserve un tamaño impreso de 8-9 pt.

D1 Pipeline DevSecOps con compuertas automatizadas y su alineación normativa y legal.
D2 Arquitectura de controles por capas con el estado REAL verificado por la suite (resultados.json).
D3 Flujo de la automatización (fuente única de verdad → ejecución → evidencia → informe).
D4 Plan de mantenimiento (ISO/IEC/IEEE 14764 en ciclo PDCA).
"""
import json
import pathlib

from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parent
RES = json.loads((AQUI.parent / "reportes" / "resultados.json").read_text(encoding="utf-8"))

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,Helvetica,sans-serif;color:#1f2933;background:#fff;padding:18px;width:1000px;font-size:17px}
.tag{display:inline-block;font-size:15px;padding:3px 9px;border-radius:11px;margin:3px 4px 3px 0;font-weight:bold}
.n{background:#e6f0ff;color:#1d4e89;border:1px solid #9fbfe8}
.l{background:#fff4e0;color:#8a4b00;border:1px solid #f0c27a}
.t{background:#eef1f4;color:#3e4c59;border:1px solid #c5ccd3}
.ok{background:#e3f6ea;color:#1b6b3a;border:1px solid #8fd1a7}
.ko{background:#fde8e8;color:#a61b1b;border:1px solid #f0a3a3}
.down{text-align:center;font-size:26px;color:#829ab1;line-height:30px}
"""


def estado(*ids):
    est = [RES.get(i, {}).get("estado", "SIN DATO") for i in ids]
    if all(e == "PASÓ" for e in est):
        return "ok", "✔ verificado"
    if any(e == "FALLÓ" for e in est):
        return "ko", "✘ ausente o con falla"
    return "t", "– sin dato"


# ---------------------------------------------------------------------------- D1
ETAPAS = [
    ("1. Código", "Estación del desarrollador", "#334e68",
     [("Hook pre-commit con Gitleaks", "TC-SEC-23"), ("Reglas Semgrep propias en el IDE", "TC-SEC-22")],
     ["ISO 27001 A.8.28 Codificación segura"], ["Ley 21.719: deber de seguridad"]),
    ("2. Integración continua", "En cada pull request", "#1d4e89",
     [("Semgrep: SAST (rulesets + reglas Atlas)", "TC-SEC-22"), ("npm audit + Trivy: SCA", "TC-SEC-21"),
      ("pytest: API funcional y de seguridad", "TC-FUN / TC-SEC")],
     ["ISO 27001 A.8.29 Pruebas de seguridad", "A.8.8 Vulnerabilidades técnicas", "OWASP Top 10:2025"],
     ["Ley 19.628 art. 11: cuidado de los datos"]),
    ("3. Construcción", "Imagen Docker versionada", "#2f6f9f",
     [("Trivy config: Dockerfile y compose", "TC-SEC-25"), ("SBOM CycloneDX de la imagen", "A03:2025")],
     ["ISO 27001 A.8.9 Configuración", "A.8.32 Gestión de cambios"], []),
    ("4. Ambiente QA", "Despliegue efímero con Docker Compose", "#3d7f72",
     [("OWASP ZAP baseline: DAST", "TC-SEC-24"), ("Playwright + axe-core: UI y WCAG", "TC-NFR-04 a 10"),
      ("k6: 200 usuarios concurrentes", "TC-NFR-03")],
     ["ISO 27001 A.8.31 Separación de ambientes", "ISO/IEC 25010", "WCAG 2.1 AA"], []),
    ("5. Compuerta de calidad", "Aprobación automática con evidencia", "#8a4b00",
     [("0 vulnerabilidades críticas/altas y 0 secretos", "bloqueante"),
      ("p95 < 300 ms y 0 violaciones WCAG serias", "bloqueante"), ("Reportes archivados", "ISO/IEC/IEEE 29119-3")],
     ["ISO/IEC/IEEE 29119", "A.8.32 Gestión de cambios"], ["Ley 21.719: responsabilidad proactiva"]),
    ("6. Producción y operación", "Monitoreo continuo", "#5b3a8c",
     [("TLS 1.3, HSTS y límite de intentos", "TC-SEC-01 / 20"), ("Respaldo cifrado y restauración probada", "TC-SEC-15"),
      ("Logs centralizados, alertas y healthcheck", "TC-SEC-14 / TC-NFR-11")],
     ["ISO 27001 A.8.13 Respaldo", "A.8.15 Registro", "A.8.16 Monitoreo"],
     ["Ley 21.719: reporte de vulneraciones", "Ley 21.663 Ciberseguridad"]),
]


def d1():
    filas = ""
    for i, (tit, sub, color, ctrls, normas, leyes) in enumerate(ETAPAS):
        items = "".join(f'<div class="ctl">{c}<span>{ref}</span></div>' for c, ref in ctrls)
        nn = "".join(f'<span class="tag n">{n}</span>' for n in normas) + "".join(f'<span class="tag l">{x}</span>' for x in leyes)
        filas += f'''<div class="st"><div class="hd" style="background:{color}">{tit}<small>{sub}</small></div>
        <div class="bd">{items}</div><div class="nm">{nn}<div class="gate">⛔ Si falla, bloquea el avance</div></div></div>'''
        if i < len(ETAPAS) - 1:
            filas += '<div class="down">▼</div>'
    return f"""<html><head><meta charset="utf-8"><style>{CSS}
    .st{{display:flex;border:1px solid #c5ccd3;border-radius:10px;overflow:hidden;background:#fbfcfd}}
    .hd{{width:215px;color:#fff;font-weight:bold;font-size:19px;padding:12px}} .hd small{{display:block;font-weight:normal;font-size:15px;margin-top:4px;opacity:.92}}
    .bd{{flex:1;padding:8px 10px}} .ctl{{display:flex;justify-content:space-between;gap:12px;background:#fff;border:1px solid #d9e2ec;border-radius:7px;padding:6px 9px;margin:3px 0;font-size:17px}}
    .ctl span{{color:#627d98;font-size:15px;white-space:nowrap;align-self:center}}
    .nm{{width:300px;padding:8px;border-left:1px dashed #c5ccd3}}
    .gate{{font-size:15px;color:#a61b1b;margin-top:4px;font-weight:bold}}
    .loop{{margin-top:12px;border:2px dashed #829ab1;border-radius:10px;padding:10px 14px;font-size:17px;background:#f5f8fb}}
    .ley{{margin-top:10px;font-size:15px}}</style></head><body>{filas}
    <div class="loop">↺ <b>Retroalimentación:</b> cada hallazgo entra al backlog con su criticidad CVSS v3.1, se corrige y la misma batería (run_todo.ps1) se re-ejecuta como prueba de regresión.</div>
    <div class="ley"><span class="tag n">Norma técnica</span> ISO/IEC 27001:2022 (Anexo A), ISO/IEC/IEEE 29119, ISO/IEC 25010, OWASP, WCAG
    <span class="tag l">Marco legal</span> Leyes 19.628, 21.719 y 21.663</div></body></html>"""


# ---------------------------------------------------------------------------- D2
CAPAS = [
    ("Cliente (navegador)", "#334e68", [
        ("Escape de salida (React)", "NFR-SEG-5", ["TC-SEC-09"], True),
        ("Content-Security-Policy", "NFR-SEG-5", ["TC-SEC-12"], False),
        ("Rol entregado por el servidor", "NFR-SEG-4", ["TC-SEC-04"], False),
        ("Mensajes de error de negocio", "NFR-USAB-3", ["TC-NFR-07"], False)]),
    ("Borde y transporte", "#1d4e89", [
        ("TLS 1.3 + HSTS", "NFR-SEG-1", ["TC-SEC-01"], False),
        ("CORS con lista blanca", "NFR-SEG-5", ["TC-SEC-11"], False),
        ("Cabeceras de seguridad", "NFR-SEG-5", ["TC-SEC-12"], False),
        ("Límite de intentos de login", "NFR-SEG-5", ["TC-SEC-20"], False)]),
    ("API (Express)", "#2f6f9f", [
        ("JWT corto, refresh y revocación", "RF-1.2 · NFR-SEG-9", ["TC-FUN-03", "TC-FUN-04"], False),
        ("Secreto de firma protegido", "NFR-SEG-9", ["TC-SEC-17"], False),
        ("Autenticación en todos los endpoints", "NFR-SEG-4", ["TC-SEC-05", "TC-SEC-06"], False),
        ("RBAC: el editor sólo lee", "RF-3.2 · RB-4", ["TC-SEC-04"], False),
        ("Aislamiento entre empresas", "RB-2", ["TC-SEC-07", "TC-SEC-08"], False),
        ("Validación de entradas", "RF-4.3 · NFR-SEG-5", ["TC-FUN-12", "TC-SEC-09"], False),
        ("Consultas parametrizadas", "NFR-SEG-5", ["TC-SEC-10"], False),
        ("Validación de archivos", "RF-5.2", ["TC-SEC-19"], False),
        ("Auditoría completa y protegida", "RF-6.1 · NFR-SEG-6", ["TC-FUN-19", "TC-SEC-14"], False)]),
    ("Datos", "#3d7f72", [
        ("Contraseñas con bcrypt", "NFR-SEG-2", ["TC-SEC-02"], False),
        ("Cifrado de datos bancarios", "NFR-SEG-3", ["TC-SEC-03"], False),
        ("BD no expuesta", "NFR-SEG-3", ["TC-SEC-25"], False),
        ("Respaldo y restauración", "NFR-SEG-7", ["TC-SEC-15"], False),
        ("Eliminación lógica", "Criterio RF-4", ["TC-FUN-11"], False),
        ("Storage de documentos", "RF-5.3", ["TC-FUN-16"], False)]),
    ("Operación y suministro", "#5b3a8c", [
        ("SCA de dependencias", "OWASP A03:2025", ["TC-SEC-21"], False),
        ("Escaneo de secretos", "NFR-SEG-9", ["TC-SEC-23"], False),
        ("Healthcheck y recuperación", "NFR-DIS-1", ["TC-NFR-11"], False),
        ("Migraciones versionadas", "NFR-DIS-2", ["TC-NFR-12"], False)]),
]


def d2():
    filas, total, ok = "", 0, 0
    ui = AQUI.parent / "evidencias" / "TC-SEC-09_ui.json"
    sin_dialogos = ui.exists() and not json.loads(ui.read_text(encoding="utf-8"))["dialogos"]
    for capa, color, ctrls in CAPAS:
        celdas = ""
        for nombre, nfr, casos, es_ui in ctrls:
            cls, txt = estado(*casos)
            if es_ui:
                cls, txt = ("ok", "✔ verificado en la UI") if sin_dialogos else ("ko", "✘ script ejecutado")
            total += 1
            ok += cls == "ok"
            celdas += f'''<div class="c {cls}b"><b>{nombre}</b><div class="m">{nfr} · {' / '.join(casos)}</div>
            <span class="st {cls}">{txt}</span></div>'''
        filas += f'<div class="capa"><div class="lab" style="background:{color}">{capa}</div><div class="grid">{celdas}</div></div>'
    return f"""<html><head><meta charset="utf-8"><style>{CSS}
    .capa{{display:flex;margin-bottom:9px;border:1px solid #c5ccd3;border-radius:10px;overflow:hidden}}
    .lab{{width:150px;color:#fff;font-weight:bold;font-size:18px;padding:10px;display:flex;align-items:center}}
    .grid{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:8px;background:#fbfcfd}}
    .c{{border-radius:8px;padding:6px 9px;background:#fff;font-size:17px}} .m{{font-size:14.5px;color:#52606d;margin:2px 0 3px}}
    .okb{{border:2px solid #8fd1a7}} .kob{{border:2px solid #f0a3a3}} .tb{{border:2px solid #c5ccd3}}
    .st{{display:inline-block;font-size:14.5px;font-weight:bold;padding:1px 8px;border-radius:9px}}
    .res{{margin:0 0 10px}}</style></head><body>
    <div class="res"><span class="tag ok">✔ {ok} controles verificados</span><span class="tag ko">✘ {total-ok} controles ausentes o con falla</span>
    <span class="tag t">{total} controles exigidos por el ERS, OWASP ASVS e ISO/IEC 27001</span></div>{filas}</body></html>"""


# ---------------------------------------------------------------------------- D3
def d3():
    herramientas = [("Semgrep", "SAST"), ("Gitleaks", "Secretos"), ("npm audit + Trivy", "SCA e IaC"),
                    ("OWASP ZAP", "DAST pasivo"), ("pytest + requests", "API y pentest"), ("Playwright", "UI, 4 navegadores"),
                    ("axe-core", "WCAG 2.1 AA"), ("k6", "Carga 200 VU"), ("psql / Docker", "Caja blanca y caídas")]
    tools = "".join(f'<div class="tool"><b>{a}</b>{b}</div>' for a, b in herramientas)
    return f"""<html><head><meta charset="utf-8"><style>{CSS}
    .b{{border:2px solid #9fb3c8;border-radius:10px;padding:10px 14px;background:#f5f8fb}}
    .b h3{{font-size:19px;margin-bottom:6px;color:#102a43}} .b li{{margin-left:20px;margin-bottom:2px}}
    .row{{display:flex;gap:10px}} .row .b{{flex:1}}
    .tools{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px}} .tool{{background:#fff;border:1px solid #d9e2ec;border-radius:7px;padding:6px 8px}}
    .tool b{{display:block;color:#1d4e89}}</style></head><body>
    <div class="row"><div class="b"><h3>① catalogo.py: fuente única de verdad</h3><ul><li>59 casos: ID, requerimiento del ERS, tipo, OWASP, CWE y vector CVSS</li><li>Criterio de aceptación y mitigación propuesta</li></ul></div>
    <div class="b"><h3>② run_todo.ps1: un solo comando</h3><ul><li>9 etapas encadenadas</li><li>Mide el tiempo real de cada etapa</li><li>Ambiente reproducible con Docker</li></ul></div></div>
    <div class="down">▼</div>
    <div class="b"><h3>③ Herramientas ejecutadas (contenedores Docker y Python)</h3><div class="tools">{tools}</div></div>
    <div class="down">▼</div>
    <div class="row"><div class="b"><h3>④ Salidas trazables</h3><ul><li>resultados.json: PASÓ / FALLÓ / BLOQUEADO</li><li>evidencias/*.txt y *.png por caso</li><li>Reportes HTML de pytest, ZAP y k6</li></ul></div>
    <div class="b"><h3>⑤ generar_informe.py</h3><ul><li>Tablas, matriz y criticidad CVSS</li><li>Figuras de evidencia</li><li>Informe Word coherente con la ejecución</li></ul></div></div>
    </body></html>"""


# ---------------------------------------------------------------------------- D4
def d4():
    tipos = [("Correctivo", "#a61b1b", "Remediar hallazgos según criticidad: críticos ≤ 7 días, altos ≤ 30 días, medios en la siguiente iteración; regresión obligatoria.", "ISO/IEC/IEEE 14764 · SLA por CVSS"),
             ("Preventivo", "#1d4e89", "SAST, SCA y secretos en cada commit; ZAP y k6 nocturnos; revisión mensual de dependencias; rotación trimestral de secretos.", "ISO 27001 A.8.8 · A.8.29"),
             ("Adaptativo", "#3d7f72", "Migrar Node 18 (sin soporte) a Node 22 LTS; adecuar el tratamiento de datos a la Ley 21.719 y a nuevas versiones del ERS.", "Ley 21.719 · NFR-DIS-2"),
             ("Perfectivo", "#8a4b00", "Mejorar accesibilidad, rendimiento y usabilidad para adultos mayores a partir de métricas e incidencias reales.", "ISO/IEC 25010 · WCAG 2.1")]
    cajas = "".join(f'<div class="tp" style="border-color:{c}"><div class="th" style="background:{c}">{t}</div><p>{d}</p><span class="tag n">{n}</span></div>' for t, c, d, n in tipos)
    pdca = [("1 · Planificar", "Priorizar el backlog por CVSS y riesgo legal; fijar la ventana de mantenimiento."),
            ("2 · Hacer", "Corregir en una rama; migración versionada; respaldo previo obligatorio."),
            ("3 · Verificar", "Ejecutar run_todo.ps1: compuertas de calidad y regresión completa."),
            ("4 · Actuar", "Desplegar, monitorear, registrar lecciones y actualizar el catálogo de casos.")]
    ciclo = "".join(f'<div class="p"><b>{a}</b>{b}</div>' for a, b in pdca)
    return f"""<html><head><meta charset="utf-8"><style>{CSS}
    .tps{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}}
    .tp{{border:2px solid;border-radius:10px;overflow:hidden;background:#fbfcfd}} .tp p{{padding:8px 12px 4px}} .tp .tag{{margin:0 12px 10px}}
    .th{{color:#fff;font-weight:bold;font-size:19px;padding:8px 12px}}
    .cy{{border:2px dashed #829ab1;border-radius:12px;padding:10px;background:#f5f8fb}} .cy h3{{font-size:19px;margin-bottom:8px}}
    .ps{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px}}
    .p{{background:#fff;border:1px solid #c5ccd3;border-radius:8px;padding:8px;font-size:16px}} .p b{{display:block;color:#102a43;margin-bottom:4px;font-size:17px}}
    .ind{{margin-top:10px;font-size:16px}}</style></head><body>
    <div class="tps">{cajas}</div>
    <div class="cy"><h3>↺ Ciclo PDCA aplicado a cada iteración del software</h3><div class="ps">{ciclo}</div></div>
    <div class="ind"><b>Indicadores:</b> <span class="tag t">% de casos PASÓ</span><span class="tag t">hallazgos críticos abiertos</span>
    <span class="tag t">MTTR de vulnerabilidades</span><span class="tag t">p95 de la API</span><span class="tag t">violaciones WCAG serias</span><span class="tag t">restauraciones exitosas</span></div>
    </body></html>"""


if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1036, "height": 400}, device_scale_factor=2)
        for nombre, fn in (("D1_pipeline_devsecops", d1), ("D2_controles_por_capas", d2),
                           ("D3_flujo_automatizacion", d3), ("D4_plan_mantenimiento", d4)):
            html = fn()
            (AQUI / f"{nombre}.html").write_text(html, encoding="utf-8")
            pg.set_content(html)
            pg.wait_for_timeout(200)
            pg.screenshot(path=str(AQUI / f"{nombre}.png"), full_page=True)
            print("ok", nombre)
        b.close()

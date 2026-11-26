"""Pruebas de interfaz automatizadas con Playwright: rendimiento web, accesibilidad, usabilidad,
compatibilidad multinavegador y responsividad. Además captura la evidencia visual del informe."""
import json
import time

import pytest
import requests
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

from conftest import API, EVID, REPORTES, WEB, CLAVE_QA, crear_cliente, h, login, sufijo

WCAG = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}}


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def chromium(pw):
    b = pw.chromium.launch()
    yield b
    b.close()


def iniciar_sesion(page, usuario="admin", clave="admin", timeout=30000):
    page.goto(f"{WEB}/login")
    page.get_by_test_id("input-nombre-usuario").fill(usuario)
    page.get_by_test_id("input-password").fill(clave)
    with page.expect_response(lambda r: "/metricas" in r.url, timeout=timeout):
        page.get_by_test_id("button-login").click()
    page.wait_for_timeout(600)


def captura(page, nombre, full=False):
    page.screenshot(path=str(EVID / f"{nombre}.png"), full_page=full)


# ---------------------------------------------------------------- evidencia visual general
def test_capturas_generales(chromium):
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(f"{WEB}/login")
    page.wait_for_load_state("networkidle")
    captura(page, "UI_01_login")
    iniciar_sesion(page)
    captura(page, "UI_02_dashboard")
    with page.expect_response(lambda r: r.url.startswith(API) and r.url.endswith("/clientes"), timeout=30000):
        page.goto(f"{WEB}/clientes")
    page.wait_for_timeout(500)
    captura(page, "UI_03_clientes")
    with page.expect_response(lambda r: r.url.startswith(API) and r.url.endswith("/contratos"), timeout=30000):
        page.goto(f"{WEB}/contratos")
    page.wait_for_timeout(500)
    captura(page, "UI_04_contratos")
    page.goto(f"{WEB}/auditoria")
    page.wait_for_timeout(1500)
    captura(page, "UI_05_auditoria")
    page.goto(f"{API}/docs/")
    page.wait_for_timeout(2000)
    captura(page, "UI_06_swagger")
    ctx.close()


def test_xss_no_se_ejecuta_en_ui(chromium):
    """Complemento visual de TC-SEC-09: el payload almacenado se muestra escapado por React."""
    tok = login("admin", "admin")
    crear_cliente(tok, nombre="<img src=x onerror=alert(document.domain)>")
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page = ctx.new_page()
    dialogos = []
    page.on("dialog", lambda d: (dialogos.append(d.message), d.dismiss()))
    iniciar_sesion(page)
    with page.expect_response(lambda r: r.url.startswith(API) and r.url.endswith("/clientes"), timeout=30000):
        page.goto(f"{WEB}/clientes")
    page.wait_for_timeout(1500)
    captura(page, "TC-SEC-09_ui")
    (EVID / "TC-SEC-09_ui.json").write_text(json.dumps({"dialogos": dialogos}), encoding="utf-8")
    ctx.close()


# ---------------------------------------------------------------- NFR-PERF-2
@pytest.mark.caso("TC-NFR-02")
def test_carga_movil(ev, chromium):
    ctx = chromium.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150,
                                                   "downloadThroughput": 1.6 * 1024 * 1024 / 8,
                                                   "uploadThroughput": 750 * 1024 / 8})
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    t0 = time.perf_counter()
    page.goto(f"{WEB}/login", wait_until="load")
    page.get_by_test_id("button-login").wait_for()
    t_login = time.perf_counter() - t0
    nav = page.evaluate("JSON.stringify(performance.getEntriesByType('navigation')[0])")
    nav = json.loads(nav)
    page.get_by_test_id("input-nombre-usuario").fill("admin")
    page.get_by_test_id("input-password").fill("admin")
    t1 = time.perf_counter()
    with page.expect_response(lambda r: "/metricas" in r.url, timeout=60000):
        page.get_by_test_id("button-login").click()
    page.wait_for_timeout(200)
    t_dash = time.perf_counter() - t1
    captura(page, "TC-NFR-02_dashboard_movil")
    ev.nota("Emulación: 390×844, 4G lenta (1,6 Mbps / 150 ms RTT), CPU 4× más lenta, caché deshabilitada")
    ev.nota(f"Login visible (interactivo): {t_login:.2f} s | DOMContentLoaded {nav['domContentLoadedEventEnd']/1000:.2f} s | "
            f"transferido {nav['transferSize']/1024:.0f} KB (documento)")
    ev.nota(f"Desde 'Ingresar' hasta dashboard con métricas: {t_dash:.2f} s")
    ev.resultado(f"Login listo en {t_login:.2f} s; dashboard (página principal) en {t_dash:.2f} s")
    (REPORTES / "carga_movil.json").write_text(json.dumps({"login_s": t_login, "dashboard_s": t_dash}), encoding="utf-8")
    ctx.close()
    assert t_login < 2 and t_dash < 2, f"Página principal en {t_dash:.1f} s (umbral 2 s)"


# ---------------------------------------------------------------- NFR-USAB-1 (axe)
@pytest.mark.caso("TC-NFR-04")
def test_accesibilidad_axe(ev, chromium):
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768})
    page = ctx.new_page()
    axe = Axe()
    vistas = {"Login": "/login", "Registro": "/registro"}
    resultados = {}
    for nombre, ruta in vistas.items():
        page.goto(WEB + ruta)
        page.wait_for_load_state("networkidle")
        resultados[nombre] = axe.run(page, options=WCAG).response["violations"]
    iniciar_sesion(page)
    resultados["Dashboard"] = axe.run(page, options=WCAG).response["violations"]
    for nombre, ruta in (("Clientes", "/clientes"), ("Contratos", "/contratos")):
        with page.expect_response(lambda r: r.url.startswith(API) and r.url.endswith(ruta), timeout=30000):
            page.goto(WEB + ruta)
        page.wait_for_timeout(800)
        resultados[nombre] = axe.run(page, options=WCAG).response["violations"]
    ctx.close()
    serias = 0
    ev.nota(f"{'VISTA':<11}{'crítica':>8}{'seria':>7}{'moderada':>10}{'menor':>7}   reglas")
    for vista, viol in resultados.items():
        c = {k: sum(1 for v in viol if v["impact"] == k) for k in ("critical", "serious", "moderate", "minor")}
        serias += c["critical"] + c["serious"]
        ev.nota(f"{vista:<11}{c['critical']:>8}{c['serious']:>7}{c['moderate']:>10}{c['minor']:>7}   "
                f"{', '.join(sorted({v['id'] for v in viol}))[:80]}")
    reglas = {}
    for viol in resultados.values():
        for v in viol:
            reglas.setdefault(v["id"], (v["impact"], v["help"], 0))
            reglas[v["id"]] = (v["impact"], v["help"], reglas[v["id"]][2] + len(v["nodes"]))
    for rid, (imp, ayuda, n) in sorted(reglas.items(), key=lambda x: x[1][0] != "critical"):
        ev.nota(f"  · {rid} [{imp}] {ayuda} ({n} elementos)")
    (REPORTES / "axe.json").write_text(json.dumps(resultados, ensure_ascii=False)[:2_000_000], encoding="utf-8")
    ev.resultado(f"{serias} violaciones de impacto crítico o serio en 5 vistas ({len(reglas)} reglas WCAG incumplidas)")
    assert serias == 0, f"{serias} violaciones WCAG 2.1 AA de impacto crítico/serio"


# ---------------------------------------------------------------- 3.1.1 tipografía y objetivos táctiles
JS_MEDIDAS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const textos = [...document.querySelectorAll('body *')].filter(e => vis(e) &&
    [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 0));
  const peq = textos.map(e => ({t: e.textContent.trim().slice(0, 40), fs: parseFloat(getComputedStyle(e).fontSize)}))
                    .filter(x => x.fs < 12);
  const inter = [...document.querySelectorAll('a,button,input,select,textarea,[role=button],[role=checkbox]')].filter(vis);
  const chicos = inter.map(e => { const r = e.getBoundingClientRect();
      return {t: (e.getAttribute('aria-label') || e.textContent || e.name || e.tagName).trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height)}; })
    .filter(x => x.w < 24 || x.h < 24);
  const min = Math.min(...textos.map(e => parseFloat(getComputedStyle(e).fontSize)));
  return {min, peq: peq.slice(0, 6), npeq: peq.length, chicos: chicos.slice(0, 6), nchicos: chicos.length, ninter: inter.length};
}"""


@pytest.mark.caso("TC-NFR-05")
def test_tipografia_y_objetivos(ev, chromium):
    ctx = chromium.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(WEB + "/login")
    page.wait_for_load_state("networkidle")
    m_login = page.evaluate(JS_MEDIDAS)
    iniciar_sesion(page)
    m_dash = page.evaluate(JS_MEDIDAS)
    ctx.close()
    for nombre, m in (("Login", m_login), ("Dashboard", m_dash)):
        ev.nota(f"{nombre}: fuente mínima {m['min']:.1f} px; textos < 12 px: {m['npeq']}; "
                f"controles < 24×24 px: {m['nchicos']} de {m['ninter']}")
        for x in m["peq"][:3]:
            ev.nota(f"   texto {x['fs']:.1f} px: '{x['t']}'")
        for x in m["chicos"][:3]:
            ev.nota(f"   control {x['w']}×{x['h']} px: '{x['t']}'")
    problemas = m_login["npeq"] + m_dash["npeq"] + m_login["nchicos"] + m_dash["nchicos"]
    ev.resultado(f"Fuente mínima {min(m_login['min'], m_dash['min']):.1f} px; "
                 f"{m_login['npeq'] + m_dash['npeq']} textos < 12 px y {m_login['nchicos'] + m_dash['nchicos']} controles < 24 px")
    assert problemas == 0, "Hay textos menores a 12 px o controles táctiles menores a 24×24 px"


# ---------------------------------------------------------------- NFR-USAB-2
@pytest.mark.caso("TC-NFR-06")
def test_flujo_registro_ui(ev, chromium):
    s = sufijo()
    usuario, clave = f"ui_{s}", CLAVE_QA
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page = ctx.new_page()
    t0 = time.perf_counter()
    page.goto(WEB + "/registro")
    page.get_by_test_id("input-registro-nombre-usuario").fill(usuario)
    page.get_by_test_id("input-registro-correo").fill(f"{usuario}@qa.test")
    page.get_by_test_id("input-registro-password").fill(clave)
    captura(page, "TC-NFR-06_paso1")
    page.get_by_test_id("button-registro-continuar").click()
    page.get_by_test_id("input-registro-nombre-empresa").fill(f"Empresa UI {s}")
    page.get_by_test_id("input-registro-calle").fill("Av. Matta 500")
    page.get_by_test_id("input-registro-comuna").fill("Santiago")
    page.get_by_test_id("input-registro-region").fill("Metropolitana")
    page.get_by_test_id("input-registro-telefono").fill("+56922223333")
    page.get_by_test_id("input-registro-correo-empresa").fill(f"empresa_{usuario}@qa.test")
    captura(page, "TC-NFR-06_paso2")
    page.get_by_test_id("button-registro-crear-cuenta").click()
    page.wait_for_url("**/login", timeout=20000)
    ev.nota("Paso 1 (usuario) y paso 2 (empresa) completados; redirección a /login con aviso de éxito")
    iniciar_sesion(page, usuario, clave)
    captura(page, "TC-NFR-06_dashboard")
    titulo = page.locator("body").inner_text()[:200].replace("\n", " | ")
    dur = time.perf_counter() - t0
    ev.nota(f"Dashboard visible tras el registro: '{titulo[:120]}…'")
    ev.resultado(f"Registro de 2 pasos + inicio de sesión completados en {dur:.1f} s y dashboard visible")
    ctx.close()
    assert "/login" not in page.url


# ---------------------------------------------------------------- NFR-USAB-3
@pytest.mark.caso("TC-NFR-07")
def test_mensajes_error_ui(ev, chromium):
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(WEB + "/registro")
    page.get_by_test_id("input-registro-nombre-usuario").fill("admin")
    page.get_by_test_id("input-registro-correo").fill(f"otro_{sufijo()}@qa.test")
    page.get_by_test_id("input-registro-password").fill(CLAVE_QA)
    page.get_by_test_id("button-registro-continuar").click()
    page.get_by_test_id("input-registro-nombre-empresa").fill("Empresa repetida")
    page.get_by_test_id("input-registro-calle").fill("Calle 1")
    page.get_by_test_id("input-registro-comuna").fill("Santiago")
    page.get_by_test_id("input-registro-region").fill("RM")
    page.get_by_test_id("input-registro-telefono").fill("+56911112222")
    page.get_by_test_id("input-registro-correo-empresa").fill(f"rep_{sufijo()}@qa.test")
    page.get_by_test_id("button-registro-crear-cuenta").click()
    toast = page.locator("[data-sonner-toast]").first
    toast.wait_for(timeout=15000)
    page.wait_for_timeout(400)
    texto = toast.inner_text().replace("\n", " | ")
    captura(page, "TC-NFR-07_toast")
    ctx.close()
    tecnico = any(t in texto.lower() for t in ("duplicate key", "violates", "constraint", "unique", "sql"))
    ev.nota(f"Mensaje mostrado al usuario: '{texto}'")
    ev.resultado(f"La interfaz muestra el error {'técnico de PostgreSQL' if tecnico else 'en lenguaje de negocio'}")
    assert not tecnico, "El mensaje de error expone términos técnicos de la base de datos al usuario"


# ---------------------------------------------------------------- NFR-USAB-4
@pytest.mark.caso("TC-NFR-08")
def test_flujo_cliente_contratos(ev, chromium):
    tok = login("admin", "admin")
    clientes = requests.get(f"{API}/clientes/search?name=", headers=h(tok)).json()
    objetivo = clientes[-1]
    r = requests.get(f"{API}/contratos", params={"cliente_id": objetivo["id"]}, headers=h(tok))
    ajenos = [c for c in r.json() if c["cliente_nombre"] != objetivo["nombre"]]
    ev.nota(f"GET /contratos?cliente_id={objetivo['id']} -> {len(r.json())} contratos, {len(ajenos)} de otros clientes (filtro ignorado)")
    ctx = chromium.new_context(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page = ctx.new_page()
    iniciar_sesion(page)
    with page.expect_response(lambda x: x.url.startswith(API) and x.url.endswith("/clientes"), timeout=30000):
        page.goto(WEB + "/clientes")
    page.wait_for_timeout(800)
    acciones = page.locator("table tbody tr").first.locator("button, a").all_inner_texts() if page.locator("table tbody tr").count() else []
    enlaces = page.get_by_text("contratos", exact=False).count()
    captura(page, "TC-NFR-08_clientes")
    ctx.close()
    ev.nota(f"Acciones disponibles en la fila del cliente: {acciones or '(iconos sin texto)'}; enlaces a contratos: {max(enlaces - 1, 0)}")
    ev.resultado("No existe navegación cliente → contratos y la API ignora el filtro por cliente")
    assert not ajenos and enlaces > 1, "No hay flujo escalonado cliente → contratos del cliente"


# ---------------------------------------------------------------- NFR-COMPAT-1
@pytest.mark.caso("TC-NFR-09")
def test_compatibilidad(ev, pw):
    motores = [("Chromium (Chrome)", pw.chromium, {}), ("Microsoft Edge", pw.chromium, {"channel": "msedge"}),
               ("Firefox", pw.firefox, {}), ("WebKit (Safari)", pw.webkit, {})]
    fallos = []
    for nombre, tipo, opts in motores:
        try:
            b = tipo.launch(**opts)
        except Exception as e:  # navegador no instalado
            ev.nota(f"{nombre:<18} no disponible: {str(e)[:60]}")
            fallos.append(f"{nombre} no disponible")
            continue
        page = b.new_page(viewport={"width": 1280, "height": 720})
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)[:80]))
        try:
            t0 = time.perf_counter()
            iniciar_sesion(page, timeout=40000)
            ok = page.get_by_text("Clientes").count() > 0
            ev.nota(f"{nombre:<18} v{b.version:<14} login + dashboard en {time.perf_counter()-t0:.1f} s; "
                    f"errores JS: {len(errores)}; menú visible: {ok}")
            page.screenshot(path=str(EVID / f"TC-NFR-09_{nombre.split()[0].lower()}.png"))
            if errores or not ok:
                fallos.append(nombre)
        except Exception as e:
            ev.nota(f"{nombre:<18} ERROR: {str(e)[:90]}")
            fallos.append(nombre)
        b.close()
    ev.resultado(f"Flujo completo en {len(motores) - len(fallos)} de {len(motores)} navegadores")
    assert not fallos, f"Problemas en: {', '.join(fallos)}"


# ---------------------------------------------------------------- NFR-COMPAT-2
@pytest.mark.caso("TC-NFR-10")
def test_responsivo(ev, chromium):
    tamanos = [("Móvil", 390, 844), ("Tablet", 768, 1024), ("Escritorio", 1366, 768)]
    desbordes = []
    ev.nota("Criterio: sin desplazamiento horizontal y sin textos visibles recortados fuera del viewport")
    ev.nota(f"{'VISTA':<11}{'Móvil':>14}{'Tablet':>14}{'Escritorio':>14}   (textos recortados · desborde)")
    filas = {"Login": [], "Dashboard": [], "Clientes": []}
    # scrollWidth no basta: con overflow:hidden el contenido se recorta sin generar desplazamiento.
    # Se cuentan los elementos con texto propio visibles cuyo borde derecho sale del viewport.
    medir = """() => {
      const vw = document.documentElement.clientWidth;
      // Un elemento dentro de un contenedor con scroll horizontal propio (p. ej. una tabla) sigue siendo alcanzable.
      const alcanzable = e => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
          const ox = getComputedStyle(a).overflowX;
          if ((ox === 'auto' || ox === 'scroll') && a.scrollWidth > a.clientWidth) return true; } return false; };
      const recortados = [...document.querySelectorAll('body *')].filter(e => {
        const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' &&
          [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1) &&
          (r.right > vw + 2 || r.left < -2) && !alcanzable(e);
      });
      return [document.documentElement.scrollWidth, vw, recortados.length,
              recortados.slice(0, 2).map(e => e.textContent.trim().slice(0, 24))];
    }"""
    for disp, w, hgt in tamanos:
        ctx = chromium.new_context(viewport={"width": w, "height": hgt}, device_scale_factor=2, is_mobile=w < 768, has_touch=w < 1024)
        page = ctx.new_page()
        page.goto(WEB + "/login")
        page.wait_for_load_state("networkidle")
        filas["Login"].append(tuple(page.evaluate(medir)))
        if disp != "Escritorio":
            captura(page, f"TC-NFR-10_login_{disp.lower()}")
        iniciar_sesion(page)
        filas["Dashboard"].append(tuple(page.evaluate(medir)))
        with page.expect_response(lambda r: r.url.startswith(API) and r.url.endswith("/clientes"), timeout=30000):
            page.goto(WEB + "/clientes")
        page.wait_for_timeout(600)
        filas["Clientes"].append(tuple(page.evaluate(medir)))
        if disp == "Móvil":
            captura(page, "TC-NFR-10_clientes_movil")
        ctx.close()
    ejemplos = []
    for vista, vals in filas.items():
        celdas = []
        for (sw, cw, rec, muestra), (disp, _, _) in zip(vals, tamanos):
            malo = sw > cw + 1 or rec > 0
            celdas.append(f"{rec} · {'sí' if sw > cw + 1 else 'no'}{' ✗' if malo else ' ✓'}")
            if malo:
                desbordes.append(f"{vista} en {disp}")
                ejemplos += [f"{vista}/{disp}: '{m}'" for m in muestra[:1]]
        ev.nota(f"{vista:<11}" + "".join(f"{c:>14}" for c in celdas))
    for e in ejemplos[:4]:
        ev.nota(f"  texto recortado -> {e}")
    ev.resultado(f"Contenido recortado en: {', '.join(desbordes) or 'ninguna combinación'}"
                 + (" (el menú lateral no se colapsa en pantallas pequeñas)" if desbordes else ""))
    assert not desbordes, f"Contenido recortado o desbordado en {', '.join(desbordes)}"

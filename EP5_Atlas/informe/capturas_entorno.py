"""Figuras del entorno y de la automatización para el informe (todas a partir de salidas reales).

ENT_01 Entorno Docker levantado (docker compose ps / images / respuesta de los servicios).
ENT_02 Consola de la ejecución oficial de run_todo.ps1 (extracto literal del log, con líneas omitidas indicadas).
ENT_03 Reporte HTML de pytest (suite de API).
ENT_04 Reporte HTML de OWASP ZAP (frontend).
ENT_05 Registro en dos pasos (TC-NFR-06) y ENT_06 Atlas en 4 navegadores (TC-NFR-09).
"""
import datetime as dt
import html
import pathlib
import re
import shutil
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).resolve().parents[1]
REPO = BASE.parent / "CodigoFuenteA"
EVID, REP = BASE / "evidencias", BASE / "reportes"
DOCKER = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"

CSS = """
body{margin:0;background:#fff;font-family:Arial,sans-serif;width:920px}
.win{margin:6px;border-radius:10px;overflow:hidden;border:1px solid #2d333b}
.bar{background:#2d333b;color:#e6edf3;padding:9px 14px;font-size:16px}
.bar b{font-size:17px}.dots span{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}
pre{margin:0;background:#012456;color:#eeedf0;font-family:Consolas,'Courier New',monospace;font-size:15.5px;line-height:1.4;
    padding:12px 16px;white-space:pre-wrap;word-break:break-word}
.cmd{color:#ffffff;font-weight:bold}.st{color:#61d6d6;font-weight:bold}.ok{color:#7ee787}.err{color:#ff7b72}
.dim{color:#9fb3c8}.t{color:#f2cc60}
.foot{background:#161b22;color:#8b949e;font-size:13px;padding:6px 16px}
"""


def correr(*args, timeout=120):
    r = subprocess.run([DOCKER, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=REPO)
    return (r.stdout + r.stderr).rstrip()


def terminal(page, salida, titulo, lineas_html, pie):
    doc = f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="win">
    <div class="bar"><span class="dots"><span style="background:#ff5f56"></span><span style="background:#ffbd2e"></span>
    <span style="background:#27c93f"></span></span><b>{html.escape(titulo)}</b></div>
    <pre>{lineas_html}</pre><div class="foot">{html.escape(pie)}</div></div></body></html>"""
    page.set_content(doc)
    page.locator(".win").screenshot(path=str(EVID / salida))


def e(t, cls=None):
    t = html.escape(t)
    return f'<span class="{cls}">{t}</span>' if cls else t


def ent01(page):
    ahora = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    ps = correr("compose", "ps", "--format", "table {{.Name}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}")
    ps = re.sub(r", \[::\]:\d+->\d+/tcp", "", ps)
    imgs = correr("images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}")
    imgs = "\n".join(l for l in imgs.splitlines() if l.startswith(("REPOSITORY", "atlas", "postgres")))
    api = requests.get("http://localhost:4450/", timeout=10)
    web = requests.get("http://localhost:3350/", timeout=10)
    out = [e("PS CodigoFuenteA> docker compose ps", "cmd")] + [e(l) for l in ps.splitlines()]
    out += ["", e("PS CodigoFuenteA> docker images", "cmd")] + [e(l) for l in imgs.splitlines()]
    out += ["", e("PS CodigoFuenteA> curl http://localhost:4450/   (API Express)", "cmd"),
            e(f"HTTP {api.status_code}  {api.text.strip()}", "ok"),
            e("PS CodigoFuenteA> curl http://localhost:3350/   (frontend React servido por Nginx)", "cmd"),
            e(f"HTTP {web.status_code}  {len(web.content)} bytes · Server: {web.headers.get('Server', '-')}", "ok")]
    terminal(page, "ENT_01_docker.png", "Entorno de pruebas: Atlas levantado con Docker Compose", "\n".join(out),
             f"Capturado el {ahora} · {correr('compose', 'version')}")


def ent02(page):
    log = (REP / "ejecucion_completa.log").read_text(encoding="utf-8-sig")
    log = re.sub(r"\x1b\[[0-9;]*m", "", log).replace("\r", "").splitlines()
    claves = re.compile(r"^=== |^ +\d+,\d+ s$|^\d+ (failed|passed)|passed in|failed in|✗ 'p\(95\)|✓ 'rate|"
                        r"http_req_duration\.\.|^Resultados:|^Name +Value|^-{4}|^(SAST|Secretos|SCA|IaC|DAST|Carga|API|Interfaz|Disponibilidad) ")
    out = [e("PS EP5_Atlas> powershell -ExecutionPolicy Bypass -File .\\run_todo.ps1", "cmd")]
    omitidas = 0
    for linea in log:
        if not linea.strip():
            continue
        if claves.search(linea):
            if omitidas:
                out.append(e(f"   [... {omitidas} líneas de detalle omitidas ...]", "dim"))
                omitidas = 0
            l = linea.replace("C:\\Users\\memos\\Documents\\GitHub\\formaB\\CodigoFuenteA\\", "")
            cls = "st" if l.startswith("===") else "t" if re.match(r"^ +\d+,\d+ s$", l) else \
                  "err" if ("failed" in l or "✗" in l) else "ok" if ("passed" in l or "✓" in l) else None
            out.append(e(l[:110], cls))
        else:
            omitidas += 1
    terminal(page, "ENT_02_consola.png", "Ejecución oficial de la batería con un solo comando (run_todo.ps1)", "\n".join(out),
             "Extracto literal de reportes/ejecucion_completa.log; se omiten las trazas de detalle de cada prueba")


def captura_html(page, archivo, salida, alto, preparar=None):
    page.set_viewport_size({"width": 1150, "height": alto})
    page.goto(archivo.resolve().as_uri())
    page.wait_for_timeout(1500)
    if preparar:
        preparar(page)
        page.wait_for_timeout(500)
    page.screenshot(path=str(EVID / salida))


def compuesta(rutas, etiquetas, salida, columnas, ancho_celda):
    ims = [Image.open(r).convert("RGB") for r in rutas]
    ims = [im.resize((ancho_celda, int(im.height * ancho_celda / im.width))) for im in ims]
    alto = max(im.height for im in ims)
    filas = (len(ims) + columnas - 1) // columnas
    pad, cab = 16, 46
    lienzo = Image.new("RGB", (columnas * (ancho_celda + pad) + pad, filas * (alto + cab + pad) + pad), "white")
    d = ImageDraw.Draw(lienzo)
    try:
        f = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        f = ImageFont.load_default()
    for i, (im, et) in enumerate(zip(ims, etiquetas)):
        x = pad + (i % columnas) * (ancho_celda + pad)
        y = pad + (i // columnas) * (alto + cab + pad)
        d.text((x, y + 6), et, fill=(16, 42, 67), font=f)
        lienzo.paste(im, (x, y + cab))
        d.rectangle([x, y + cab, x + im.width - 1, y + cab + im.height - 1], outline=(197, 204, 211), width=2)
    lienzo.save(EVID / salida)


if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 920, "height": 400}, device_scale_factor=2)
        ent01(page)
        ent02(page)
        pg2 = b.new_page(device_scale_factor=1.5)
        captura_html(pg2, REP / "reporte_api.html", "ENT_03_pytest_html.png", 1350,
                     lambda pg: pg.get_by_text("Hide all details").click())  # tabla de resultados sin el código
        captura_html(pg2, REP / "zap_frontend.html", "ENT_04_zap_html.png", 1150)
        b.close()
    compuesta([EVID / "TC-NFR-06_paso1.png", EVID / "TC-NFR-06_paso2.png", EVID / "TC-NFR-06_dashboard.png"],
              ["1. Datos del usuario", "2. Datos de la empresa", "3. Dashboard tras iniciar sesión"],
              "ENT_05_registro.png", 3, 1100)
    compuesta([EVID / "TC-NFR-09_chromium.png", EVID / "TC-NFR-09_microsoft.png",
               EVID / "TC-NFR-09_firefox.png", EVID / "TC-NFR-09_webkit.png"],
              ["Chromium (Chrome)", "Microsoft Edge", "Firefox", "WebKit (Safari)"],
              "ENT_06_navegadores.png", 2, 1280)
    print("figuras de entorno generadas")

"""Convierte evidencias/<ID>.txt (transcripciones reales de la suite) en figuras PNG tipo terminal."""
import html
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pruebas"))
from catalogo import POR_ID  # noqa: E402

EVID = BASE / "evidencias"
RES = json.loads((BASE / "reportes" / "resultados.json").read_text(encoding="utf-8"))

CSS = """
body{margin:0;background:#fff;font-family:Arial,sans-serif;width:920px}
.win{margin:6px;border-radius:10px;overflow:hidden;border:1px solid #2d333b;box-shadow:0 2px 6px rgba(0,0,0,.25)}
.bar{background:#2d333b;color:#e6edf3;padding:9px 14px;font-size:16px;display:flex;justify-content:space-between;align-items:center}
.bar b{font-size:17px}.dots span{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}
.est{font-weight:bold;padding:2px 10px;border-radius:9px;font-size:14px}
.PASO{background:#1b6b3a;color:#fff}.FALLO{background:#b42318;color:#fff}.BLOQ{background:#8a6d00;color:#fff}
pre{margin:0;background:#0d1117;color:#e6edf3;font-family:Consolas,'Courier New',monospace;font-size:16.5px;line-height:1.4;
    padding:12px 16px;white-space:pre-wrap;word-break:break-word}
.req{color:#79c0ff}.ok{color:#56d364}.err{color:#ff7b72}.cmt{color:#8b949e}.res{color:#f2cc60;font-weight:bold}.body{color:#c9d1d9}
.foot{background:#161b22;color:#8b949e;font-size:13px;padding:6px 16px;font-family:Arial}
"""


def colorear(linea: str) -> str:
    e = html.escape(linea)
    if linea.startswith("=>"):
        return f'<span class="res">{e}</span>'
    if linea.startswith(">"):
        return f'<span class="req">{e}</span>'
    if linea.startswith("< HTTP"):
        codigo = int(linea.split()[2]) if linea.split()[2].isdigit() else 0
        return f'<span class="{"err" if codigo >= 400 else "ok"}">{e}</span>'
    if linea.startswith("#") or linea.startswith("$"):
        return f'<span class="cmt">{e}</span>'
    return f'<span class="body">{e}</span>'


def render(page, caso_id):
    txt = (EVID / f"{caso_id}.txt").read_text(encoding="utf-8")
    c, r = POR_ID[caso_id], RES.get(caso_id, {})
    est = r.get("estado", "SIN DATO")
    cls = {"PASÓ": "PASO", "FALLÓ": "FALLO"}.get(est, "BLOQ")
    lineas = "\n".join(colorear(l) for l in txt.splitlines())
    doc = f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="win">
    <div class="bar"><div><span class="dots"><span style="background:#ff5f56"></span><span style="background:#ffbd2e"></span>
    <span style="background:#27c93f"></span></span><b>{caso_id}</b> · {html.escape(c['nombre'])}</div><span class="est {cls}">{est}</span></div>
    <pre>{lineas}</pre><div class="foot">Ejecución automatizada · {r.get('fecha', '')} · {html.escape(r.get('test', ''))} · {c['herramienta']}</div>
    </div></body></html>"""
    page.set_content(doc)
    page.locator(".win").screenshot(path=str(EVID / f"{caso_id}.png"))


if __name__ == "__main__":
    ids = [p.stem for p in sorted(EVID.glob("TC-*.txt"))]
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 920, "height": 400}, device_scale_factor=2)
        for i in ids:
            render(page, i)
        b.close()
    print(f"{len(ids)} evidencias renderizadas")

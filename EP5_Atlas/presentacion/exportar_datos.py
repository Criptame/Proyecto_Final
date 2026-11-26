"""Exporta a datos_deck.json las cifras reales que usa la presentación (sin valores escritos a mano)."""
import json
import pathlib
import re
import sys
from collections import Counter

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pruebas"))
sys.path.insert(0, str(BASE / "informe"))
from catalogo import CASOS, POR_ID  # noqa: E402
from cvss import puntaje  # noqa: E402
import generar_informe as gi  # noqa: E402

H = gi.herramientas()
RES = gi.RES
est = Counter(RES[c["id"]]["estado"] for c in CASOS)
por_tipo = {p: Counter(RES[c["id"]]["estado"] for c in CASOS if c["id"].startswith(p)) for p in ("TC-FUN", "TC-SEC", "TC-NFR")}

inc = []
for c in CASOS:
    if RES[c["id"]]["estado"] != "FALLÓ":
        continue
    sev, base = gi.criticidad(c)
    inc.append({"id": c["id"], "nombre": c["nombre"], "sev": sev, "base": base,
                "cvss": puntaje(c["cvss"]) if c.get("cvss") else None})
sev = Counter(i["sev"] for i in inc)
criticos = sorted([i for i in inc if i["sev"] == "Crítica"], key=lambda x: -(x["cvss"] or 0))

semgrep = H["semgrep_reglas"]
datos = {
    "total": len(CASOS), "paso": est.get("PASÓ", 0), "fallo": est.get("FALLÓ", 0), "bloqueado": est.get("BLOQUEADO", 0),
    "por_tipo": {k: dict(v) for k, v in por_tipo.items()},
    "severidad": dict(sev), "criticos": criticos,
    "tiempos": gi.TIEMPOS, "total_min": round(sum(gi.TIEMPOS.values()) / 60, 1),
    "crud": {k: v["p95"] for k, v in H["crud"].items()},
    "k6": H.get("k6", {}),
    "movil": H.get("movil", {}),
    "axe_serias": sum(c.get("critical", 0) + c.get("serious", 0) for c in H["axe"].values()),
    "semgrep_total": H["semgrep_total"], "semgrep_publicas": H["semgrep_publicas"], "semgrep_propias": H["semgrep_propias"],
    "semgrep_error": H["semgrep_sev"].get("ERROR", 0), "semgrep_reglas_propias": sum(1 for r in semgrep if r.startswith("atlas-")),
    "gitleaks": len(H["gitleaks"]),
    "npm": H["npm"], "trivy": dict(H["trivy_sev"]), "trivy_conf": len(H["trivy_conf"]),
    "zap": {k: Counter(r for r, _, _ in v) for k, v in H["zap"].items()},
    "obtenido": {c["id"]: RES[c["id"]]["obtenido"] for c in CASOS},
    "fecha": sorted(v["fecha"] for v in RES.values())[0][:10],
    "portada": gi.PORTADA,
}
sys.path.insert(0, str(BASE / "diagramas"))
import generar_diagramas as gd  # noqa: E402

ui = BASE / "evidencias" / "TC-SEC-09_ui.json"
sin_dialogos = ui.exists() and not json.loads(ui.read_text(encoding="utf-8"))["dialogos"]
capas = []
for capa, _, ctrls in gd.CAPAS:
    ok = []
    for nombre, _, casos, es_ui in ctrls:
        cls = ("ok" if sin_dialogos else "ko") if es_ui else gd.estado(*casos)[0]
        if cls == "ok":
            ok.append(nombre)
    capas.append({"capa": capa, "ok": len(ok), "total": len(ctrls), "verificados": ok})
datos["capas"] = capas
rec = re.search(r"([\d.]+) s", RES["TC-NFR-11"]["obtenido"])
datos["recuperacion_s"] = float(rec.group(1)) if rec else None
(BASE / "presentacion" / "datos_deck.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
print(json.dumps({k: datos[k] for k in ("total", "paso", "fallo", "severidad", "total_min", "crud", "axe_serias",
                                         "semgrep_total", "gitleaks", "recuperacion_s")}, ensure_ascii=False))
print([(c["id"], c["cvss"], c["base"]) for c in criticos])
print(datos["k6"], datos["npm"], datos["trivy"], datos["zap"])

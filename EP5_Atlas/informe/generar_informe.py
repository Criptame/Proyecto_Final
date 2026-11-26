"""Genera el informe EP5 (Word) a partir del catálogo de casos y de los resultados REALES de la ejecución.

Formato exigido por la pauta: títulos Arial 12, cuerpo Arial 11, interlineado 1,5, texto justificado,
portada con integrante, carrera, sección, docente y fecha. Los datos de portada se leen de datos_portada.json.
"""
import datetime as dt
import json
import pathlib
import re
import sys
from collections import Counter, OrderedDict

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "pruebas"))
from catalogo import CASOS, POR_ID  # noqa: E402
from cvss import puntaje, severidad  # noqa: E402

REP, EVID, DIAG = BASE / "reportes", BASE / "evidencias", BASE / "diagramas"


def jload(nombre, defecto=None):
    p = REP / nombre
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() and p.stat().st_size else defecto


RES = jload("resultados.json", {})
TIEMPOS = jload("tiempos_etapas.json", {})
PORTADA = json.loads((BASE / "informe" / "datos_portada.json").read_text(encoding="utf-8"))
VERSIONES = jload("versiones.json", {})

AZUL = RGBColor(0x1F, 0x38, 0x64)
GRIS_TABLA = "D9E2F3"
COLOR_ESTADO = {"PASÓ": "E2F0D9", "FALLÓ": "FBE5E5", "BLOQUEADO": "FFF2CC"}
COLOR_SEV = {"Crítica": "F4B6B6", "Alta": "F8D3C0", "Media": "FFF2CC", "Baja": "E2F0D9"}


def est(cid):
    return RES.get(cid, {}).get("estado", "SIN EJECUTAR")


def obtenido(cid):
    return RES.get(cid, {}).get("obtenido", "")


def criticidad(c):
    """Criticidad del caso: CVSS v3.1 para seguridad; impacto en el negocio para el resto."""
    if c.get("cvss"):
        s = puntaje(c["cvss"])
        return severidad(s), f"CVSS {s:.1f}"
    if c["id"].startswith("TC-SEC"):
        mapa = {"TC-SEC-15": "Alta", "TC-SEC-21": "Crítica", "TC-SEC-22": "Alta", "TC-SEC-23": "Crítica", "TC-SEC-24": "Media"}
        return mapa.get(c["id"], "Media"), "Herramienta"
    return c.get("criticidad", "Media"), "Impacto"


# ============================================================== utilidades de formato
def fuente_run(run, size=None, bold=None, italic=None, color=None, nombre="Arial"):
    run.font.name = nombre
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), nombre)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def estilo_fuente(estilo, nombre="Arial", size=11, bold=None, italic=None, color=None):
    estilo.font.name = nombre
    estilo.font.size = Pt(size)
    if bold is not None:
        estilo.font.bold = bold
    if italic is not None:
        estilo.font.italic = italic
    if color is not None:
        estilo.font.color.rgb = color
    rpr = estilo.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in list(rfonts.attrib):
        if a.endswith("Theme"):
            del rfonts.attrib[a]
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), nombre)


def sombrear(celda, color):
    tcpr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def repetir_encabezado(fila):
    trpr = fila._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def no_dividir(fila):
    trpr = fila._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def campo(parrafo, instruccion, texto="1"):
    r = parrafo.add_run()
    for tipo, val in (("begin", None), ("instr", instruccion), ("separate", None), ("text", texto), ("end", None)):
        if tipo == "instr":
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = val
            r._element.append(it)
        elif tipo == "text":
            t = OxmlElement("w:t")
            t.text = val
            r._element.append(t)
        else:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), tipo)
            r._element.append(fc)
    return r


class Informe:
    def __init__(self):
        self.doc = Document()
        self.fig = 0
        self.tab = 0
        self._estilos()
        s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21.59), Cm(27.94)  # Carta
        s.left_margin = s.right_margin = Cm(2.5)
        s.top_margin = s.bottom_margin = Cm(2.5)
        s.different_first_page_header_footer = True
        self._encabezado_pie(s)

    # ---------------------------------------------------------- estilos
    def _estilos(self):
        st = self.doc.styles
        n = st["Normal"]
        estilo_fuente(n, size=11)
        pf = n.paragraph_format
        pf.line_spacing = 1.5
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.space_after = Pt(6)
        pf.space_before = Pt(0)
        for i in (1, 2, 3):
            h = st[f"Heading {i}"]
            estilo_fuente(h, size=12, bold=True, italic=False, color=AZUL)
            h.paragraph_format.line_spacing = 1.5
            h.paragraph_format.space_before = Pt(12 if i == 1 else 8)
            h.paragraph_format.space_after = Pt(4)
            h.paragraph_format.keep_with_next = True
            h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cap = st["Caption"]
        estilo_fuente(cap, size=10, bold=False, italic=True, color=RGBColor(0x26, 0x26, 0x26))
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(10)
        cap.paragraph_format.line_spacing = 1.15
        for nombre in ("List Bullet", "List Number", "List Bullet 2"):
            estilo_fuente(st[nombre], size=11)
            st[nombre].paragraph_format.line_spacing = 1.5
            st[nombre].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            st[nombre].paragraph_format.space_after = Pt(3)
        for nombre in ("TOC 1", "TOC 2", "TOC 3"):
            try:
                estilo_fuente(st[nombre], size=11)
            except KeyError:
                pass

    def _encabezado_pie(self, s):
        hp = s.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = hp.add_run("ISY1102 · Evaluación Parcial N.º 5 · Sistema de Gestión Atlas (Caso A)")
        fuente_run(r, size=9, color=RGBColor(0x59, 0x59, 0x59))
        fp = s.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run("Página ")
        fuente_run(r, size=9)
        fuente_run(campo(fp, "PAGE"), size=9)

    # ---------------------------------------------------------- bloques
    def h(self, nivel, texto):
        return self.doc.add_heading(texto, level=nivel)

    def p(self, texto, estilo=None, align=None, size=None, space_after=None):
        par = self.doc.add_paragraph(style=estilo)
        if align is not None:
            par.alignment = align
        if space_after is not None:
            par.paragraph_format.space_after = Pt(space_after)
        for i, trozo in enumerate(re.split(r"\*\*", texto)):
            if trozo:
                r = par.add_run(trozo)
                fuente_run(r, size=size, bold=(i % 2 == 1))
        return par

    def bullets(self, items, estilo="List Bullet"):
        for it in items:
            self.p(it, estilo=estilo)

    def salto(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def figura(self, ruta, titulo, ancho=16.0, fuente_txt=None):
        ruta = pathlib.Path(ruta)
        if not ruta.exists():
            self.p(f"[Figura no disponible: {ruta.name}]")
            return
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.keep_with_next = True
        par.paragraph_format.line_spacing = 1.0
        par.paragraph_format.space_after = Pt(2)
        par.add_run().add_picture(str(ruta), width=Cm(ancho))
        self.fig += 1
        cap = self.doc.add_paragraph(style="Caption")
        r = cap.add_run(f"Figura {self.fig}. {titulo}")
        fuente_run(r, size=10, italic=True)
        if fuente_txt:
            r2 = cap.add_run(f" Fuente: {fuente_txt}.")
            fuente_run(r2, size=10, italic=True)
        return self.fig

    def tabla(self, encabezados, filas, anchos, titulo=None, size=9, colores=None, negrita_col0=False, juntas=False):
        if titulo:
            self.tab += 1
            cap = self.doc.add_paragraph(style="Caption")
            cap.paragraph_format.keep_with_next = True
            cap.paragraph_format.space_after = Pt(4)
            r = cap.add_run(f"Tabla {self.tab}. {titulo}")
            fuente_run(r, size=10, italic=True)
        t = self.doc.add_table(rows=1, cols=len(encabezados))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        tblpr = t._tbl.tblPr
        lay = OxmlElement("w:tblLayout")
        lay.set(qn("w:type"), "fixed")
        tblpr.append(lay)
        for i, e in enumerate(encabezados):
            c = t.rows[0].cells[i]
            c.width = Cm(anchos[i])
            sombrear(c, GRIS_TABLA)
            self._texto_celda(c, e, size, bold=True)
            for par in c.paragraphs:  # el encabezado nunca queda solo al pie de una página
                par.paragraph_format.keep_with_next = True
        repetir_encabezado(t.rows[0])
        for fi, fila in enumerate(filas):
            cells = t.add_row().cells
            no_dividir(t.rows[-1])
            for i, v in enumerate(fila):
                cells[i].width = Cm(anchos[i])
                self._texto_celda(cells[i], str(v), size, bold=(negrita_col0 and i == 0))
                if colores and colores(fi, i, v):
                    sombrear(cells[i], colores(fi, i, v))
        if juntas:  # mantiene la tabla completa en una misma página
            for fila in t.rows[:-1]:
                for celda in fila.cells:
                    for par in celda.paragraphs:
                        par.paragraph_format.keep_with_next = True
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    def _texto_celda(self, celda, texto, size, bold=False):
        celda.paragraphs[0].text = ""
        lineas = texto.split("\n")
        for k, linea in enumerate(lineas):
            par = celda.paragraphs[0] if k == 0 else celda.add_paragraph()
            par.paragraph_format.line_spacing = 1.0
            par.paragraph_format.space_after = Pt(1)
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for j, trozo in enumerate(re.split(r"\*\*", linea)):
                if trozo:
                    r = par.add_run(trozo)
                    fuente_run(r, size=size, bold=bold or (j % 2 == 1))

    def codigo(self, texto, titulo=None):
        if titulo:
            self.p(titulo, space_after=2)
        for linea in texto.strip("\n").split("\n"):
            par = self.doc.add_paragraph()
            par.paragraph_format.line_spacing = 1.0
            par.paragraph_format.space_after = Pt(0)
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            ppr = par._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "F2F4F7")
            ppr.append(shd)
            r = par.add_run(linea if linea else " ")
            fuente_run(r, size=8.5, nombre="Consolas")
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def guardar(self, ruta):
        self.doc.save(ruta)


def color_estado(fi, i, v):
    return COLOR_ESTADO.get(v)


# ============================================================== datos derivados
def contar(prefijo=None):
    c = Counter(est(x["id"]) for x in CASOS if prefijo is None or x["id"].startswith(prefijo))
    return c


def herramientas():
    d = {}
    sg = jload("semgrep.json", {})
    res = sg.get("results", [])
    propias = [r for r in res if "atlas-" in r["check_id"]]
    d["semgrep_total"] = len(res)
    d["semgrep_publicas"] = len(res) - len(propias)
    d["semgrep_propias"] = len(propias)
    d["semgrep_reglas"] = Counter(r["check_id"].split(".")[-1] for r in res)
    d["semgrep_sev"] = Counter(r["extra"]["severity"] for r in res)
    d["semgrep_version"] = sg.get("version", "")
    d["semgrep_ej"] = {}
    for r in res:
        regla = r["check_id"].split(".")[-1]
        d["semgrep_ej"].setdefault(regla, f"{r['path'].removeprefix('/src/')}:{r['start']['line']}")
    gl = jload("gitleaks.json", [])
    d["gitleaks"] = [(x["RuleID"], x["File"].removeprefix("/src/"), x["StartLine"]) for x in gl]
    d["npm"] = {}
    d["npm_top"] = []
    for p in ("backend", "frontend"):
        a = jload(f"npm_audit_{p}.json", {})
        d["npm"][p] = a.get("metadata", {}).get("vulnerabilities", {})
        for nombre, v in a.get("vulnerabilities", {}).items():
            if v.get("severity") in ("critical", "high") and v.get("isDirect"):
                tit = next((x.get("title", "") for x in v.get("via", []) if isinstance(x, dict)), "")
                d["npm_top"].append((p, nombre, v["severity"], tit, v.get("range", "")))
    tf = jload("trivy_fs.json", {})
    vulns = [v for r in tf.get("Results", []) for v in (r.get("Vulnerabilities") or [])]
    d["trivy_sev"] = Counter(v["Severity"] for v in vulns)
    d["trivy_ej"] = sorted({(v["PkgName"], v["InstalledVersion"], v["VulnerabilityID"], v["Severity"], v.get("FixedVersion", ""))
                            for v in vulns if v["Severity"] == "CRITICAL"})[:6]
    tc = jload("trivy_config.json", {})
    d["trivy_conf"] = [(r["Target"], m["Severity"], m["ID"], m["Title"]) for r in tc.get("Results", [])
                       for m in (r.get("Misconfigurations") or []) if m.get("Status") == "FAIL"]
    d["zap"] = {}
    riesgo = {"3": "Alto", "2": "Medio", "1": "Bajo", "0": "Informativo"}
    for o in ("frontend", "api"):
        z = jload(f"zap_{o}.json", {})
        al = [a for s in z.get("site", []) for a in s.get("alerts", [])]
        d["zap"][o] = [(riesgo[a["riskcode"]], a["name"], a.get("cweid", "")) for a in sorted(al, key=lambda x: -int(x["riskcode"]))]
        d["zap_version"] = z.get("@version", "")
    k6 = jload("k6_resumen.json", {})
    if k6:
        m = k6["metrics"]
        v = lambda k: m[k].get("values", m[k])  # noqa: E731
        d["k6"] = {"p95": v("http_req_duration")["p(95)"], "p50": v("http_req_duration")["med"],
                   "max": v("http_req_duration")["max"], "err": v("http_req_failed").get("rate", v("http_req_failed").get("value", 0)),
                   "reqs": v("http_reqs")["count"], "rps": v("http_reqs")["rate"], "vus": v("vus_max")["max"]}
    d["crud"] = jload("rendimiento_crud.json", {})
    d["movil"] = jload("carga_movil.json", {})
    axe = jload("axe.json", {})
    d["axe"] = {vista: Counter(x["impact"] for x in viol) for vista, viol in axe.items()}
    return d


# ============================================================== contenido
def portada(inf: Informe):
    doc = inf.doc
    logo = BASE / "informe" / "logo_duoc.png"
    if logo.exists():
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(logo), width=Cm(6))
    for _ in range(3):
        doc.add_paragraph()
    for texto, sz, b in (("INFORME DE SEGURIDAD Y CALIDAD EN EL DESARROLLO DE SOFTWARE", 12, True),
                         ("Optimizando el aseguramiento de la calidad y seguridad del software", 12, False),
                         ("Iteración final: pruebas de seguridad, automatización, mitigación y mantenimiento", 12, False),
                         ("Sistema de Gestión Atlas (Caso A)", 12, True)):
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fuente_run(par.add_run(texto), size=sz, bold=b)
    doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fuente_run(par.add_run("ISY1102 · Seguridad y Calidad en el Desarrollo de Software"), size=11)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fuente_run(par.add_run("Evaluación Parcial N.º 5 · Encargo"), size=11)
    for _ in range(3):
        doc.add_paragraph()
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for etiqueta, clave in (("Integrante", "integrante"), ("Carrera", "carrera"), ("Sección", "seccion"),
                            ("Docente", "docente"), ("Fecha de entrega", "fecha_entrega")):
        c = t.add_row().cells
        c[0].width, c[1].width = Cm(4.5), Cm(9)
        fuente_run(c[0].paragraphs[0].add_run(etiqueta), size=11, bold=True)
        r = c[1].paragraphs[0].add_run(PORTADA[clave])
        fuente_run(r, size=11)
        if PORTADA[clave].startswith("["):
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        for cc in c:
            cc.paragraphs[0].paragraph_format.line_spacing = 1.5
            cc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    inf.salto()


def indice(inf: Informe):
    par = inf.doc.add_paragraph()
    fuente_run(par.add_run("Índice"), size=12, bold=True, color=AZUL)
    par = inf.doc.add_paragraph()
    campo(par, 'TOC \\o "1-3" \\h \\z \\u', "Haga clic derecho y seleccione «Actualizar campo» para generar el índice.")
    inf.salto()


def cap1(inf: Informe, H):
    total = len(CASOS)
    inf.h(1, "1. Introducción")
    inf.h(2, "1.1 Contexto del sistema")
    inf.p("El Sistema de Gestión Atlas (Caso A), desarrollado por CreaLab SpA, es una plataforma web multiempresa "
          "orientada a pymes chilenas que permite gestionar clientes, contratos y sus documentos, administrar usuarios con "
          "roles (administrador y editor) y registrar la auditoría de las acciones. Cada empresa debe acceder únicamente a sus "
          "propios datos (RB-2), y los clientes incluyen datos personales y bancarios —RUT, correo, teléfono, banco, número y "
          "titular de cuenta—, por lo que una falla de seguridad no sólo afecta la calidad del producto, sino también derechos "
          "de las personas protegidos por la ley.")
    inf.p("Técnicamente, Atlas es una aplicación de tres capas: una SPA en React 19 con Material UI y Tailwind, una API REST "
          "en Node.js con Express 4, pg y jsonwebtoken, y una base de datos PostgreSQL 15, desplegadas en tres contenedores "
          "mediante Docker Compose. El propio software advierte que contiene errores introducidos de manera intencional con "
          "fines académicos y que no debe utilizarse en producción; por ello, todo el trabajo se realizó como una auditoría "
          "controlada en un entorno local aislado.")
    inf.h(2, "1.2 Propósito")
    inf.p("Este informe corresponde a la iteración final del aseguramiento de la calidad de Atlas. Su propósito es "
          "ejecutar pruebas de seguridad con distintos enfoques y herramientas, automatizar las pruebas funcionales y no "
          "funcionales para optimizar tiempo y recursos, representar mediante diagramas la integración de controles de "
          "seguridad automatizados, proponer mitigaciones a cada defecto identificado y evaluar un plan de mantenimiento que "
          "preserve la calidad, la seguridad y el cumplimiento normativo y legal en futuras iteraciones del software.")
    inf.h(2, "1.3 Alcance y limitaciones")
    inf.p(f"Se verificaron la API (19 rutas documentadas en OpenAPI), la interfaz web, la base de datos, la configuración "
          f"de los contenedores y las dependencias de terceros, mediante {total} casos de prueba automatizados que cubren el "
          f"100 % de los requerimientos del ERS (RF-1 a RF-6, RB-1 a RB-5, NFR y requisitos de interfaz). Se reconocen las "
          f"siguientes limitaciones, declaradas para no sobreestimar los resultados:")
    inf.bullets([
        "**Usabilidad con usuarios reales:** el ERS pide pruebas con cinco adultos mayores. Ese ensayo requiere participantes "
        "y no puede automatizarse; se sustituyó por mediciones objetivas (axe-core, tamaño de fuente, objetivos táctiles, "
        "flujo E2E) y se recomienda ejecutarlo antes del paso a producción.",
        "**DAST sólo pasivo:** OWASP ZAP se ejecutó en modo baseline. Un escaneo activo habría enviado peticiones DELETE "
        "a endpoints que no exigen autenticación (TC-SEC-06) y habría destruido datos; se privilegió una decisión ética y "
        "controlada, y los ataques activos se realizaron de forma dirigida con scripts propios sobre datos creados por la suite.",
        "**Disponibilidad mensual (99,5 %):** no es medible en un laboratorio; se verificaron los mecanismos que la sostienen "
        "(reinicio automático, healthcheck y tiempo de recuperación ante un corte de la base de datos).",
        "**Ambiente:** las mediciones de rendimiento corresponden a un equipo local y sirven para comparar contra los umbrales "
        "del ERS, no para dimensionar producción.",
    ])
    inf.h(2, "1.4 Objetivos")
    inf.p("**Objetivo general:** optimizar el aseguramiento de la calidad y la seguridad de Atlas mediante pruebas de "
          "seguridad y pruebas automatizadas ejecutadas sobre el software real, documentando hallazgos, mitigaciones y un plan "
          "de mantenimiento alineado con estándares técnicos y con la legislación chilena.")
    inf.p("**Objetivos específicos:**", space_after=2)
    inf.bullets([
        "Reconocer los principales enfoques y herramientas de pruebas de seguridad y demostrar su función en la detección "
        "de vulnerabilidades con hallazgos concretos de Atlas (IL 3.1).",
        "Diseñar diagramas que integren controles de seguridad automatizados y su verificación normativa y legal (IL 3.2).",
        "Aplicar herramientas de automatización para diseñar y ejecutar casos de prueba, cuantificando el ahorro de tiempo y "
        "recursos (IL 3.3).",
        "Evaluar un plan de mantenimiento que preserve la calidad, la seguridad y el cumplimiento durante el ciclo de vida (IL 3.4).",
        "Documentar y comunicar los resultados de la automatización y de la mejora continua con evidencia verificable (IL 3.5).",
    ])
    inf.h(2, "1.5 Estructura del informe")
    inf.p("El capítulo 2 define los criterios de calidad, seguridad y cumplimiento; el 3 presenta los enfoques y herramientas "
          "de pruebas de seguridad; el 4 retoma y consolida el plan de pruebas y el diseño de casos; el 5 describe la "
          "automatización y su impacto; el 6 contiene los diagramas de controles automatizados; el 7 expone los resultados y "
          "evidencias de la ejecución; el 8 propone las mitigaciones; el 9 evalúa el plan de mantenimiento; y el 10 concluye.")


def cap2(inf: Informe, H):
    inf.h(1, "2. Criterios de calidad, seguridad y cumplimiento normativo")
    inf.p("Los criterios que Atlas debe satisfacer se derivan del ERS y de marcos técnicos y legales reconocidos. La Tabla 1 "
          "los resume junto con la forma en que esta iteración los verifica.")
    filas = [
        ["Calidad del producto", "ISO/IEC 25010", "NFR-PERF, NFR-USAB, NFR-COMPAT, NFR-DIS", "Casos TC-NFR automatizados (pytest, Playwright, k6)"],
        ["Proceso y documentación de pruebas", "ISO/IEC/IEEE 29119", "Todo el ERS", "Catálogo único, estados normalizados y evidencia por caso"],
        ["Seguridad de la información", "ISO/IEC 27001:2022 (Anexo A: A.8.5, A.8.8, A.8.13, A.8.15, A.8.24, A.8.25-A.8.29)", "NFR-SEG-1 a 9", "Compuertas del pipeline DevSecOps (capítulo 6)"],
        ["Seguridad de aplicaciones web", "OWASP Top 10:2025 y OWASP ASVS 4.0", "NFR-SEG-4, NFR-SEG-5, NFR-SEG-9", "Casos TC-SEC con categoría OWASP y CWE"],
        ["Severidad de vulnerabilidades", "CVSS v3.1 (FIRST)", "Criterio de aceptación NFR-SEG", "Vector y puntaje calculados por cvss.py"],
        ["Accesibilidad", "WCAG 2.1 nivel AA", "NFR-USAB-1, interfaz 3.1.1", "axe-core en 5 vistas, fuente mínima y objetivos táctiles"],
        ["Protección de datos personales", "Ley N.º 19.628 y Ley N.º 21.719", "NFR-SEG-8, NFR-SEG-3", "Pruebas de exposición, minimización y cifrado"],
        ["Ciberseguridad", "Ley N.º 21.663 (Marco de Ciberseguridad)", "NFR-SEG-6, NFR-SEG-7", "Registro, respaldo y gestión de incidentes"],
    ]
    inf.tabla(["Eje", "Estándar o marco", "Requerimientos ERS", "Verificación en esta iteración"], filas,
              [3.2, 4.8, 3.6, 4.6], "Criterios de calidad, seguridad y cumplimiento aplicados.")
    inf.p("Respecto del marco legal, la Ley N.º 21.719, publicada el 13 de diciembre de 2024, moderniza la Ley N.º 19.628, "
          "crea la Agencia de Protección de Datos Personales e incorpora, entre otros, los principios de proporcionalidad, "
          "seguridad y responsabilidad, junto con el deber de reportar vulneraciones de seguridad. Su entrada en vigencia está "
          "prevista para el 1 de diciembre de 2026, aunque a la fecha de este informe se tramita un proyecto que propone "
          "postergarla a 2027. En cualquier escenario, un sistema que trata datos bancarios de clientes, como Atlas, debe "
          "diseñarse hoy para cumplirla, y el artículo 11 de la Ley N.º 19.628 vigente ya obliga a cuidar los datos con la "
          "debida diligencia.")


def cap3(inf: Informe, H):
    inf.h(1, "3. Enfoques y herramientas de pruebas de seguridad")
    inf.p("Ningún enfoque de pruebas de seguridad detecta por sí solo todas las vulnerabilidades: cada uno observa el "
          "software desde una perspectiva distinta (código, dependencias, configuración o comportamiento en ejecución) y tiene "
          "puntos ciegos propios. Por ello se combinaron ocho enfoques, aplicados con herramientas de uso profesional, y se "
          "contrastó qué detectó cada uno sobre el mismo sistema.")
    inf.h(2, "3.1 Clasificación de enfoques")
    filas = [
        ["SAST (análisis estático)", "Caja blanca", "Desarrollo y CI", "Patrones inseguros en el código: secretos por defecto, comparación de contraseñas en claro, rutas sin autorización, errores expuestos", "Falsos positivos; no ve configuración ni ejecución", "Semgrep (rulesets públicos + 13 reglas propias)"],
        ["Escaneo de secretos", "Caja blanca", "Pre-commit y CI", "Claves, tokens y contraseñas en archivos versionados", "No evalúa si el secreto sigue vigente", "Gitleaks"],
        ["SCA (composición)", "Caja blanca", "CI y monitoreo continuo", "Dependencias con CVE conocidos y versiones sin soporte", "Sólo vulnerabilidades ya publicadas", "npm audit, Trivy fs"],
        ["Revisión de configuración (IaC)", "Caja blanca", "Construcción", "Contenedores como root, falta de healthcheck, puertos expuestos", "No detecta fallas lógicas", "Trivy config"],
        ["DAST (análisis dinámico)", "Caja negra", "QA", "Cabeceras ausentes, divulgación de información, configuración HTTP", "No entiende la lógica de negocio ni la autorización", "OWASP ZAP baseline"],
        ["Pentesting dirigido", "Caja gris", "QA", "Control de acceso roto, IDOR/BOLA, escalada de privilegios, falsificación de tokens, fuerza bruta", "Depende del diseño de los casos", "pytest + requests (scripts propios)"],
        ["Pruebas negativas y fuzzing de entradas", "Caja negra", "QA", "Falta de validación: XSS almacenado, archivos peligrosos, contraseñas débiles", "Cobertura limitada a los payloads usados", "pytest + Playwright"],
        ["Verificación de caja blanca en datos", "Caja blanca", "QA", "Contraseñas en claro, datos bancarios sin cifrar, borrado físico", "Requiere acceso a la BD", "psql en el contenedor"],
    ]
    inf.tabla(["Enfoque", "Visibilidad", "Momento", "Qué detecta", "Limitación", "Herramienta"], filas,
              [2.6, 1.7, 1.8, 4.4, 3.1, 2.6], "Enfoques de pruebas de seguridad aplicados.", size=8.5, negrita_col0=True)
    inf.p("Los enfoques IAST y RASP, que instrumentan la aplicación en ejecución, no se aplicaron porque requieren agentes "
          "comerciales o modificar el runtime de Node.js; su función queda cubierta parcialmente por la combinación de SAST con "
          "pentesting dirigido.")
    inf.h(2, "3.2 Función de cada herramienta y ejemplos en Atlas")
    sev = H["semgrep_sev"]
    reglas_prop = [r for r in H["semgrep_reglas"] if r.startswith("atlas-")]
    inf.p(f"**Semgrep (SAST).** Con los rulesets públicos (p/javascript, p/nodejs, p/owasp-top-ten, p/jwt, p/react y "
          f"p/secrets) Semgrep sólo reportó {H['semgrep_publicas']} hallazgo(s), lo que evidencia una limitación conocida del "
          f"SAST genérico: no conoce la lógica de autorización propia de cada sistema. Por eso se escribieron 13 reglas "
          f"personalizadas (seguridad/semgrep_atlas.yml) que traducen requisitos del ERS a patrones verificables; con ellas "
          f"el análisis detectó {H['semgrep_propias']} ocurrencias adicionales ({sev.get('ERROR', 0)} de severidad ERROR en total). "
          f"Por ejemplo, la regla atlas-contrasena-comparada-en-claro encontró en "
          f"{H['semgrep_ej'].get('atlas-contrasena-comparada-en-claro', 'auth.js')} la comparación "
          f"«user.contrasena_hash !== password», confirmando estáticamente el defecto que TC-SEC-02 confirma en la base de datos.")
    inf.p("Los hallazgos de SAST requieren triage. La primera ejecución de las reglas propias produjo dos falsos positivos: "
          "la regla de comparación de contraseñas marcó en el frontend la validación «contraseña = confirmación» "
          "(UsuarioForm.jsx), lo que se corrigió acotando la regla al backend; y la regla de rutas de escritura sin "
          "autenticación marcó POST /empresas, que es el registro público exigido por RF-2.1 y se documentó como excepción "
          "aceptada. Las 13 rutas restantes señaladas por esa regla son verdaderos positivos según la revisión manual del "
          "código, y varias de ellas se explotaron dinámicamente en TC-SEC-05, TC-SEC-06, TC-SEC-07 y TC-SEC-14.")
    gl = H["gitleaks"]
    inf.p(f"**Gitleaks (secretos).** Detectó {len(gl)} secretos expuestos en {', '.join(sorted({f for _, f, _ in gl}))}. El más "
          f"grave es el secreto de firma JWT publicado en el README: con él, TC-SEC-17 fabricó un token válido de otra empresa "
          f"sin conocer ninguna contraseña. Este caso muestra cómo un hallazgo de escaneo estático se convierte en una "
          f"explotación real cuando se combina con pentesting.")
    nb, nf = H["npm"].get("backend", {}), H["npm"].get("frontend", {})
    ts = H["trivy_sev"]
    inf.p(f"**npm audit y Trivy (SCA).** npm audit reportó {nb.get('total', 0)} vulnerabilidades en el backend "
          f"({nb.get('critical', 0)} crítica(s) y {nb.get('high', 0)} altas) y {nf.get('total', 0)} en el frontend "
          f"({nf.get('critical', 0)} críticas y {nf.get('high', 0)} altas). Trivy, con su propia base de datos de CVE, "
          f"identificó {ts.get('CRITICAL', 0)} críticas y {ts.get('HIGH', 0)} altas. Usar dos fuentes reduce falsos negativos, "
          f"ya que cada base de datos de vulnerabilidades tiene distinta cobertura.")
    conf = H["trivy_conf"]
    inf.p(f"**Trivy config (IaC).** Encontró {len(conf)} configuraciones inseguras en los Dockerfile: contenedores que se "
          f"ejecutan como root y ausencia de HEALTHCHECK. Complementariamente, TC-SEC-25 comprobó que PostgreSQL acepta "
          f"conexiones desde la red con las credenciales por defecto postgres/postgres a través del puerto publicado 15432.")
    zf, za = H["zap"].get("frontend", []), H["zap"].get("api", [])
    medios = sorted({n for r, n, _ in zf + za if r in ("Alto", "Medio")})
    inf.p(f"**OWASP ZAP (DAST).** El escaneo pasivo generó {len(zf)} alertas sobre el frontend y {len(za)} sobre la API, "
          f"entre ellas de riesgo medio: {', '.join(medios) if medios else 'ninguna'}. ZAP no detectó ninguno de los "
          f"defectos de autorización, porque un escáner automático no sabe qué usuario debería poder ver qué dato; esa "
          f"brecha la cubre el pentesting dirigido.")
    inf.p("**pytest + requests (pentesting dirigido).** Los scripts reproducen ataques realistas encadenando debilidades. "
          "El más grave (TC-SEC-07) parte de un visitante que sólo se registra: lee el identificador de su vínculo en su "
          "propio JWT, obtiene la lista de empresas en GET /empresas sin autenticación, modifica sin token su vínculo con "
          "PUT /empresa-usuarios para quedar como administrador de otra empresa e inicia sesión para leer sus clientes con "
          "datos bancarios. Ninguna herramienta automática genérica encontró esta cadena.")
    inf.p("**Playwright, axe-core, psql y k6.** Playwright ejecutó la interfaz en cuatro motores de navegador y confirmó que "
          "React escapa el payload XSS almacenado. axe-core auditó WCAG 2.1 AA. psql verificó en la base de datos lo que la "
          "API no muestra (contraseñas y cuentas en claro, borrado físico). k6 sometió la API a 200 usuarios concurrentes.")
    inf.h(2, "3.3 Complementariedad de los enfoques")
    inf.p("La Tabla 3 cruza los principales hallazgos con los enfoques que los detectaron; ningún enfoque detectó más de la "
          "mitad de ellos, lo que justifica integrarlos todos en el pipeline.")
    marca = "✔"
    filas = [
        ["Contraseñas en texto plano (TC-SEC-02)", marca, "", "", "", "", marca],
        ["Endpoints sin autenticación (TC-SEC-05/06)", marca, "", "", "", marca, ""],
        ["Toma de control entre empresas (TC-SEC-07)", "", "", "", "", marca, ""],
        ["Secreto JWT publicado (TC-SEC-17, 23)", marca, marca, "", "", marca, ""],
        ["Dependencias vulnerables (TC-SEC-21)", "", "", marca, "", "", ""],
        ["Contenedores como root y BD expuesta (TC-SEC-25)", marca, "", marca, "", marca, ""],
        ["Cabeceras y CORS (TC-SEC-11/12)", marca, "", "", marca, marca, ""],
        ["Errores con detalle de BD (TC-SEC-13)", marca, "", "", "", marca, ""],
        ["Archivos peligrosos aceptados (TC-SEC-19)", marca, "", "", "", marca, ""],
        ["Datos bancarios sin cifrar (TC-SEC-03)", "", "", "", "", "", marca],
    ]
    inf.tabla(["Hallazgo", "SAST", "Secretos", "SCA / IaC", "DAST", "Pentest", "Caja blanca BD"], filas,
              [6.0, 1.5, 1.6, 1.7, 1.4, 1.6, 2.4], "Hallazgos detectados por cada enfoque de pruebas de seguridad.", size=8.5)


def cap4(inf: Informe, H):
    inf.h(1, "4. Plan de pruebas y diseño de casos")
    inf.p("Este capítulo retoma los apartados de las evaluaciones anteriores (criterios, plan de pruebas y diseño de casos) y "
          "los consolida en un catálogo único y ejecutable, de modo que el plan documentado y las pruebas efectivamente "
          "ejecutadas sean la misma cosa.")
    inf.h(2, "4.1 Estrategia de pruebas")
    inf.p("Se aplicó una estrategia basada en riesgo y orientada a la automatización. La prioridad se asignó según el impacto "
          "sobre la confidencialidad de datos personales y bancarios y según la criticidad del requerimiento:")
    inf.bullets([
        "**Prioridad 1 (crítica):** autenticación, autorización, aislamiento entre empresas, criptografía y secretos.",
        "**Prioridad 2 (alta):** operaciones CRUD de clientes, contratos, documentos y usuarios; auditoría; validación de entradas.",
        "**Prioridad 3 (media):** rendimiento, carga, accesibilidad, usabilidad, compatibilidad, disponibilidad y mantenibilidad.",
    ])
    inf.p("Las pruebas se organizaron en capas: análisis estático (código, secretos, dependencias y configuración), pruebas de "
          "API (funcionales y de seguridad), pruebas de interfaz y pruebas no funcionales. Cada ejecución crea sus propias "
          "empresas de prueba («víctima» y «atacante») con datos ficticios, de modo que las pruebas destructivas nunca alteran "
          "los datos semilla y los resultados son reproducibles.")
    inf.h(2, "4.2 Tipos de prueba y justificación")
    filas = [
        ["Funcional", "Verifica que cada RF y regla de negocio se cumpla", "Login, CRUD, estado de contratos, auditoría", f"{sum(1 for c in CASOS if c['id'].startswith('TC-FUN'))}"],
        ["Seguridad", "Detecta vulnerabilidades antes que un atacante", "Autorización, autenticación, criptografía, entradas, configuración, cadena de suministro", f"{sum(1 for c in CASOS if c['id'].startswith('TC-SEC'))}"],
        ["Rendimiento y carga", "Comprueba los umbrales NFR-PERF bajo uso normal y concurrente", "CRUD < 300 ms, carga móvil < 2 s, 200 usuarios", "3"],
        ["Accesibilidad y usabilidad", "Asegura el uso por adultos mayores (WCAG 2.1 AA)", "axe-core, tipografía, flujos E2E, mensajes", "5"],
        ["Compatibilidad", "Garantiza funcionamiento en navegadores y pantallas objetivo", "Chromium, Edge, Firefox, WebKit; móvil, tablet, escritorio", "2"],
        ["Disponibilidad y mantenibilidad", "Verifica mecanismos de recuperación y evolución segura", "Caída controlada, migraciones versionadas", "2"],
    ]
    inf.tabla(["Tipo", "Propósito", "Aplicación en Atlas", "Casos"], filas, [3.0, 5.0, 6.6, 1.6],
              "Tipos de prueba aplicados.")
    inf.h(2, "4.3 Criterios de aceptación y estados de ejecución")
    inf.p("Cada caso codifica como aserción el comportamiento correcto exigido por el ERS; si el sistema se desvía, la "
          "aserción falla y su mensaje documenta lo obtenido. Se emplean exclusivamente tres estados:")
    inf.bullets([
        "**PASÓ:** el resultado obtenido coincide con el esperado y con el criterio de aceptación.",
        "**FALLÓ:** el sistema se desvía del requerimiento; se registra un incidente con su criticidad.",
        "**BLOQUEADO:** el caso no pudo completarse por una causa externa (dependencia o herramienta no ejecutada); no "
        "se interpreta como aprobación ni como falla del sistema.",
    ])
    inf.p("El criterio de salida para producción es: 100 % de los casos de prioridad 1 en estado PASÓ, cero incidentes "
          "críticos o altos abiertos y al menos 95 % del total de casos en estado PASÓ.")
    inf.h(2, "4.4 Escala de criticidad")
    inf.p("Para los hallazgos de seguridad se utiliza el puntaje base CVSS v3.1, calculado a partir del vector de cada caso, y "
          "para los defectos funcionales y no funcionales, el impacto en el negocio. Ambos se expresan en la misma escala:")
    filas = [["Crítica", "9,0 – 10,0", "Compromete datos de terceros o el control del sistema sin requisitos previos", "Remediación inmediata (≤ 7 días)"],
             ["Alta", "7,0 – 8,9", "Afecta funciones esenciales o expone datos con condiciones mínimas", "Corregir con urgencia (≤ 30 días)"],
             ["Media", "4,0 – 6,9", "Afecta funciones secundarias o requiere condiciones específicas", "Siguiente iteración"],
             ["Baja", "0,1 – 3,9", "Impacto acotado, sin exposición de datos", "Según disponibilidad"]]
    inf.tabla(["Criticidad", "CVSS v3.1", "Impacto en el negocio", "Acción"], filas, [2.4, 2.4, 7.0, 4.4],
              "Escala de criticidad de incidentes.", colores=lambda fi, i, v: COLOR_SEV.get(v) if i == 0 else None)
    inf.h(2, "4.5 Entorno y herramientas")
    filas = [["Docker Desktop / Compose", VERSIONES.get("docker", "29.9.3 / 5.7.1"), "Ambiente reproducible: frontend :3350, API :4450, PostgreSQL :15432"],
             ["Python + pytest + requests", VERSIONES.get("pytest", "3.13 · pytest 9.2 · requests 2.34"), "Suite de API funcional, seguridad y no funcional"],
             ["Playwright + axe-core", VERSIONES.get("playwright", "Playwright 1.65 · axe-playwright-python 0.1.9"), "Interfaz, compatibilidad, accesibilidad"],
             ["Semgrep", H.get("semgrep_version") or VERSIONES.get("semgrep", ""), "SAST con rulesets públicos y reglas propias"],
             ["Gitleaks", VERSIONES.get("gitleaks", ""), "Escaneo de secretos"],
             ["npm audit / Trivy", VERSIONES.get("trivy", ""), "SCA e IaC"],
             ["OWASP ZAP", H.get("zap_version") or VERSIONES.get("zap", ""), "DAST pasivo (baseline)"],
             ["Grafana k6", VERSIONES.get("k6", ""), "Prueba de carga con 200 usuarios virtuales"]]
    inf.tabla(["Herramienta", "Versión", "Uso"], filas, [4.2, 4.6, 7.4], "Herramientas y versiones utilizadas.")
    inf.h(2, "4.6 Diseño de casos representativos")
    inf.p(f"El catálogo contiene {len(CASOS)} casos. A continuación se detallan casos representativos de cada tipo de "
          "requerimiento; el resto se presenta en la matriz de trazabilidad (sección 4.7) con la misma estructura en el "
          "archivo pruebas/catalogo.py.")
    for cid in ("TC-FUN-01", "TC-FUN-11", "TC-FUN-17", "TC-SEC-04", "TC-SEC-07", "TC-SEC-17", "TC-SEC-19", "TC-NFR-01", "TC-NFR-04"):
        c = POR_ID[cid]
        filas = [["Nombre", c["nombre"]], ["Requerimiento", ", ".join(c["req"])], ["Tipo de prueba", c["tipo"]],
                 ["Descripción", c["descripcion"]], ["Precondiciones", c["precondiciones"]], ["Datos de entrada", c["datos"]],
                 ["Pasos", "\n".join(f"{i}. {s}" for i, s in enumerate(c["pasos"], 1))],
                 ["Resultado esperado", c["esperado"]], ["Criterio de aceptación", c["criterio"]],
                 ["Herramienta", c["herramienta"]]]
        if c.get("owasp"):
            filas.insert(3, ["OWASP / CWE", f"{c['owasp']} · {c['cwe']}"])
        t = inf.tabla([cid, ""], filas, [3.8, 12.4], size=9, negrita_col0=True, juntas=True)
        t.rows[0].cells[0].merge(t.rows[0].cells[1])
    inf.h(2, "4.7 Matriz de trazabilidad")
    filas = [[c["id"], c["nombre"], ", ".join(c["req"]), c["tipo"], c["herramienta"], est(c["id"])] for c in CASOS]
    inf.tabla(["ID", "Caso", "Requerimiento", "Tipo", "Herramienta", "Estado"], filas,
              [1.9, 4.5, 3.0, 2.6, 2.4, 1.8], "Matriz de trazabilidad de los casos de prueba.", size=8,
              colores=lambda fi, i, v: COLOR_ESTADO.get(v) if i == 5 else None)
    inf.h(2, "4.8 Cobertura de los requerimientos del ERS")
    codigos = (["RF-1.1", "RF-1.2", "RF-2.1", "RF-2.2", "RF-2.3", "RF-3.1", "RF-3.2", "RF-3.3", "RF-4.1", "RF-4.2", "RF-4.3",
                "RF-5.1", "RF-5.2", "RF-5.3", "RF-5.4", "RF-5.5", "RF-6.1", "RB-1", "RB-2", "RB-3", "RB-4", "RB-5"]
               + [f"NFR-SEG-{i}" for i in range(1, 10)] + ["NFR-PERF-1", "NFR-PERF-2", "NFR-PERF-3"]
               + [f"NFR-USAB-{i}" for i in range(1, 5)] + ["NFR-DIS-1", "NFR-DIS-2", "NFR-COMPAT-1", "NFR-COMPAT-2",
                                                             "Restricción 2.4", "Interfaz frontend 3.1.1", "Interfaz backend 3.1.2"])
    cob = OrderedDict((k, [c["id"] for c in CASOS if k in c["req"]]) for k in codigos)
    sin = [k for k, v in cob.items() if not v]
    filas = []
    items = list(cob.items())
    mitad = (len(items) + 1) // 2
    for a, b in zip(items[:mitad], items[mitad:] + [("", [])]):
        filas.append([a[0], ", ".join(x.replace("TC-", "") for x in a[1]), b[0], ", ".join(x.replace("TC-", "") for x in b[1])])
    inf.p(f"La Tabla {inf.tab + 1} demuestra que los {len(codigos)} códigos de requerimiento del ERS tienen al menos un caso "
          f"asociado (cobertura {100 * (len(codigos) - len(sin)) / len(codigos):.0f} %). La asociación es directa: cada código "
          f"se vincula al caso que efectivamente lo verifica, no a un caso relacionado.")
    inf.tabla(["Requerimiento", "Casos", "Requerimiento", "Casos"], filas, [3.4, 4.7, 3.4, 4.7],
              "Cobertura de los requerimientos del ERS.", size=8)


def cap5(inf: Informe, H):
    inf.h(1, "5. Automatización de pruebas")
    inf.p("La automatización se diseñó para que toda la batería se ejecute con un solo comando, sin instalar herramientas de "
          "seguridad en el equipo (todas corren como contenedores Docker) y produciendo evidencia trazable para cada caso.")
    inf.h(2, "5.1 Arquitectura del marco de automatización")
    inf.figura(DIAG / "D3_flujo_automatizacion.png", "Flujo de la automatización: de una fuente única de verdad al informe.")
    inf.p("Las decisiones de diseño que sostienen la calidad de la automatización son:")
    inf.bullets([
        "**Fuente única de verdad:** pruebas/catalogo.py define cada caso (requerimiento, tipo, OWASP, CWE, vector CVSS, "
        "criterio y mitigación). Los tests lo referencian con @pytest.mark.caso y el informe se genera desde el mismo "
        "catálogo, por lo que el resumen, el detalle y la matriz no pueden contradecirse.",
        "**Aserciones que codifican el ERS:** cada prueba afirma el comportamiento correcto; un desvío produce FALLÓ con un "
        "mensaje que describe lo obtenido. Los errores de la propia prueba se clasifican como BLOQUEADO, nunca como aprobados.",
        "**Aislamiento de datos:** cada ejecución registra empresas y usuarios nuevos con sufijos aleatorios; las pruebas "
        "destructivas sólo operan sobre esos datos.",
        "**Evidencia automática:** cada caso guarda la transcripción de peticiones y respuestas (evidencias/<ID>.txt), que se "
        "convierte en figura; Playwright captura las pantallas.",
        "**Verificación del efecto, no sólo del código HTTP:** varias operaciones anónimas responden HTTP 500 porque falla el "
        "registro de auditoría, pero el cambio ya quedó aplicado. La suite consulta la base de datos para confirmar el efecto "
        "real (TC-SEC-05, TC-SEC-06 y TC-SEC-07), evitando falsos negativos que una revisión manual basada sólo en el código de "
        "estado pasaría por alto.",
    ])
    inf.h(2, "5.2 Componentes de la suite")
    filas = [["run_todo.ps1", "Orquestador de 9 etapas; mide el tiempo de cada una", "PowerShell"],
             ["pruebas/catalogo.py · cvss.py", f"{len(CASOS)} casos; cálculo CVSS v3.1 verificado con ejemplos de FIRST", "Python"],
             ["pruebas/conftest.py", "Registro de resultados, evidencias, datos aislados y acceso a la BD", "pytest"],
             ["pruebas/api/test_funcionales.py", f"{sum(1 for c in CASOS if c['id'].startswith('TC-FUN'))} casos RF, RB e interfaz backend", "pytest + requests"],
             ["pruebas/api/test_seguridad.py", "20 casos de pentesting y verificación de controles", "pytest + requests + psql"],
             ["pruebas/api/test_herramientas.py", "Interpreta Semgrep, Gitleaks, npm audit, Trivy, ZAP y k6", "pytest"],
             ["pruebas/api/test_no_funcionales.py · test_zz_disponibilidad.py", "Rendimiento CRUD, migraciones y caída controlada", "pytest + Docker"],
             ["pruebas/ui/test_ui.py", "8 casos de interfaz y capturas de evidencia", "Playwright + axe-core"],
             ["pruebas/carga/k6_carga.js", "200 usuarios virtuales con umbrales p95 < 300 ms", "k6"],
             ["seguridad/semgrep_atlas.yml", "13 reglas SAST propias derivadas del ERS", "Semgrep"]]
    inf.tabla(["Archivo", "Responsabilidad", "Tecnología"], filas, [5.6, 7.6, 3.0], "Componentes del marco de automatización.")
    inf.h(2, "5.3 Entorno y ejecución de la batería")
    inf.p("Todas las pruebas se ejecutaron sobre Atlas desplegado localmente con Docker Compose: un contenedor de "
          "PostgreSQL 15 con healthcheck, la API Express y el frontend React servido por Nginx. La Figura siguiente muestra "
          "los contenedores en ejecución, las imágenes construidas y la respuesta de ambos servicios; a continuación se "
          "muestra la aplicación levantada en el navegador.")
    inf.figura(EVID / "ENT_01_docker.png", "Entorno de pruebas: contenedores de Atlas en ejecución y servicios respondiendo.")
    inf.figura(EVID / "UI_01_login.png", "Atlas levantado en http://localhost:3350 (pantalla de inicio de sesión).", ancho=15)
    total = sum(TIEMPOS.values()) if TIEMPOS else 0
    filas = [[k, f"{v:,.1f} s".replace(",", "X").replace(".", ",").replace("X", ".")] for k, v in TIEMPOS.items()]
    filas.append(["**Total de la batería**", f"**{total/60:,.1f} min**".replace(".", ",")])
    inf.p("La batería completa se ejecuta con el comando «powershell -ExecutionPolicy Bypass -File .\\run_todo.ps1». La "
          "Tabla siguiente presenta el tiempo real medido por el propio orquestador en la ejecución oficial:")
    inf.tabla(["Etapa", "Duración"], filas, [12.0, 4.2], "Tiempo real de cada etapa de la ejecución automatizada.")
    inf.figura(EVID / "ENT_02_consola.png", "Consola de la ejecución oficial de run_todo.ps1 (extracto literal del log).")
    inf.p("En la consola, pytest cuenta funciones de prueba y no casos: los 16 resultados «passed» corresponden a los 14 "
          "casos en estado PASÓ más 2 funciones que sólo capturan evidencia de la interfaz, y los 45 «failed» coinciden "
          "exactamente con los 45 casos en estado FALLÓ. Cada herramienta deja además su propio reporte navegable, que se "
          "archiva como evidencia de la iteración:")
    inf.figura(EVID / "ENT_03_pytest_html.png", "Reporte HTML de pytest de la suite de API (resultado y duración por prueba).", ancho=15)
    inf.figura(EVID / "ENT_04_zap_html.png", "Reporte HTML de OWASP ZAP sobre el frontend (resumen de alertas por riesgo).", ancho=15)
    inf.h(2, "5.4 Eficiencia frente a la ejecución manual")
    inf.p("Para estimar el esfuerzo manual equivalente se aplicaron supuestos explícitos y conservadores: revisión de código "
          "de seguridad a 150 líneas por hora (1.848 líneas en el backend y 5.593 en el frontend), 2 minutos por dependencia "
          "para cotejar CVE (533 paquetes), 8 minutos por caso de API con Postman incluyendo la captura de evidencia y 15 "
          "minutos por caso de interfaz por navegador.")
    t = lambda k: TIEMPOS.get(k, 0)  # noqa: E731
    filas = [
        ["Revisión de código (SAST)", "≈ 50 h", f"{t('SAST - Semgrep'):.0f} s"],
        ["Búsqueda de secretos", "≈ 1 h", f"{t('Secretos - Gitleaks'):.0f} s"],
        ["Cotejo de dependencias (SCA)", "≈ 18 h", f"{t('SCA - npm audit') + t('SCA - Trivy fs'):.0f} s"],
        ["Revisión de Dockerfile y compose", "≈ 1 h", f"{t('IaC - Trivy config'):.0f} s"],
        ["Revisión de cabeceras y respuestas (DAST)", "≈ 2 h", f"{t('DAST - OWASP ZAP baseline'):.0f} s"],
        ["200 usuarios concurrentes", "No factible", f"{t('Carga - k6 (200 VU)'):.0f} s"],
        ["Casos de API (funcionales, seguridad, NFR)", "≈ 6 h", f"{t('API - pytest (funcional, seguridad, no funcional)'):.0f} s"],
        ["Casos de interfaz en 4 navegadores", "≈ 4 h", f"{t('Interfaz - Playwright + axe-core'):.0f} s"],
        ["Caída controlada y medición de recuperación", "≈ 0,5 h", f"{t('Disponibilidad - caída controlada'):.0f} s"],
    ]
    inf.tabla(["Actividad", "Manual (estimado)", "Automatizado (medido)"], filas, [8.2, 3.8, 4.2],
              "Comparación del esfuerzo manual estimado con el tiempo automatizado medido.")
    inf.p(f"Frente a unas 82 horas de trabajo manual estimado, la batería completa tarda {total/60:.0f} minutos y no requiere "
          "intervención, lo que representa una reducción superior al 98 % por ciclo. Más relevante que el ahorro de una "
          "ejecución es que el costo marginal de repetirla es casi nulo: la misma batería puede correr en cada commit como "
          "prueba de regresión, algo inviable de forma manual.")
    inf.h(2, "5.5 Aporte al aseguramiento de la calidad y limitaciones")
    inf.p("La automatización aporta repetibilidad (los mismos pasos y datos en cada ciclo), objetividad (umbrales del ERS "
          "convertidos en aserciones), trazabilidad (cada resultado está ligado a un requerimiento y a su evidencia) y detección "
          "temprana (las compuertas del pipeline bloquean un cambio inseguro antes de llegar a QA). Sus limitaciones son que no "
          "reemplaza el juicio experto en usabilidad con personas reales, que las reglas SAST requieren mantenimiento para "
          "evitar falsos positivos y que la suite debe evolucionar junto con el ERS; estas tareas se incorporan al plan de "
          "mantenimiento del capítulo 9.")
    inf.p("La propia suite también se verificó. Al revisar las evidencias de una primera ejecución se corrigieron tres "
          "casos antes de la ejecución oficial: (1) TC-NFR-11 intentaba detener la API con «kill 1», pero Node.js corre "
          "como PID 1 en el contenedor y el kernel ignora esa señal, por lo que el caso concluía erróneamente que la API "
          "no se recuperaba; se rediseñó para simular un corte real de la base de datos, lo que además reveló que la API "
          "se cae porque el pool de conexiones no maneja errores; (2) TC-NFR-10 aprobaba porque sólo medía el "
          "desplazamiento horizontal, mientras la captura móvil mostraba contenido recortado por «overflow: hidden»; se "
          "refinó el criterio para detectar texto fuera del viewport sin penalizar tablas con desplazamiento propio; y "
          "(3) el SAST se amplió con reglas propias y se depuraron sus falsos positivos. Esta revisión crítica de la "
          "automatización es parte del aseguramiento de la calidad: una prueba mal diseñada genera falsos positivos o "
          "negativos tan dañinos como un defecto del producto.")


def cap6(inf: Informe, H):
    inf.h(1, "6. Diagramas de controles de seguridad automatizados")
    inf.p("Los siguientes diagramas representan cómo los controles de seguridad automatizados se integran en el ciclo de "
          "desarrollo y en la arquitectura de Atlas, y cómo cada uno verifica el cumplimiento de requisitos normativos y legales.")
    inf.h(2, "6.1 Pipeline DevSecOps con compuertas automatizadas")
    inf.figura(DIAG / "D1_pipeline_devsecops.png", "Pipeline DevSecOps de Atlas con controles de seguridad automatizados y su alineación normativa y legal.")
    inf.p("El pipeline desplaza la seguridad hacia las primeras etapas («shift-left»): un secreto se detiene antes del commit, "
          "un patrón inseguro o una dependencia vulnerable se detienen en el pull request, y una regresión de autorización se "
          "detiene en QA. La compuerta de calidad (etapa 5) formaliza los criterios de salida del capítulo 4 y archiva la "
          "evidencia, lo que permite demostrar ante una auditoría o ante la futura Agencia de Protección de Datos Personales "
          "que el sistema se verificó antes de cada despliegue.")
    filas = [["Pre-commit", "Gitleaks", "NFR-SEG-9", "ISO 27001 A.8.28", "Ley 21.719: seguridad"],
             ["Pull request", "Semgrep + reglas Atlas", "NFR-SEG-2, 4, 5, 6, 9", "ISO 27001 A.8.29; OWASP ASVS", "Ley 19.628 art. 11"],
             ["Pull request", "npm audit + Trivy", "NFR-SEG-5", "ISO 27001 A.8.8; OWASP A03:2025", "Ley 21.663: gestión de riesgos"],
             ["Pull request", "pytest (API)", "RF-1 a RF-6, RB, NFR-SEG", "ISO/IEC/IEEE 29119", "Ley 21.719: proporcionalidad"],
             ["Construcción", "Trivy config", "NFR-SEG-3, NFR-DIS", "ISO 27001 A.8.9; CIS Docker", "—"],
             ["QA", "OWASP ZAP", "NFR-SEG-1, 5", "OWASP Top 10:2025", "—"],
             ["QA", "Playwright + axe-core", "NFR-USAB, NFR-COMPAT", "WCAG 2.1 AA; ISO/IEC 25010", "—"],
             ["QA", "k6", "NFR-PERF-1 a 3", "ISO/IEC 25010", "—"],
             ["Operación", "Respaldo, logs y alertas", "NFR-SEG-6, 7; NFR-DIS-1", "ISO 27001 A.8.13, A.8.15, A.8.16", "Ley 21.719: reporte de vulneraciones"]]
    inf.tabla(["Etapa", "Control automatizado", "Requisito ERS", "Norma técnica", "Marco legal"], filas,
              [2.3, 3.6, 3.4, 3.9, 3.0], "Alineación de los controles automatizados con requisitos, normas y leyes.", size=8.5)
    inf.h(2, "6.2 Arquitectura de controles por capas")
    inf.figura(DIAG / "D2_controles_por_capas.png", "Arquitectura de controles de seguridad por capas con su estado verificado por la suite.", ancho=14.0)
    inf.p("El diagrama aplica el principio de defensa en profundidad: si un control falla, otro de la capa siguiente debe "
          "contener el ataque. El estado de cada control proviene de la ejecución real de la suite, por lo que el diagrama "
          "sirve a la vez como objetivo de arquitectura y como tablero de cumplimiento: hoy sólo el escape de salida de React y "
          "las consultas parametrizadas funcionan, lo que explica por qué un único defecto de autorización permite exponer "
          "datos bancarios de otra empresa.")


def cap7(inf: Informe, H):
    inf.h(1, "7. Resultados de la ejecución")
    tot = contar()
    inf.h(2, "7.1 Resumen de ejecución")
    fechas = sorted({v.get("fecha", "") for v in RES.values()})
    filas = []
    for etiqueta, pref in (("Funcionales (TC-FUN)", "TC-FUN"), ("Seguridad (TC-SEC)", "TC-SEC"), ("No funcionales (TC-NFR)", "TC-NFR")):
        c = contar(pref)
        n = sum(c.values())
        filas.append([etiqueta, n, c.get("PASÓ", 0), c.get("FALLÓ", 0), c.get("BLOQUEADO", 0) + c.get("SIN EJECUTAR", 0)])
    filas.append(["**Total**", f"**{sum(tot.values())}**", f"**{tot.get('PASÓ', 0)}**", f"**{tot.get('FALLÓ', 0)}**",
                  f"**{tot.get('BLOQUEADO', 0) + tot.get('SIN EJECUTAR', 0)}**"])
    inf.p(f"La ejecución oficial se realizó el {fechas[0][:10] if fechas else ''} sobre Atlas desplegado con Docker Compose y "
          f"datos semilla reiniciados (docker compose down -v). Ejecutor: {PORTADA['integrante']}. Se ejecutó el 100 % de los "
          f"casos diseñados.")
    inf.tabla(["Categoría", "Casos", "PASÓ", "FALLÓ", "BLOQUEADO"], filas, [6.2, 2.5, 2.5, 2.5, 2.5],
              "Resumen de ejecución por categoría.")
    pct = 100 * tot.get("PASÓ", 0) / max(sum(tot.values()), 1)
    inf.p(f"Sólo el {pct:.0f} % de los casos aprobó. Las funciones básicas operan (inicio de sesión, registro, creación de "
          f"clientes y contratos, documentación Swagger, compatibilidad con navegadores), pero prácticamente todos los "
          f"controles de seguridad exigidos por el ERS están ausentes. El único control de seguridad efectivo es la resistencia "
          f"a inyección SQL, gracias a las consultas parametrizadas.")
    inf.h(2, "7.2 Resultados de las pruebas de seguridad")
    filas = []
    for c in CASOS:
        if not c["id"].startswith("TC-SEC"):
            continue
        sev, base = criticidad(c) if est(c["id"]) == "FALLÓ" else ("—", "")
        filas.append([c["id"], c["nombre"], est(c["id"]), f"{sev}\n{base}".strip(), c.get("owasp", "") or "—", obtenido(c["id"])])
    inf.tabla(["ID", "Prueba", "Estado", "Severidad", "OWASP 2025", "Resultado obtenido"], filas,
              [1.8, 3.4, 1.6, 1.8, 2.6, 5.0], "Resultados de las pruebas de seguridad.", size=7.5,
              colores=lambda fi, i, v: COLOR_ESTADO.get(v) if i == 2 else (COLOR_SEV.get(v.split("\n")[0]) if i == 3 else None))
    inf.h(2, "7.3 Resultados de las pruebas automatizadas funcionales y no funcionales")
    filas = [[c["id"], c["nombre"], est(c["id"]), obtenido(c["id"])] for c in CASOS if not c["id"].startswith("TC-SEC")]
    inf.tabla(["ID", "Prueba", "Estado", "Resultado obtenido"], filas, [1.8, 4.6, 1.6, 8.2],
              "Resultados de las pruebas funcionales y no funcionales.", size=7.5,
              colores=lambda fi, i, v: COLOR_ESTADO.get(v) if i == 2 else None)
    k6 = H.get("k6", {})
    crud = H.get("crud", {})
    if crud:
        inf.p(f"En rendimiento, las lecturas por identificador y la creación de clientes responden en "
              f"{crud.get('GET /clientes/:id', {}).get('p95', 0)} ms y {crud.get('POST /clientes', {}).get('p95', 0)} ms (p95), "
              f"muy por debajo del umbral, mientras que los listados y el inicio de sesión tardan más de 4 segundos por una "
              f"latencia artificial («await delay(4000)») detectada también por la regla SAST atlas-latencia-artificial. "
              + (f"Con 200 usuarios concurrentes, k6 midió un p95 de {k6['p95']:,.0f} ms con {k6['err']*100:.2f} % de errores "
                 f"({k6['reqs']:,} peticiones), es decir, el sistema no colapsa pero incumple el umbral en todas las peticiones."
                 .replace(",", ".") if k6 else ""))
    inf.h(2, "7.4 Evidencias de la ejecución")
    inf.p("Las figuras siguientes corresponden a la salida real de la suite y de las herramientas. Cada transcripción indica "
          "el caso, su estado, la fecha y la prueba que la generó; las peticiones sin token se marcan explícitamente.")
    inf.h(3, "Evidencias de la interfaz")
    inf.figura(EVID / "UI_02_dashboard.png", "Dashboard de Atlas tras iniciar sesión como administrador (Playwright, 1366×768).")
    inf.figura(EVID / "UI_03_clientes.png", "Gestión de clientes con los datos semilla.", ancho=15)
    inf.figura(EVID / "ENT_05_registro.png", "[TC-NFR-06] Registro en dos pasos y acceso al dashboard ejecutado por Playwright.")
    inf.figura(EVID / "ENT_06_navegadores.png", "[TC-NFR-09] Atlas en Chromium, Microsoft Edge, Firefox y WebKit (Safari).")
    inf.figura(EVID / "UI_06_swagger.png", "[TC-FUN-22] Documentación OpenAPI publicada en /docs (Swagger UI).", ancho=15)
    inf.h(3, "Evidencias de pruebas de seguridad")
    for cid, tit in (("TC-SEC-07", "Escalada de privilegios y toma de control de otra empresa por un usuario recién registrado."),
                     ("TC-SEC-17", "Falsificación de un JWT con el secreto publicado en el README."),
                     ("TC-SEC-05", "Endpoints que aceptan operaciones sin autenticación; las escrituras se verifican en la BD."),
                     ("TC-SEC-06", "Eliminación anónima de un contrato ajeno sin registro en auditoría."),
                     ("TC-SEC-04", "El rol editor crea, edita y elimina clientes."),
                     ("TC-SEC-02", "Contraseñas almacenadas en texto plano (caja blanca en PostgreSQL)."),
                     ("TC-SEC-19", "Archivos ejecutables, HTML y de 25 MB aceptados como documentos de contrato."),
                     ("TC-SEC-14", "Auditoría legible por anónimos y eventos fabricados por un editor."),
                     ("TC-SEC-13", "Errores que exponen mensajes internos de PostgreSQL y logs con datos del token."),
                     ("TC-SEC-10", "Inyección SQL neutralizada por consultas parametrizadas (único control efectivo)."),
                     ("TC-SEC-22", "Resultado del análisis estático con Semgrep y las reglas propias de Atlas."),
                     ("TC-SEC-23", "Secretos expuestos detectados por Gitleaks."),
                     ("TC-SEC-21", "Dependencias vulnerables detectadas por npm audit y Trivy."),
                     ("TC-SEC-24", "Alertas del escaneo pasivo de OWASP ZAP."),
                     ("TC-SEC-25", "Base de datos accesible desde la red con credenciales por defecto.")):
        inf.figura(EVID / f"{cid}.png", f"[{cid}] {tit}")
    inf.figura(EVID / "TC-SEC-09_ui.png", "[TC-SEC-09] El payload XSS almacenado se muestra escapado por React (sin ejecución).", ancho=15)
    inf.h(3, "Evidencias de pruebas funcionales y no funcionales")
    for cid, tit in (("TC-FUN-19", "Cobertura de auditoría de las acciones críticas."),
                     ("TC-FUN-17", "El backend no calcula el estado de los contratos."),
                     ("TC-FUN-08", "La eliminación de usuarios falla por la clave foránea de empresa_usuarios."),
                     ("TC-FUN-11", "Eliminación física de clientes."),
                     ("TC-NFR-01", "Tiempos de respuesta CRUD frente al umbral de 300 ms."),
                     ("TC-NFR-03", "Prueba de carga con 200 usuarios concurrentes (k6)."),
                     ("TC-NFR-04", "Violaciones WCAG 2.1 AA detectadas por axe-core."),
                     ("TC-NFR-09", "Compatibilidad en Chromium, Edge, Firefox y WebKit."),
                     ("TC-NFR-10", "Contenido recortado en móvil: el menú lateral no se colapsa."),
                     ("TC-NFR-11", "Un corte de la base de datos derriba la API y Docker la reinicia.")):
        inf.figura(EVID / f"{cid}.png", f"[{cid}] {tit}")
    inf.figura(EVID / "TC-NFR-10_clientes_movil.png", "[TC-NFR-10] Gestión de clientes en un teléfono (390 px): títulos y pestañas recortados.", ancho=6.5)
    inf.figura(EVID / "TC-NFR-07_toast.png", "[TC-NFR-07] Mensaje de error técnico de PostgreSQL mostrado al usuario.", ancho=15)
    inf.figura(EVID / "TC-NFR-02_dashboard_movil.png", "[TC-NFR-02] Dashboard en emulación móvil con red 4G lenta.", ancho=6.5)
    inf.h(2, "7.5 Incidentes identificados y su criticidad")
    inc = []
    for c in CASOS:
        if est(c["id"]) != "FALLÓ":
            continue
        sev, base = criticidad(c)
        orden = {"Crítica": 0, "Alta": 1, "Media": 2, "Baja": 3}[sev]
        inc.append((orden, -(puntaje(c["cvss"]) if c.get("cvss") else 0), c["id"], c["nombre"], sev, base))
    inc.sort()
    cnt = Counter(x[4] for x in inc)
    inf.p(f"Se registraron {len(inc)} incidentes: {cnt.get('Crítica', 0)} críticos, {cnt.get('Alta', 0)} altos, "
          f"{cnt.get('Media', 0)} medios y {cnt.get('Baja', 0)} bajos. La Tabla siguiente los ordena por criticidad; para "
          f"los hallazgos de seguridad la base es el puntaje CVSS v3.1 calculado a partir del vector del catálogo.")
    filas = [[i, cid, nom, sev, base] for (_, _, cid, nom, sev, base), i in zip(inc, range(1, len(inc) + 1))]
    inf.tabla(["N.º", "Caso", "Incidente", "Criticidad", "Base"], filas, [1.0, 2.0, 8.8, 2.2, 2.2],
              "Incidentes ordenados por criticidad.", size=8,
              colores=lambda fi, i, v: COLOR_SEV.get(v) if i == 3 else None)
    return inc


def cap8(inf: Informe, H, inc):
    inf.h(1, "8. Propuestas de mitigación")
    inf.p("Cada incidente tiene una mitigación técnica concreta y un caso de regresión que verificará su corrección: el mismo "
          "caso que hoy falla debe pasar a PASÓ. Las mitigaciones se agrupan en tres oleadas según su criticidad.")
    inf.h(2, "8.1 Plan de remediación por oleadas")
    filas = [["1 · Inmediata (≤ 7 días)", "Críticas", "Rotar el secreto JWT y retirarlo del repositorio; middleware global de autenticación; proteger /empresa-usuarios, /empresas, /roles y DELETE /contratos; cerrar el puerto 15432; actualizar dependencias críticas."],
             ["2 · Corto plazo (≤ 30 días)", "Altas", "bcrypt; RBAC por rol; validación de propiedad por empresa; TLS + HSTS; límite de intentos; validación de archivos; respaldo automatizado; eliminar latencias artificiales."],
             ["3 · Siguiente iteración", "Medias y bajas", "Cifrado de datos bancarios; eliminación lógica; estado de contratos; storage de documentos; auditoría completa; accesibilidad; mensajes de error; paginación; migraciones versionadas."]]
    inf.tabla(["Oleada", "Criticidad", "Acciones"], filas, [3.6, 2.4, 10.2], "Plan de remediación por oleadas.")
    inf.h(2, "8.2 Mitigación propuesta por incidente")
    filas = []
    for _, _, cid, nom, sev, base in inc:
        filas.append([cid, nom, sev, POR_ID[cid]["mitigacion"]])
    inf.tabla(["Caso", "Defecto", "Criticidad", "Mitigación propuesta (verificación: el mismo caso debe pasar a PASÓ)"], filas,
              [1.8, 3.6, 1.7, 9.1], "Mitigaciones por incidente.", size=7.5,
              colores=lambda fi, i, v: COLOR_SEV.get(v) if i == 2 else None)
    inf.h(2, "8.3 Ejemplos de implementación de las mitigaciones críticas")
    inf.p("Los siguientes fragmentos muestran cómo implementar las tres mitigaciones de mayor impacto en el backend Express; "
          "corrigen en conjunto los incidentes TC-SEC-04 a TC-SEC-08, TC-SEC-17 y TC-SEC-02.")
    inf.codigo("""
// middleware/seguridad.js
// Autenticación global, rol y pertenencia a la empresa (TC-SEC-04 a 08 y 17)
const jwt = require("jsonwebtoken");
const SECRETO = process.env.JWT_SECRET;          // sin valor por defecto
if (!SECRETO || SECRETO.length < 32) {
  throw new Error("JWT_SECRET ausente o débil");  // el arranque falla
}

function autenticar(req, res, next) {
  const [tipo, token] = (req.headers.authorization || "").split(" ");
  if (tipo !== "Bearer" || !token) {
    return res.status(401).json({ error: "No autenticado" });
  }
  try {
    req.usuario = jwt.verify(token, SECRETO,
      { algorithms: ["HS256"], maxAge: "15m" });
    return next();
  } catch {
    return res.status(401).json({ error: "Sesión inválida o expirada" });
  }
}

const requiereRol = (...roles) => (req, res, next) =>
  roles.includes(req.usuario.rol)
    ? next()
    : res.status(403).json({ error: "Acción no permitida" });

module.exports = { autenticar, requiereRol };

// app.js: toda ruta de negocio exige sesión
app.use(["/clientes", "/contratos", "/usuarios",
         "/empresa-usuarios", "/auditoria"], autenticar);

// Escritura sólo para administradores, siempre filtrada por empresa
router.delete("/:id", requiereRol("administrador"), async (req, res) => {
  /* UPDATE clientes SET deleted_at = now()
     WHERE id = $1 AND empresa_id = $2  -- req.usuario.empresaId */
});
""", "**a) Autenticación global y autorización por rol y empresa:**")
    inf.codigo("""
// routes/auth.js · bcrypt (TC-SEC-02) y política mínima (TC-SEC-18)
const bcrypt = require("bcrypt");
const POLITICA = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[^\\w\\s]).{12,}$/;

if (!POLITICA.test(password)) {
  return res.status(400).json({ error: "La contraseña no cumple la política" });
}
const hash = await bcrypt.hash(password, 12);                    // registro
const ok = await bcrypt.compare(password, user.contrasena_hash); // login
""", "**b) Contraseñas con bcrypt y política mínima:**")
    inf.codigo("""
// routes/contracts.js · archivos (TC-SEC-19) y propiedad del cliente (TC-SEC-08)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024, files: 1 },
});
const PERMITIDOS = ["application/pdf", "image/png", "image/jpeg",
  "application/msword", "application/vnd.ms-powerpoint"];

const { fileTypeFromBuffer } = await import("file-type");
const tipo = await fileTypeFromBuffer(req.file.buffer);  // tipo real
if (!tipo || !PERMITIDOS.includes(tipo.mime)) {
  return res.status(400).json({ error: "Tipo de archivo no permitido" });
}
const propio = await pool.query(
  "SELECT 1 FROM clientes WHERE id = $1 AND empresa_id = $2",
  [cliente_id, req.usuario.empresaId]);
if (propio.rowCount === 0) {
  return res.status(404).json({ error: "Cliente no encontrado" });
}
""", "**c) Validación de archivos y de propiedad del cliente:**")


def cap9(inf: Informe, H, inc):
    inf.h(1, "9. Plan de mantenimiento para futuras iteraciones")
    inf.p("El mantenimiento se planifica según los cuatro tipos que define ISO/IEC/IEEE 14764 (correctivo, preventivo, "
          "adaptativo y perfectivo) y se gestiona en un ciclo PDCA. La batería automatizada es el mecanismo que preserva la "
          "calidad entre iteraciones: ningún cambio se despliega sin pasar por ella.")
    inf.figura(DIAG / "D4_plan_mantenimiento.png", "Plan de mantenimiento: tipos ISO/IEC/IEEE 14764 en un ciclo PDCA.")
    inf.h(2, "9.1 Actividades y periodicidad")
    filas = [["Ejecución completa de run_todo.ps1 (regresión)", "Cada pull request y cada despliegue", "Pipeline CI", "Calidad y seguridad", "ISO/IEC/IEEE 29119"],
             ["SAST, secretos y SCA", "Cada commit", "Semgrep, Gitleaks, npm audit, Trivy", "Seguridad", "ISO 27001 A.8.8, A.8.28"],
             ["DAST y carga", "Nocturna sobre QA", "OWASP ZAP, k6", "Seguridad y rendimiento", "ISO 27001 A.8.29; ISO 25010"],
             ["Actualización de dependencias", "Semanal (Dependabot) y revisión mensual", "Dependabot / Renovate", "Seguridad", "OWASP A03:2025"],
             ["Rotación de secretos y credenciales", "Trimestral y ante incidente", "Gestor de secretos", "Seguridad", "ISO 27001 A.8.5"],
             ["Respaldo cifrado y prueba de restauración", "Diario / semanal", "pg_dump + script de restauración", "Disponibilidad", "ISO 27001 A.8.13; NFR-SEG-7"],
             ["Revisión de reglas SAST y del catálogo de casos", "Cada cambio del ERS", "catalogo.py, semgrep_atlas.yml", "Calidad", "ISO/IEC/IEEE 29119"],
             ["Pentest externo y prueba con usuarios mayores", "Anual o ante cambios mayores", "Equipo externo; 5 usuarios", "Seguridad y usabilidad", "OWASP ASVS; WCAG 2.1"],
             ["Revisión de cumplimiento de datos personales", "Semestral y ante cambio de tratamiento", "Matriz de cumplimiento", "Cumplimiento legal", "Leyes 19.628 y 21.719"]]
    inf.tabla(["Actividad", "Frecuencia", "Herramienta", "Preserva", "Referencia"], filas, [4.6, 3.2, 3.4, 2.4, 2.6],
              "Actividades de mantenimiento y su periodicidad.", size=8.5)
    inf.h(2, "9.2 Preservación de la seguridad")
    inf.bullets([
        "**Seguridad como requisito de regresión:** los 25 casos TC-SEC se mantienen en la batería; una vez corregido un "
        "defecto, su caso impide que reaparezca en una iteración posterior.",
        "**Gestión de vulnerabilidades por SLA:** los hallazgos nuevos se clasifican con CVSS v3.1 y se corrigen en los plazos "
        "de la escala de criticidad (crítica ≤ 7 días, alta ≤ 30 días).",
        "**Plataforma soportada:** la imagen base node:18 está fuera de soporte desde abril de 2025; el mantenimiento adaptativo "
        "la migra a Node 22 LTS y programa la siguiente migración antes de su fin de soporte.",
        "**Respuesta a incidentes:** registro centralizado sin datos sensibles, alertas ante patrones anómalos (por ejemplo, "
        "cambios de rol o accesos entre empresas) y un procedimiento documentado de contención y notificación.",
    ])
    inf.h(2, "9.3 Preservación del cumplimiento normativo y legal")
    inf.p("El cumplimiento se trata como un requisito verificable y no como una revisión ocasional. Cada obligación legal se "
          "asocia a un control técnico y a un caso de prueba:")
    filas = [["Deber de seguridad y confidencialidad (Ley 19.628 art. 11; Ley 21.719)", "Cifrado, control de acceso, aislamiento entre empresas", "TC-SEC-02, 03, 04, 05, 07"],
             ["Proporcionalidad y minimización (Ley 21.719)", "Enmascarar cuentas bancarias según el rol", "TC-SEC-16"],
             ["Reporte de vulneraciones de seguridad (Ley 21.719)", "Auditoría íntegra, logs y procedimiento de notificación", "TC-FUN-19, TC-SEC-14"],
             ["Derechos de los titulares (acceso, rectificación, supresión, oposición y portabilidad)", "Exportación de datos del cliente y anonimización al término de la retención", "Nuevo caso en la siguiente iteración"],
             ["Gestión de riesgos de ciberseguridad (Ley 21.663)", "Pipeline DevSecOps, respaldo y monitoreo", "TC-SEC-15, 21, 22, 23, 24"]]
    inf.tabla(["Obligación", "Control técnico", "Verificación"], filas, [6.4, 6.0, 3.8],
              "Trazabilidad entre obligaciones legales, controles y casos de prueba.", size=8.5)
    inf.p("Un punto que el plan debe resolver es la tensión entre la eliminación lógica exigida por el ERS y el derecho de "
          "supresión: conservar indefinidamente un cliente marcado como eliminado podría contravenir la ley. Se propone "
          "eliminación lógica con un plazo de retención definido, seguido de anonimización irreversible de los datos personales.")
    inf.h(2, "9.4 Evaluación del plan de mantenimiento")
    inf.p("Para evaluar el plan propuesto se comparó con dos alternativas habituales en pymes: el mantenimiento reactivo "
          "(corregir sólo cuando un usuario reporta una falla) y la auditoría manual periódica (una revisión de seguridad "
          "anual sin automatización).")
    filas = [["Detección temprana de defectos", "Baja: se detectan en producción", "Media: una vez al año", "Alta: en cada commit"],
             ["Costo por iteración", "Bajo hasta el incidente; muy alto después", "Alto (≈ 82 h por revisión)", f"Bajo (≈ {sum(TIEMPOS.values())/60:.0f} min de máquina)"],
             ["Cobertura de requerimientos", "Sin medición", "Parcial según el auditor", "100 % del ERS, medible"],
             ["Evidencia para auditorías y la Agencia", "Inexistente", "Informe puntual", "Continua y archivada"],
             ["Dependencia de personas", "Alta", "Alta", "Baja (requiere mantener la suite)"],
             ["Riesgo legal (Ley 21.719)", "Alto", "Medio", "Bajo"]]
    inf.tabla(["Criterio", "Reactivo", "Auditoría manual anual", "Plan propuesto (continuo)"], filas, [4.4, 3.8, 3.8, 4.2],
              "Evaluación comparativa de planes de mantenimiento.", size=8.5)
    inf.p("El plan propuesto es superior en todos los criterios salvo en el esfuerzo inicial, que ya está realizado (la suite "
          "existe y se ejecuta). Sus riesgos son la falsa sensación de seguridad si la suite no se actualiza junto con el ERS, "
          "los falsos positivos del SAST que pueden fatigar al equipo y la dependencia de la disponibilidad de las herramientas. "
          "Se mitigan revisando el catálogo en cada cambio del ERS, ajustando las reglas con excepciones documentadas y "
          "complementando con un pentest externo anual, que no se reemplaza por la automatización.")
    inf.h(2, "9.5 Indicadores de calidad sostenible")
    tot = contar()
    k6 = H.get("k6", {})
    axe_serias = sum(c.get("critical", 0) + c.get("serious", 0) for c in H.get("axe", {}).values())
    nb, nf = H["npm"].get("backend", {}), H["npm"].get("frontend", {})
    cve = nb.get("critical", 0) + nb.get("high", 0) + nf.get("critical", 0) + nf.get("high", 0)
    criticos = sum(1 for x in inc if x[4] == "Crítica")
    rec = re.search(r"([\d.]+) s", obtenido("TC-NFR-11"))
    filas = [["Casos en estado PASÓ", f"{100 * tot.get('PASÓ', 0) / len(CASOS):.0f} %", "≥ 95 %"],
             ["Incidentes críticos abiertos", str(criticos), "0"],
             ["Vulnerabilidades altas o críticas en dependencias", str(cve), "0"],
             ["Secretos en el repositorio", str(len(H["gitleaks"])), "0"],
             ["p95 de GET /clientes", f"{H.get('crud', {}).get('GET /clientes', {}).get('p95', 0):,} ms".replace(",", "."), "< 300 ms"],
             ["p95 con 200 usuarios (k6)", f"{k6.get('p95', 0):,.0f} ms".replace(",", ".") if k6 else "—", "< 300 ms"],
             ["Violaciones WCAG serias o críticas", str(axe_serias), "0"],
             ["Recuperación ante un corte de la base de datos", f"{rec.group(1)} s" if rec else "—", "< 60 s con healthcheck"],
             ["Restauraciones de respaldo exitosas", "0 (sin respaldo)", "100 % mensual"]]
    inf.tabla(["Indicador", "Línea base (medida)", "Meta"], filas, [8.4, 3.9, 3.9],
              "Indicadores de seguimiento con su línea base medida en esta ejecución.")
    inf.p("La línea base proviene de la ejecución automatizada de este informe, de modo que cada iteración futura podrá "
          "compararse objetivamente con ella y demostrar mejora continua.")


def cap10(inf: Informe, H, inc):
    tot = contar()
    cnt = Counter(x[4] for x in inc)
    inf.h(1, "10. Conclusiones")
    inf.p(f"La iteración final permitió verificar Atlas con {len(CASOS)} casos automatizados que cubren el 100 % de los "
          f"requerimientos del ERS. El resultado —{tot.get('PASÓ', 0)} casos aprobados y {tot.get('FALLÓ', 0)} fallidos, con "
          f"{cnt.get('Crítica', 0)} incidentes críticos— muestra un sistema funcionalmente operativo pero inseguro: un usuario "
          f"recién registrado puede convertirse en administrador de otra empresa y leer sus datos bancarios, cualquier persona "
          f"puede fabricar tokens con el secreto publicado y borrar contratos sin autenticarse. En su estado actual, Atlas no "
          f"es apto para producción.")
    inf.p("Combinar enfoques de prueba fue decisivo: el SAST genérico, el DAST y el SCA detectaron problemas de "
          "configuración y de dependencias, pero los defectos más graves —de autorización y aislamiento entre empresas— sólo "
          "aparecieron con reglas SAST propias derivadas del ERS y con pentesting dirigido. La automatización redujo el esfuerzo "
          "de un ciclo completo de unas 82 horas a minutos y, sobre todo, convirtió la verificación en una actividad repetible "
          "que puede ejecutarse en cada cambio.")
    inf.p("Las mitigaciones propuestas y el pipeline DevSecOps con compuertas automatizadas dan un camino concreto para "
          "corregir los incidentes por criticidad. El plan de mantenimiento, evaluado frente a alternativas reactivas y "
          "manuales, preserva la calidad, la seguridad y el cumplimiento de las Leyes 19.628, 21.719 y 21.663 a lo largo del "
          "ciclo de vida, con indicadores medibles cuya línea base quedó establecida en este informe.")


def referencias(inf: Informe):
    inf.h(1, "Referencias")
    refs = [
        "Biblioteca del Congreso Nacional de Chile. (1999). Ley N.º 19.628 sobre protección de la vida privada. https://www.bcn.cl/leychile",
        "Biblioteca del Congreso Nacional de Chile. (2024). Ley N.º 21.663, Ley marco de ciberseguridad. https://www.bcn.cl/leychile",
        "Biblioteca del Congreso Nacional de Chile. (2024). Ley N.º 21.719, que regula la protección y el tratamiento de los datos personales y crea la Agencia de Protección de Datos Personales. https://www.bcn.cl/leychile",
        "FIRST. (2019). Common Vulnerability Scoring System v3.1: Specification document. https://www.first.org/cvss/v3.1/specification-document",
        "International Organization for Standardization. (2022). ISO/IEC 27001:2022 Information security, cybersecurity and privacy protection — Information security management systems — Requirements.",
        "International Organization for Standardization. (2023). ISO/IEC 25010:2023 Systems and software engineering — Product quality model.",
        "ISO/IEC/IEEE. (2022). ISO/IEC/IEEE 14764:2022 Software engineering — Software life cycle processes — Maintenance.",
        "ISO/IEC/IEEE. (2022). ISO/IEC/IEEE 29119 Software and systems engineering — Software testing (partes 1 a 3).",
        "OWASP Foundation. (2025). OWASP Top 10:2025. https://owasp.org/Top10/2025/",
        "OWASP Foundation. (2021). Application Security Verification Standard 4.0.3. https://owasp.org/www-project-application-security-verification-standard/",
        "World Wide Web Consortium. (2018). Web Content Accessibility Guidelines (WCAG) 2.1. https://www.w3.org/TR/WCAG21/",
    ]
    for r in refs:
        par = inf.p(r)
        par.paragraph_format.left_indent = Cm(1.0)
        par.paragraph_format.first_line_indent = Cm(-1.0)
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT


def anexo(inf: Informe):
    inf.h(1, "Anexo A. Reproducción de la ejecución")
    inf.p("La batería completa puede reproducirse en cualquier equipo con Docker Desktop y Python 3.13:")
    inf.codigo("""
# 1) Levantar Atlas con datos semilla limpios
cd CodigoFuenteA
docker compose down -v
docker compose up -d

# 2) Preparar el entorno de pruebas (una sola vez)
cd ..\\EP5_Atlas
python -m venv .venv
.venv\\Scripts\\python -m pip install pytest requests pytest-html
.venv\\Scripts\\python -m pip install playwright axe-playwright-python python-docx
.venv\\Scripts\\python -m playwright install chromium firefox webkit

# 3) Ejecutar las 9 etapas y generar evidencias y reportes
powershell -ExecutionPolicy Bypass -File .\\run_todo.ps1

# 4) Regenerar diagramas, figuras de evidencia e informe
.venv\\Scripts\\python diagramas\\generar_diagramas.py
.venv\\Scripts\\python informe\\render_evidencias.py
.venv\\Scripts\\python informe\\capturas_entorno.py
.venv\\Scripts\\python informe\\generar_informe.py
""")
    inf.p("Estructura del repositorio de pruebas: pruebas/ (catálogo, suites pytest, carga k6), seguridad/ (reglas Semgrep "
          "propias), reportes/ (resultados.json y reportes HTML/JSON de cada herramienta), evidencias/ (transcripciones y "
          "capturas por caso), diagramas/ e informe/.")


def main():
    H = herramientas()
    inf = Informe()
    portada(inf)
    indice(inf)
    cap1(inf, H)
    cap2(inf, H)
    cap3(inf, H)
    cap4(inf, H)
    cap5(inf, H)
    cap6(inf, H)
    inc = cap7(inf, H)
    cap8(inf, H, inc)
    cap9(inf, H, inc)
    cap10(inf, H, inc)
    referencias(inf)
    anexo(inf)
    salida = BASE / "informe" / "EP5_Informe_Atlas_Seguridad_Automatizacion.docx"
    inf.guardar(salida)
    print("Informe generado:", salida)


if __name__ == "__main__":
    main()

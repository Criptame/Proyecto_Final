// Presentación de defensa del EP5 (Atlas, Caso A). Todas las cifras provienen de datos_deck.json,
// exportado desde los resultados reales de la ejecución (exportar_datos.py).
// Ejecución (Node en Docker): node build_deck.js  -> EP5_Defensa_Atlas.pptx
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.SKILL_DIR + "/scripts/apply_theme.js");

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "datos_deck.json"), "utf8"));
const EVID = path.join(__dirname, "..", "evidencias");

const THEME = {
  name: "Auditoria Atlas",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "17202A", lt1: "FFFFFF", dk2: "22344A", lt2: "EEF2F6",
    accent1: "C0392B", accent2: "17917F", accent3: "E39B2D", accent4: "34567A",
    accent5: "6B7A8C", accent6: "6B4FA0", hlink: "34567A", folHlink: "6B4FA0",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "EP5 · Auditoría de seguridad y automatización · Atlas (Caso A)";
pres.author = D.portada.integrante;
const C = pres.SchemeColor;

const num = (v, d = 0) => Number(v).toLocaleString("es-CL", { minimumFractionDigits: d, maximumFractionDigits: d });

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "PORTADA",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.7, w: 11.7, h: 1.9, fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "subtitulo", type: "body", x: 0.8, y: 3.8, w: 11.7, h: 0.9, fontSize: 20, color: C.background2, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "datos", type: "body", x: 0.8, y: 5.4, w: 11.7, h: 1.2, fontSize: 15, color: C.background1, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENIDO",
  background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 34, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "ISY1102 · EP5 · Sistema de Gestión Atlas (Caso A)", options: { x: 0.6, y: 7.02, w: 8, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});
pres.defineSlideMaster({
  title: "CIERRE",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 0.6, w: 11.7, h: 1.0, fontSize: 36, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: "B8C4D2", align: "right" },
});

// ------------------------------------------------------------------ componentes
const sombra = () => ({ type: "outer", color: "17202A", blur: 6, offset: 2, angle: 90, opacity: 0.12 });

function tarjeta(s, x, y, w, h, nombre, fill = C.background2) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { type: "none" }, objectName: nombre });
}
function pastilla(s, texto, x, y, w, fill, color = C.background1, nombre = "pastilla", h = 0.34) {
  s.addText(texto, { x, y, w, h, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.17, fill: { color: fill }, color, fontSize: 12, bold: true,
    align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: nombre });
}
function cifra(s, x, y, w, valor, etiqueta, color, nombre) {
  s.addText(valor, { x, y, w, h: 0.95, fontSize: 48, bold: true, color, margin: 0, valign: "bottom", isTextBox: true, objectName: nombre + " valor" });
  s.addText(etiqueta, { x, y: y + 1.0, w, h: 0.6, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: nombre + " etiqueta" });
}
function circuloNum(s, n, x, y, fill, nombre) {
  s.addText(String(n), { x, y, w: 0.5, h: 0.5, shape: pres.shapes.OVAL, fill: { color: fill }, color: C.background1, fontSize: 16, bold: true,
    align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: nombre });
}
const ejeChart = { catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent5, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", catAxisLabelFontSize: 13, valAxisLabelFontSize: 11, dataLabelFontSize: 12,
  valGridLine: { color: "D9E0E7", size: 0.75 }, catGridLine: { style: "none" } };

// ================================================================== 1. Portada
pres.addSection({ title: "Inicio" });
let s = pres.addSlide({ masterName: "PORTADA", sectionTitle: "Inicio" });
s.addText("Atlas: auditoría de seguridad y automatización de pruebas", { placeholder: "title" });
s.addText("Evaluación Parcial N.º 5 · ISY1102 Seguridad y Calidad en el Desarrollo de Software", { placeholder: "subtitulo" });
s.addText([
  { text: D.portada.integrante, options: { bold: true, breakLine: true } },
  { text: `${D.portada.carrera} · Sección ${D.portada.seccion}`, options: { breakLine: true } },
  { text: `Docente: ${D.portada.docente} · ${D.portada.fecha_entrega}` },
], { placeholder: "datos" });
s.addNotes(`Buenos días. Presento la iteración final del aseguramiento de calidad del Sistema de Gestión Atlas, el Caso A. ` +
  `En esta etapa ejecuté pruebas de seguridad con ocho enfoques distintos, automaticé toda la batería para que corra con un solo comando, ` +
  `diseñé los controles de seguridad automatizados del pipeline y propuse mitigaciones y un plan de mantenimiento. ` +
  `Todo lo que voy a mostrar proviene de una ejecución real sobre Atlas levantado en Docker, y se puede reproducir en vivo.`);

// ================================================================== 2. Resumen
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Inicio" });
s.addText("Atlas funciona, pero no es seguro", { placeholder: "title" });
cifra(s, 0.6, 1.5, 2.8, String(D.total), "casos automatizados\n100 % del ERS cubierto", C.text2, "Casos");
cifra(s, 3.6, 1.5, 2.8, `${num(D.total_min, 1)} min`, "batería completa\ncon un solo comando", C.accent4, "Duración");
cifra(s, 0.6, 3.5, 2.8, `${D.paso} / ${D.fallo}`, "PASÓ / FALLÓ\n0 bloqueados", C.accent2, "Resultado");
cifra(s, 3.6, 3.5, 2.8, String(D.severidad["Crítica"]), "incidentes críticos\n(CVSS ≥ 9,0 o herramienta)", C.accent1, "Críticos");
const pt = D.por_tipo;
s.addChart(pres.charts.BAR, [
  { name: "PASÓ", labels: ["Funcionales", "Seguridad", "No funcionales"], values: [pt["TC-FUN"]["PASÓ"] || 0, pt["TC-SEC"]["PASÓ"] || 0, pt["TC-NFR"]["PASÓ"] || 0] },
  { name: "FALLÓ", labels: ["Funcionales", "Seguridad", "No funcionales"], values: [pt["TC-FUN"]["FALLÓ"] || 0, pt["TC-SEC"]["FALLÓ"] || 0, pt["TC-NFR"]["FALLÓ"] || 0] },
], { x: 6.8, y: 1.45, w: 5.9, h: 4.3, barDir: "bar", barGrouping: "stacked", chartColors: [HEX.accent2, HEX.accent1],
  showValue: true, dataLabelPosition: "ctr", dataLabelColor: "FFFFFF", showLegend: true, legendPos: "b", legendFontSize: 13,
  showTitle: true, title: "Resultado por tipo de prueba", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: HEX.dk2,
  catAxisOrientation: "maxMin", valAxisHidden: true, ...ejeChart, objectName: "Resultado por tipo" });
tarjeta(s, 0.6, 5.85, 12.1, 0.9, "Veredicto");
s.addText([
  { text: "Veredicto: ", options: { bold: true, color: C.accent1 } },
  { text: "las funciones básicas operan, pero casi todos los controles de seguridad del ERS están ausentes. En su estado actual, Atlas no es apto para producción." },
], { x: 0.9, y: 5.85, w: 11.6, h: 0.9, fontSize: 16, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: "Veredicto texto" });
s.addNotes(`El mensaje principal es este: Atlas funciona, pero no es seguro. Diseñé ${D.total} casos que cubren el 100 % de los requerimientos del ERS, ` +
  `y toda la batería corre con un solo comando en ${num(D.total_min, 1)} minutos. ${D.paso} casos pasaron y ${D.fallo} fallaron, con ${D.severidad["Crítica"]} incidentes críticos. ` +
  `El gráfico muestra dónde está el problema: en funcionales la mitad aprueba, pero en seguridad sólo aprueba uno, la resistencia a inyección SQL. ` +
  `Por eso mi conclusión es que Atlas no es apto para producción en su estado actual.`);

// ================================================================== 3. Enfoques
pres.addSection({ title: "Pruebas de seguridad" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Pruebas de seguridad" });
s.addText("Ocho enfoques, cada uno ve algo distinto", { placeholder: "title" });
const npmAlto = D.npm.backend.critical + D.npm.backend.high + D.npm.frontend.critical + D.npm.frontend.high;
const zapMedio = (D.zap.frontend["Medio"] || 0) + (D.zap.api["Medio"] || 0);
const enfoques = [
  ["SAST", "Semgrep", `${D.semgrep_total} hallazgos en el código`, "Caja blanca"],
  ["Secretos", "Gitleaks", `${D.gitleaks} secretos expuestos (JWT en el README)`, "Caja blanca"],
  ["SCA", "npm audit · Trivy", `${npmAlto} dependencias altas o críticas`, "Caja blanca"],
  ["IaC", "Trivy config", `${D.trivy_conf} configuraciones inseguras (root)`, "Caja blanca"],
  ["DAST", "OWASP ZAP", `${zapMedio} alertas de riesgo medio (CSP, CORS)`, "Caja negra"],
  ["Pentest dirigido", "pytest + requests", "Toma de control entre empresas", "Caja gris"],
  ["Entradas negativas", "pytest · Playwright", "XSS, .exe aceptado, claves débiles", "Caja negra"],
  ["Caja blanca en BD", "psql", "Contraseñas y cuentas en claro", "Caja blanca"],
];
enfoques.forEach(([nombre, herr, hallazgo, vis], i) => {
  const x = 0.6 + (i % 4) * 3.07, y = 1.5 + Math.floor(i / 4) * 2.65;
  tarjeta(s, x, y, 2.82, 2.4, `Enfoque ${nombre}`);
  s.addText(nombre, { x: x + 0.2, y: y + 0.15, w: 2.45, h: 0.5, fontSize: 18, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: `Enfoque ${nombre} nombre` });
  pastilla(s, herr, x + 0.2, y + 0.72, 2.42, C.accent4, C.background1, `Enfoque ${nombre} herramienta`);
  s.addText(hallazgo, { x: x + 0.2, y: y + 1.18, w: 2.45, h: 0.8, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `Enfoque ${nombre} hallazgo` });
  s.addText(vis, { x: x + 0.2, y: y + 1.95, w: 2.45, h: 0.3, fontSize: 12, italic: true, color: C.accent5, margin: 0, isTextBox: true, objectName: `Enfoque ${nombre} visibilidad` });
});
s.addNotes(`Las pruebas de seguridad se pueden clasificar por lo que observan. El SAST analiza el código sin ejecutarlo; el escaneo de secretos busca claves en los archivos; ` +
  `el SCA revisa dependencias con vulnerabilidades conocidas; la revisión de IaC mira Dockerfile y compose. Todos son de caja blanca. ` +
  `El DAST, con OWASP ZAP, ataca la aplicación en ejecución como caja negra. El pentest dirigido usa conocimiento parcial, caja gris, para encadenar debilidades. ` +
  `Cada tarjeta muestra la herramienta real que usé y lo que encontró en Atlas. Cada enfoque tiene puntos ciegos, por eso usé los ocho.`);

// ================================================================== 4. Complementariedad
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Pruebas de seguridad" });
s.addText("Ningún enfoque detecta más de la mitad", { placeholder: "title" });
const V = "✔";
const filasComp = [
  ["Contraseñas en texto plano", V, "", "", "", "", V],
  ["Endpoints sin autenticación", V, "", "", "", V, ""],
  ["Toma de control entre empresas", "", "", "", "", V, ""],
  ["Secreto JWT publicado", V, V, "", "", V, ""],
  ["Dependencias vulnerables", "", "", V, "", "", ""],
  ["Contenedores root y BD expuesta", V, "", V, "", V, ""],
  ["Cabeceras y CORS", V, "", "", V, V, ""],
  ["Errores con detalle de la BD", V, "", "", "", V, ""],
  ["Archivos peligrosos aceptados", V, "", "", "", V, ""],
  ["Datos bancarios sin cifrar", "", "", "", "", "", V],
];
const cab = ["Hallazgo", "SAST", "Secretos", "SCA / IaC", "DAST", "Pentest", "Caja blanca"];
const hdr = cab.map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 }, align: t === "Hallazgo" ? "left" : "center" } }));
const cuerpo = filasComp.map((f, r) => f.map((v, i) => ({ text: v, options: {
  align: i === 0 ? "left" : "center", bold: i > 0, color: i > 0 ? C.accent2 : C.text1, fill: { color: r % 2 ? C.background1 : C.background2 } } })));
s.addTable([hdr, ...cuerpo], { x: 0.6, y: 1.45, w: 8.6, colW: [3.2, 0.9, 0.95, 0.95, 0.8, 0.9, 0.9], fontSize: 14, rowH: 0.42,
  border: { type: "solid", pt: 0.5, color: "D9E0E7" }, margin: [0, 0.08, 0, 0.08], valign: "middle", objectName: "Matriz de complementariedad" });
tarjeta(s, 9.6, 1.45, 3.1, 4.62, "Lectura de la matriz");
s.addText([
  { text: "Lo que muestra", options: { bold: true, fontSize: 18, breakLine: true } },
  { text: "ZAP no detectó ningún defecto de autorización: un escáner no sabe qué usuario debería ver qué dato.", options: { breakLine: true, paraSpaceAfter: 10 } },
  { text: "Los defectos más graves sólo aparecieron con reglas SAST propias y pentest dirigido.", options: { breakLine: true, paraSpaceAfter: 10 } },
  { text: "Por eso el pipeline integra todos los enfoques." },
], { x: 9.85, y: 1.65, w: 2.65, h: 4.3, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "Lectura texto" });
s.addNotes(`Esta matriz cruza los principales hallazgos con el enfoque que los detectó. La conclusión es que ningún enfoque cubre más de la mitad. ` +
  `Por ejemplo, ZAP encontró cabeceras faltantes y CORS abierto, pero no encontró ningún problema de autorización, porque un escáner automático ` +
  `no conoce la lógica de negocio. La toma de control entre empresas sólo la encontró el pentest dirigido, y los datos bancarios sin cifrar sólo se ven ` +
  `entrando a la base de datos. Esto justifica integrar todos los enfoques en el pipeline, no elegir uno.`);

// ================================================================== 5. Cadena crítica
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Pruebas de seguridad" });
s.addText("Un visitante se adueña de otra empresa", { placeholder: "title" });
const pasos = [
  ["Se registra", "Crea su propia empresa; su JWT revela su empresaUsuarioId."],
  ["Busca la víctima", "GET /empresas responde sin token con todas las empresas."],
  ["Se asigna como admin", "PUT /empresa-usuarios sin token: empresa víctima, rol 1."],
  ["Roba los datos", "Inicia sesión y lee clientes con RUT y cuenta bancaria."],
];
pasos.forEach(([t, d], i) => {
  const y = 1.55 + i * 1.12;
  circuloNum(s, i + 1, 0.6, y + 0.05, i === 3 ? C.accent1 : C.text2, `Paso ${i + 1} número`);
  s.addText(t, { x: 1.3, y, w: 3.9, h: 0.4, fontSize: 18, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: `Paso ${i + 1} título` });
  s.addText(d, { x: 1.3, y: y + 0.4, w: 3.9, h: 0.62, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `Paso ${i + 1} detalle` });
});
s.addImage({ path: path.join(EVID, "TC-SEC-07.png"), x: 5.55, y: 1.5, w: 7.15, h: 7.15 * 738 / 1816, objectName: "Evidencia TC-SEC-07", altText: "Transcripción de la prueba TC-SEC-07" });
pastilla(s, "TC-SEC-07", 5.55, 4.75, 1.5, C.text2, C.background1, "ID caso");
pastilla(s, "CVSS 9,8 · Crítica", 7.2, 4.75, 2.1, C.accent1, C.background1, "CVSS caso");
pastilla(s, "OWASP A01:2025", 9.45, 4.75, 1.9, C.accent4, C.background1, "OWASP caso");
s.addText("Mitigación: autenticación y rol administrador en /empresa-usuarios, empresa_id siempre desde el token y alerta ante cambios de rol.",
  { x: 5.55, y: 5.3, w: 7.15, h: 0.9, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Mitigación TC-SEC-07" });
s.addNotes(`Este es el hallazgo más grave, el TC-SEC-07, con CVSS 9,8. Un visitante sólo necesita registrarse. Su propio token le revela el identificador de su vínculo con la empresa. ` +
  `Luego pide la lista de empresas, que no exige token, y elige una víctima. Con un PUT sin token cambia su vínculo para quedar como administrador de esa empresa. ` +
  `Al volver a iniciar sesión, lee los clientes de la víctima con RUT y número de cuenta. Ojo con un detalle: la API responde error 500, pero el cambio ya quedó aplicado; ` +
  `por eso mis pruebas verifican el efecto en la base de datos y no sólo el código HTTP.`);

// ================================================================== 6. Críticos
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Pruebas de seguridad" });
s.addText("Seis hallazgos críticos, todos evitables", { placeholder: "title" });
const impacto = {
  "TC-SEC-07": "Usuario nuevo se vuelve administrador de otra empresa y lee sus cuentas.",
  "TC-SEC-17": "Con el secreto del README se fabrican tokens válidos de cualquier empresa.",
  "TC-SEC-25": "PostgreSQL acepta conexiones externas con postgres/postgres.",
  "TC-SEC-06": "Un anónimo borra contratos ajenos y no queda rastro en auditoría.",
  "TC-SEC-21": `npm audit: ${npmAlto} dependencias altas o críticas (incluida jws del JWT).`,
  "TC-SEC-23": `${D.gitleaks} secretos versionados en .env y README.`,
};
D.criticos.slice(0, 6).forEach((c, i) => {
  const x = 0.6 + (i % 3) * 4.1, y = 1.5 + Math.floor(i / 3) * 2.7;
  tarjeta(s, x, y, 3.85, 2.45, `Crítico ${c.id}`);
  pastilla(s, c.id, x + 0.2, y + 0.2, 1.45, C.text2, C.background1, `Crítico ${c.id} id`);
  pastilla(s, c.cvss ? `CVSS ${num(c.cvss, 1)}` : "Herramienta", x + 1.8, y + 0.2, 1.6, C.accent1, C.background1, `Crítico ${c.id} cvss`);
  s.addText(c.nombre, { x: x + 0.2, y: y + 0.68, w: 3.45, h: 0.7, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `Crítico ${c.id} nombre` });
  s.addText(impacto[c.id] || "", { x: x + 0.2, y: y + 1.4, w: 3.45, h: 0.9, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `Crítico ${c.id} impacto` });
});
s.addNotes(`Estos son los seis incidentes críticos. Cuatro tienen CVSS calculado sobre 9: la toma de control entre empresas, la falsificación de tokens con el secreto publicado, ` +
  `la base de datos expuesta con credenciales por defecto y el borrado anónimo de contratos. Los otros dos vienen de herramientas: dependencias con vulnerabilidades críticas ` +
  `y secretos versionados en el repositorio. Todos son evitables con prácticas estándar: autenticación global, gestión de secretos y no publicar el puerto de la base de datos.`);

// ================================================================== 7. SAST propio
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Pruebas de seguridad" });
s.addText(`Reglas SAST propias: de ${D.semgrep_publicas} a ${D.semgrep_total} hallazgos`, { placeholder: "title" });
cifra(s, 0.6, 1.5, 3.0, String(D.semgrep_publicas), "hallazgo con reglas\npúblicas de Semgrep", C.accent5, "SAST público");
cifra(s, 3.8, 1.5, 3.0, String(D.semgrep_total), `hallazgos al sumar ${D.semgrep_reglas_propias}\nreglas propias del ERS`, C.accent1, "SAST propio");
tarjeta(s, 0.6, 3.55, 6.2, 2.9, "Triage");
s.addText([
  { text: "Triage de falsos positivos", options: { bold: true, fontSize: 18, breakLine: true } },
  { text: "Validación «contraseña = confirmación» en el frontend: se acotó la regla al backend.", options: { bullet: true, breakLine: true, paraSpaceAfter: 6 } },
  { text: "POST /empresas es el registro público (RF-2.1): excepción aceptada y documentada.", options: { bullet: true, breakLine: true, paraSpaceAfter: 6 } },
  { text: "Las otras 13 rutas sin autenticación son verdaderos positivos.", options: { bullet: true } },
], { x: 0.85, y: 3.7, w: 5.75, h: 2.65, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "Triage texto" });
s.addText([
  { text: "# seguridad/semgrep_atlas.yml", options: { color: "8B949E", breakLine: true } },
  { text: "- id: atlas-contrasena-comparada-en-claro", options: { breakLine: true } },
  { text: "  severity: ERROR", options: { breakLine: true } },
  { text: "  pattern: $U.contrasena_hash !== $P", options: { breakLine: true } },
  { text: " ", options: { breakLine: true } },
  { text: "BACKEND/src/routes/auth.js:26", options: { color: "F2CC60", breakLine: true } },
  { text: "if (user.contrasena_hash !== password)", options: { color: "FF7B72" } },
], { x: 7.2, y: 1.5, w: 5.5, h: 2.6, fontFace: "Courier New", fontSize: 14, color: "E6EDF3", fill: { color: "0D1117" }, margin: 12,
  valign: "top", shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, isTextBox: true, objectName: "Regla de ejemplo" });
s.addText("Cada regla traduce un requisito del ERS (NFR-SEG-2, NFR-SEG-4, NFR-SEG-9…) en un patrón que el pipeline verifica en cada commit.",
  { x: 7.2, y: 4.35, w: 5.5, h: 1.2, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Regla explicación" });
s.addNotes(`Una lección importante: con las reglas públicas, Semgrep encontró sólo ${D.semgrep_publicas} hallazgo, que el contenedor corre como root. ` +
  `El SAST genérico no conoce la lógica de autorización de cada sistema. Por eso escribí ${D.semgrep_reglas_propias} reglas propias que traducen requisitos del ERS en patrones; ` +
  `por ejemplo, esta regla detecta que la contraseña se compara en texto plano en auth.js. Con ellas el análisis subió a ${D.semgrep_total} hallazgos. ` +
  `También hice triage: hubo dos falsos positivos, uno lo corregí ajustando la regla y el otro, el registro público, lo documenté como excepción.`);

// ================================================================== 8. Pipeline
pres.addSection({ title: "Controles automatizados" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Controles automatizados" });
s.addText("Seguridad automatizada en cada etapa", { placeholder: "title" });
const etapas = [
  ["Código", "Gitleaks pre-commit", "ISO 27001 A.8.28"],
  ["Pull request", "Semgrep · npm audit · Trivy · pytest", "ISO 27001 A.8.29 · A.8.8"],
  ["Construcción", "Trivy config · SBOM", "ISO 27001 A.8.9"],
  ["Ambiente QA", "OWASP ZAP · Playwright + axe · k6", "ISO 25010 · WCAG 2.1"],
  ["Compuerta", "0 críticas, 0 secretos, p95 < 300 ms", "ISO/IEC/IEEE 29119"],
  ["Operación", "TLS, respaldo, logs y alertas", "ISO 27001 A.8.13 · A.8.15"],
];
etapas.forEach(([t, herr, norma], i) => {
  const x = 0.6 + i * 2.05, fill = i === 4 ? C.accent3 : C.text2;
  tarjeta(s, x, 1.55, 1.85, 3.3, `Etapa ${t}`);
  circuloNum(s, i + 1, x + 0.68, 1.75, fill, `Etapa ${t} número`);
  s.addText(t, { x: x + 0.1, y: 2.35, w: 1.65, h: 0.45, fontSize: 16, bold: true, color: C.text1, align: "center", margin: 0, isTextBox: true, objectName: `Etapa ${t} nombre` });
  s.addText(herr, { x: x + 0.12, y: 2.85, w: 1.61, h: 1.15, fontSize: 14, color: C.text1, align: "center", valign: "top", margin: 0, isTextBox: true, objectName: `Etapa ${t} herramientas` });
  s.addText(norma, { x: x + 0.12, y: 4.05, w: 1.61, h: 0.7, fontSize: 12, italic: true, color: C.accent4, align: "center", valign: "top", margin: 0, isTextBox: true, objectName: `Etapa ${t} norma` });
  if (i < etapas.length - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.87, y: 3.05, w: 0.16, h: 0.3, fill: { color: C.accent5 }, line: { type: "none" }, objectName: `Flecha ${i + 1}` });
});
const leyes = [["Ley 19.628 art. 11", "cuidado diligente de los datos"], ["Ley 21.719", "seguridad, proporcionalidad y reporte de vulneraciones"], ["Ley 21.663", "gestión de riesgos de ciberseguridad"]];
leyes.forEach(([l, d], i) => {
  const x = 0.6 + i * 4.1;
  pastilla(s, l, x, 5.2, 1.9, C.accent3, C.text1, `Ley ${l}`);
  s.addText(d, { x: x + 2.0, y: 5.12, w: 2.0, h: 0.5, fontSize: 12, color: C.text2, margin: 0, valign: "middle", isTextBox: true, objectName: `Ley ${l} detalle` });
});
s.addText("Cada etapa es una compuerta: si un control falla, el cambio no avanza; la evidencia queda archivada para auditorías y para la Agencia de Protección de Datos.",
  { x: 0.6, y: 5.85, w: 12.1, h: 0.8, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Pipeline conclusión" });
s.addNotes(`Este es el diagrama de controles de seguridad automatizados. Es un pipeline DevSecOps de seis etapas: en el código, Gitleaks bloquea secretos antes del commit; ` +
  `en cada pull request corren Semgrep, npm audit, Trivy y la suite pytest; al construir la imagen, Trivy revisa el Dockerfile; en QA corren ZAP, Playwright con axe y k6. ` +
  `La compuerta de calidad, en ámbar, aplica los criterios de salida: cero críticas, cero secretos y p95 bajo 300 ms. Cada control está alineado con un control del Anexo A de ISO 27001 ` +
  `y con las leyes chilenas: la 19.628, la 21.719 que entra en vigencia prevista el 1 de diciembre de 2026, y la 21.663 de ciberseguridad.`);

// ================================================================== 9. Controles por capas
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Controles automatizados" });
const okTot = D.capas.reduce((a, c) => a + c.ok, 0), tot = D.capas.reduce((a, c) => a + c.total, 0);
s.addText(`Sólo ${okTot} de ${tot} controles funcionan`, { placeholder: "title" });
const nombresCapa = D.capas.map((c) => c.capa.replace(" (navegador)", "").replace(" (Express)", ""));
s.addChart(pres.charts.BAR, [
  { name: "Verificados", labels: nombresCapa, values: D.capas.map((c) => c.ok) },
  { name: "Ausentes o con falla", labels: nombresCapa, values: D.capas.map((c) => c.total - c.ok) },
], { x: 0.6, y: 1.45, w: 7.4, h: 5.0, barDir: "bar", barGrouping: "stacked", chartColors: [HEX.accent2, HEX.accent1], catAxisOrientation: "maxMin",
  showValue: true, dataLabelPosition: "ctr", dataLabelColor: "FFFFFF", dataLabelFormatCode: "0;;;", showLegend: true, legendPos: "b", legendFontSize: 13, valAxisHidden: true,
  showTitle: true, title: "Controles por capa (defensa en profundidad)", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: HEX.dk2, ...ejeChart,
  objectName: "Controles por capa" });
tarjeta(s, 8.4, 1.45, 4.3, 2.2, "Controles verificados", C.background2);
s.addText([
  { text: "Lo único que funciona", options: { bold: true, fontSize: 17, color: C.accent2, breakLine: true } },
  ...D.capas.flatMap((c) => c.verificados.map((v) => ({ text: `${v} · capa ${c.capa.split(" ")[0]}`, options: { bullet: true, breakLine: true } }))),
  { text: "Evitaron la ejecución del XSS almacenado y la inyección SQL.", options: { italic: true, color: C.text2 } },
], { x: 8.65, y: 1.6, w: 3.9, h: 1.95, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "Verificados texto" });
tarjeta(s, 8.4, 3.9, 4.3, 2.55, "Lectura capas", C.background2);
s.addText([
  { text: "Defensa en profundidad", options: { bold: true, fontSize: 17, breakLine: true } },
  { text: "Si un control falla, el de la capa siguiente debe contener el ataque. En Atlas no hay segunda línea: un solo defecto de autorización expone datos bancarios." },
], { x: 8.65, y: 4.05, w: 3.9, h: 2.3, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "Lectura capas texto" });
s.addNotes(`El segundo diagrama organiza los controles por capas, según el principio de defensa en profundidad. El estado de cada control sale de la ejecución real de la suite. ` +
  `De ${tot} controles exigidos por el ERS, OWASP e ISO 27001, sólo ${okTot} funcionan: el escape de salida de React, que evitó que el XSS almacenado se ejecutara, ` +
  `y las consultas parametrizadas, que neutralizan la inyección SQL. En las capas de borde, datos y operación no funciona ninguno. ` +
  `Por eso un solo defecto de autorización basta para exponer datos bancarios: no hay una segunda línea de defensa.`);

// ================================================================== 10. Automatización
pres.addSection({ title: "Automatización" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Automatización" });
s.addText(`Una batería, un comando, ${Math.round(D.total_min)} minutos`, { placeholder: "title" });
cifra(s, 0.6, 1.45, 3.6, "≈ 82 h", "esfuerzo manual estimado\npor ciclo completo", C.accent5, "Manual");
cifra(s, 0.6, 3.25, 3.6, `${num(D.total_min, 1)} min`, "ejecución automatizada\nmedida, sin intervención", C.accent2, "Automatizado");
tarjeta(s, 0.6, 5.1, 3.6, 1.45, "Comando");
s.addText([{ text: ".\\run_todo.ps1", options: { fontFace: "Courier New", bold: true, fontSize: 18, breakLine: true } },
  { text: "1 comando · 9 etapas · evidencia por caso", options: { fontSize: 14, color: C.text2 } }],
  { x: 0.8, y: 5.2, w: 3.3, h: 1.25, fontSize: 14, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: "Comando texto" });
const etiquetas = Object.keys(D.tiempos).map((k) => k.replace(" (funcional, seguridad, no funcional)", "").replace(" baseline", "").replace(" (200 VU)", ""));
s.addChart(pres.charts.BAR, [{ name: "Segundos", labels: etiquetas, values: Object.values(D.tiempos) }], {
  x: 4.6, y: 1.45, w: 8.1, h: 5.1, barDir: "bar", chartColors: [HEX.accent4], catAxisOrientation: "maxMin", showValue: true,
  dataLabelPosition: "outEnd", dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0", showLegend: false, valAxisHidden: true,
  showTitle: true, title: "Tiempo real por etapa (segundos)", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: HEX.dk2, ...ejeChart,
  catAxisLabelFontSize: 12, objectName: "Tiempo por etapa" });
s.addNotes(`La automatización es el corazón de esta entrega. Un catálogo único en Python define los ${D.total} casos con su requerimiento, OWASP, CWE, vector CVSS y mitigación, ` +
  `y desde ese mismo catálogo se generan las pruebas y el informe, por lo que el resumen y la matriz no pueden contradecirse. Con un solo comando, run_todo.ps1, ` +
  `corren nueve etapas en ${num(D.total_min, 1)} minutos; el gráfico muestra el tiempo real de cada una. Con supuestos conservadores, hacerlo a mano tomaría unas 82 horas, ` +
  `y la prueba de 200 usuarios simplemente no es factible manualmente. Además, la suite también se revisó: corregí tres casos cuya primera versión daba falsos resultados.`);

// ================================================================== 11. Resultados no funcionales
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Automatización" });
s.addText("Lento, poco accesible y frágil", { placeholder: "title" });
const ops = Object.keys(D.crud);
s.addChart(pres.charts.BAR, [{ name: "p95 (ms)", labels: ops.map((o) => o.replace("/autenticacion", "")), values: ops.map((o) => D.crud[o]) }], {
  x: 0.6, y: 1.45, w: 6.6, h: 5.0, barDir: "col", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: HEX.dk1, dataLabelFormatCode: "#,##0", showLegend: false, valAxisHidden: true,
  showTitle: true, title: "p95 por operación (ms) · umbral 300 ms", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: HEX.dk2, ...ejeChart,
  catAxisLabelFontSize: 11, objectName: "p95 por operación" });
const nf = [
  ["200 usuarios concurrentes", `p95 de ${num(D.k6.p95)} ms con ${num(D.k6.err * 100, 2)} % de errores (k6)`, C.accent1],
  ["Accesibilidad WCAG 2.1 AA", `${D.axe_serias} violaciones serias o críticas en 5 vistas (axe-core)`, C.accent3],
  ["Móvil", "El menú lateral no se colapsa y recorta el contenido (390 px)", C.accent3],
  ["Corte de la base de datos", `Derriba la API; Docker la reinicia en ${num(D.recuperacion_s, 1)} s sin healthcheck`, C.accent1],
];
nf.forEach(([t, d, col], i) => {
  const y = 1.45 + i * 1.28;
  tarjeta(s, 7.6, y, 5.1, 1.12, `NFR ${t}`);
  s.addShape(pres.shapes.OVAL, { x: 7.8, y: y + 0.36, w: 0.4, h: 0.4, fill: { color: col }, line: { type: "none" }, objectName: `NFR ${t} indicador` });
  s.addText([{ text: t, options: { bold: true, breakLine: true } }, { text: d, options: { fontSize: 14, color: C.text2 } }],
    { x: 8.4, y: y + 0.08, w: 4.15, h: 0.96, fontSize: 15, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: `NFR ${t} texto` });
});
s.addNotes(`En lo no funcional, las lecturas por identificador responden en milisegundos, pero los listados y el login tardan 4 segundos por una latencia artificial ` +
  `que también detectó una regla SAST: await delay de 4000. Con 200 usuarios concurrentes el sistema no colapsa, cero por ciento de errores, pero el p95 es de ${num(D.k6.p95)} milisegundos. ` +
  `axe-core encontró ${D.axe_serias} violaciones serias de accesibilidad, y en móvil el menú no se colapsa. Finalmente, al cortar las conexiones de la base de datos, ` +
  `la API se cae porque el pool de pg no maneja errores; Docker la reinicia en ${num(D.recuperacion_s, 1)} segundos, pero no hay healthcheck que detecte un proceso colgado.`);

// ================================================================== 12. Mitigación
pres.addSection({ title: "Mitigación y mantenimiento" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Mitigación y mantenimiento" });
s.addText("Remediación en tres oleadas", { placeholder: "title" });
const sev = D.severidad;
const oleadas = [
  ["Inmediata", "≤ 7 días", `${sev["Crítica"] || 0} críticas`, C.accent1, ["Rotar el secreto JWT y sacarlo del repositorio", "Autenticación global en la API", "Cerrar el puerto 15432", "Actualizar dependencias críticas"]],
  ["Corto plazo", "≤ 30 días", `${sev["Alta"] || 0} altas`, C.accent3, ["bcrypt y política de contraseñas", "RBAC y validación por empresa", "TLS, HSTS y límite de intentos", "Respaldo cifrado automatizado"]],
  ["Siguiente iteración", "planificada", `${(sev["Media"] || 0) + (sev["Baja"] || 0)} medias y bajas`, C.accent4, ["Cifrado de datos bancarios", "Eliminación lógica y auditoría completa", "Accesibilidad y diseño móvil", "Migraciones versionadas"]],
];
oleadas.forEach(([t, plazo, cant, col, acc], i) => {
  const x = 0.6 + i * 4.1;
  tarjeta(s, x, 1.5, 3.85, 3.75, `Oleada ${t}`);
  circuloNum(s, i + 1, x + 0.2, 1.7, col, `Oleada ${t} número`);
  s.addText([{ text: t, options: { bold: true, breakLine: true } }, { text: `${plazo} · ${cant}`, options: { fontSize: 14, color: C.text2 } }],
    { x: x + 0.85, y: 1.62, w: 2.85, h: 0.75, fontSize: 18, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `Oleada ${t} título` });
  s.addText(acc.map((a, k) => ({ text: a, options: { bullet: true, breakLine: k < acc.length - 1, paraSpaceAfter: 8 } })),
    { x: x + 0.25, y: 2.6, w: 3.4, h: 3.0, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `Oleada ${t} acciones` });
});
s.addText([{ text: "Verificación: ", options: { bold: true, color: C.accent2 } },
  { text: "cada mitigación se comprueba re-ejecutando su propio caso, que debe pasar de FALLÓ a PASÓ (prueba de regresión)." }],
  { x: 0.6, y: 5.55, w: 12.1, h: 0.6, fontSize: 16, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "Verificación mitigación" });
s.addNotes(`Cada uno de los ${D.fallo} incidentes tiene una mitigación concreta en el informe, y las agrupé en tres oleadas según criticidad. ` +
  `En los primeros siete días, las críticas: rotar el secreto JWT y sacarlo del repositorio, poner un middleware de autenticación global, cerrar el puerto de la base de datos ` +
  `y actualizar dependencias. En treinta días, las altas: bcrypt, control de acceso por rol y por empresa, TLS y límite de intentos. El resto en la siguiente iteración. ` +
  `Lo importante es que cada corrección se verifica con el mismo caso automatizado, que debe pasar de FALLÓ a PASÓ.`);

// ================================================================== 13. Mantenimiento
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Mitigación y mantenimiento" });
s.addText("Mantenimiento continuo frente a reactivo", { placeholder: "title" });
const tipos = [
  ["Correctivo", "Remediar por SLA según CVSS", C.accent1],
  ["Preventivo", "SAST, SCA y secretos en cada commit", C.accent4],
  ["Adaptativo", "Node 18 → 22 LTS; Ley 21.719", C.accent2],
  ["Perfectivo", "Accesibilidad y rendimiento", C.accent3],
];
tipos.forEach(([t, d, col], i) => {
  const x = 0.6 + (i % 2) * 2.95, y = 1.5 + Math.floor(i / 2) * 1.75;
  tarjeta(s, x, y, 2.75, 1.55, `Tipo ${t}`);
  s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.22, w: 0.32, h: 0.32, fill: { color: col }, line: { type: "none" }, objectName: `Tipo ${t} indicador` });
  s.addText(t, { x: x + 0.65, y: y + 0.15, w: 1.95, h: 0.45, fontSize: 17, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `Tipo ${t} nombre` });
  s.addText(d, { x: x + 0.2, y: y + 0.68, w: 2.4, h: 0.8, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `Tipo ${t} detalle` });
});
s.addText("Tipos ISO/IEC/IEEE 14764 gestionados en un ciclo PDCA: planificar, hacer, verificar con run_todo.ps1 y actuar.",
  { x: 0.6, y: 5.1, w: 5.65, h: 0.9, fontSize: 14, italic: true, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "PDCA" });
const evalHdr = ["Criterio", "Reactivo", "Auditoría anual", "Continuo"].map((t, i) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: i === 3 ? C.accent2 : C.text2 }, align: i ? "center" : "left" } }));
const evalFilas = [
  ["Detección de defectos", "En producción", "1 vez al año", "Cada commit"],
  ["Costo por ciclo", "Alto tras incidente", "≈ 82 h", `≈ ${Math.round(D.total_min)} min`],
  ["Cobertura del ERS", "Sin medir", "Parcial", "100 %"],
  ["Evidencia legal", "No hay", "Puntual", "Continua"],
  ["Riesgo Ley 21.719", "Alto", "Medio", "Bajo"],
].map((f, r) => f.map((v, i) => ({ text: v, options: { align: i ? "center" : "left", bold: i === 3, color: i === 3 ? C.accent2 : C.text1, fill: { color: r % 2 ? C.background1 : C.background2 } } })));
s.addTable([evalHdr, ...evalFilas], { x: 6.6, y: 1.5, w: 6.1, colW: [1.9, 1.45, 1.4, 1.35], fontSize: 14, rowH: 0.5,
  border: { type: "solid", pt: 0.5, color: "D9E0E7" }, margin: [0, 0.08, 0, 0.08], valign: "middle", objectName: "Evaluación de planes" });
s.addText("Riesgo del plan: falsa seguridad si la suite no evoluciona con el ERS; se mitiga revisando el catálogo en cada cambio y con un pentest externo anual.",
  { x: 6.6, y: 4.75, w: 6.1, h: 1.25, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Riesgo plan" });
s.addNotes(`Para el plan de mantenimiento usé los cuatro tipos de ISO/IEC/IEEE 14764: correctivo por SLA según CVSS, preventivo con controles en cada commit, ` +
  `adaptativo, por ejemplo migrar Node 18 que ya no tiene soporte y adecuarse a la Ley 21.719, y perfectivo en accesibilidad y rendimiento. Todo se gestiona en un ciclo PDCA. ` +
  `Evalué el plan contra dos alternativas típicas de una pyme: el mantenimiento reactivo y la auditoría manual anual. El plan continuo gana en detección temprana, costo y evidencia legal. ` +
  `Su riesgo es la falsa sensación de seguridad si la suite no se actualiza; por eso propongo revisar el catálogo en cada cambio del ERS y un pentest externo anual.`);

// ================================================================== 14. Indicadores
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Mitigación y mantenimiento" });
s.addText("Indicadores para demostrar mejora", { placeholder: "title" });
const kpis = [
  ["Casos en estado PASÓ", `${Math.round(100 * D.paso / D.total)} %`, "≥ 95 %"],
  ["Incidentes críticos abiertos", String(D.severidad["Crítica"] || 0), "0"],
  ["Dependencias altas o críticas", String(npmAlto), "0"],
  ["Secretos en el repositorio", String(D.gitleaks), "0"],
  ["p95 de GET /clientes", `${num(D.crud["GET /clientes"])} ms`, "< 300 ms"],
  ["Violaciones WCAG serias", String(D.axe_serias), "0"],
];
kpis.forEach(([t, base, meta], i) => {
  const x = 0.6 + (i % 3) * 4.1, y = 1.5 + Math.floor(i / 3) * 2.35;
  tarjeta(s, x, y, 3.85, 2.1, `KPI ${t}`);
  s.addText(t, { x: x + 0.2, y: y + 0.15, w: 3.45, h: 0.45, fontSize: 15, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: `KPI ${t} nombre` });
  s.addText(base, { x: x + 0.2, y: y + 0.65, w: 1.9, h: 0.8, fontSize: 32, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true, objectName: `KPI ${t} base` });
  s.addText([{ text: "meta", options: { fontSize: 12, color: C.text2, breakLine: true } }, { text: meta, options: { fontSize: 20, bold: true, color: C.accent2 } }],
    { x: x + 2.15, y: y + 0.65, w: 1.5, h: 0.8, margin: 0, valign: "middle", isTextBox: true, objectName: `KPI ${t} meta` });
  s.addText("línea base medida", { x: x + 0.2, y: y + 1.5, w: 3.45, h: 0.35, fontSize: 12, italic: true, color: C.accent5, margin: 0, isTextBox: true, objectName: `KPI ${t} nota` });
});
s.addText("La línea base proviene de esta ejecución: cada iteración futura se compara con ella para demostrar mejora continua (IL 3.5).",
  { x: 0.6, y: 6.25, w: 12.1, h: 0.5, fontSize: 15, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "KPI conclusión" });
s.addNotes(`Para que la mejora sea medible definí indicadores con su línea base real, medida en esta ejecución, y su meta. ` +
  `Hoy sólo el ${Math.round(100 * D.paso / D.total)} % de los casos pasa; la meta para producción es al menos 95 %. Hay ${D.severidad["Crítica"]} críticos abiertos, ${npmAlto} dependencias altas o críticas, ` +
  `${D.gitleaks} secretos en el repositorio, un p95 de 4 segundos y ${D.axe_serias} violaciones de accesibilidad; todas las metas son cero o bajo el umbral del ERS. ` +
  `Como la batería es automática, cada iteración futura produce estos mismos indicadores y se puede demostrar objetivamente si mejoró.`);

// ================================================================== 15. Cierre
pres.addSection({ title: "Cierre" });
s = pres.addSlide({ masterName: "CIERRE", sectionTitle: "Cierre" });
s.addText("Conclusiones", { placeholder: "title" });
const concl = [
  ["Calidad, seguridad y ley son inseparables", "Un defecto de autorización no es sólo técnico: expone datos bancarios protegidos por las Leyes 19.628 y 21.719."],
  ["Combinar enfoques fue decisivo", "Los hallazgos más graves sólo aparecieron con reglas SAST propias y pentest dirigido."],
  ["La automatización hace sostenible la calidad", `De ≈ 82 h a ${num(D.total_min, 1)} min por ciclo: la verificación se repite en cada cambio.`],
];
concl.forEach(([t, d], i) => {
  const y = 1.9 + i * 1.45;
  circuloNum(s, i + 1, 0.8, y + 0.05, C.accent3, `Conclusión ${i + 1} número`);
  s.addText([{ text: t, options: { bold: true, fontSize: 20, breakLine: true } }, { text: d, options: { fontSize: 15, color: C.background2 } }],
    { x: 1.55, y, w: 11.0, h: 1.2, color: C.background1, margin: 0, valign: "top", isTextBox: true, objectName: `Conclusión ${i + 1} texto` });
});
s.addText("Atlas no es apto para producción en su estado actual. ¿Preguntas?", { x: 0.8, y: 6.3, w: 11.7, h: 0.6, fontSize: 18, bold: true,
  color: HEX.accent3, margin: 0, valign: "middle", isTextBox: true, objectName: "Cierre mensaje" });
s.addNotes(`Para cerrar, tres ideas. Primero, calidad, seguridad y cumplimiento legal son inseparables: un defecto de autorización expone datos bancarios que la ley obliga a proteger. ` +
  `Segundo, combinar enfoques fue decisivo, porque los hallazgos más graves no los encuentra un escáner genérico. Tercero, la automatización convierte la verificación ` +
  `en algo repetible en cada cambio, lo que sostiene la calidad en el tiempo. Mi veredicto es que Atlas no es apto para producción hasta remediar al menos las oleadas uno y dos. ` +
  `Si lo desean, puedo ejecutar la batería en vivo. Quedo atento a sus preguntas.`);

// ------------------------------------------------------------------ guardar
(async () => {
  const salida = path.join(__dirname, "EP5_Defensa_Atlas.pptx");
  await pres.writeFile({ fileName: salida });
  await applyTheme(salida, THEME);
  console.log("ok", salida);
})();

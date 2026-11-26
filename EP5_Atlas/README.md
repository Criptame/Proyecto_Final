# EP5 · Atlas (Caso A) — Pruebas de seguridad y automatización

Batería automatizada de 59 casos (22 funcionales, 25 de seguridad y 12 no funcionales) que cubre el 100 % del ERS del
Sistema de Gestión Atlas, más el generador del informe Word.

## Ejecutar todo (≈ 16 min)

```powershell
cd ..\CodigoFuenteA
docker compose down -v
docker compose up -d
cd ..\EP5_Atlas
powershell -ExecutionPolicy Bypass -File .\run_todo.ps1
```

Regenerar figuras e informe a partir de los resultados:

```powershell
.venv\Scripts\python diagramas\generar_diagramas.py
.venv\Scripts\python informe\render_evidencias.py
.venv\Scripts\python informe\capturas_entorno.py   # entorno Docker, consola y reportes HTML
.venv\Scripts\python informe\generar_informe.py
```

Los datos de la portada se editan en `informe\datos_portada.json`.

Presentación de defensa (15 diapositivas con notas del orador), generada con pptxgenjs en un contenedor Node:

```powershell
.venv\Scripts\python presentacion\exportar_datos.py
docker run --rm -v "${PWD}:/work" -v "<carpeta del skill pptx>:/skill:ro" -w /work/presentacion -e SKILL_DIR=/skill -e NODE_PATH=/work/presentacion/node_modules node:22-alpine sh -c "npm install --silent pptxgenjs && node build_deck.js"
```

## Estructura

| Carpeta / archivo | Contenido |
|---|---|
| `pruebas/catalogo.py` | Fuente única de verdad: cada caso con requerimiento ERS, tipo, OWASP, CWE, vector CVSS, criterio y mitigación |
| `pruebas/api/` | pytest + requests: funcionales, seguridad (pentest), rendimiento, herramientas y disponibilidad |
| `pruebas/ui/` | Playwright + axe-core: accesibilidad, usabilidad, compatibilidad (4 navegadores) y responsividad |
| `pruebas/carga/k6_carga.js` | Prueba de carga con 200 usuarios virtuales |
| `seguridad/semgrep_atlas.yml` | 13 reglas SAST propias derivadas del ERS |
| `reportes/` | `resultados.json`, tiempos por etapa y reportes de Semgrep, Gitleaks, npm audit, Trivy, ZAP, k6 y pytest |
| `evidencias/` | Transcripción (`.txt`) y figura (`.png`) de cada caso, más capturas de la interfaz |
| `diagramas/` | Pipeline DevSecOps, controles por capas, flujo de automatización y plan de mantenimiento |
| `informe/` | Generador y documento final (`.docx` y `.pdf`) |

## Casos clave para la defensa

- **TC-SEC-07**: un usuario recién registrado se convierte en administrador de otra empresa y lee sus datos bancarios
  (GET /empresas público + PUT /empresa-usuarios sin token).
- **TC-SEC-17**: con el secreto JWT publicado en el README se fabrica un token válido de cualquier empresa.
- **TC-SEC-06**: un anónimo borra contratos ajenos; la API responde 500 pero el borrado ya ocurrió.
- **TC-SEC-10**: el único control efectivo (consultas parametrizadas contra inyección SQL).
- **TC-NFR-11**: un corte de la BD derriba la API porque el pool de `pg` no maneja errores.

<#
  EP5 · Atlas (Caso A) — Ejecución completa de la batería automatizada con un solo comando.

  Etapas: 1) SAST (Semgrep)  2) Secretos (Gitleaks)  3) SCA (npm audit + Trivy)  4) IaC (Trivy config)
          5) DAST (OWASP ZAP baseline)  6) Carga (k6, 200 VU)  7) API funcional/seguridad (pytest)
          8) Interfaz (Playwright + axe-core)  9) Disponibilidad (caída controlada de la API)

  Uso:   powershell -ExecutionPolicy Bypass -File .\run_todo.ps1
         powershell -ExecutionPolicy Bypass -File .\run_todo.ps1 -SoloPytest
  Requisitos: Docker Desktop en ejecución, Atlas levantado (docker compose up -d) y el entorno .venv.
#>
param([switch]$SoloPytest)

$ErrorActionPreference = "Continue"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$Base     = $PSScriptRoot
$Repo     = (Resolve-Path "$Base\..\CodigoFuenteA").Path
$Rep      = "$Base\reportes"
$Py       = "$Base\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force $Rep, "$Base\evidencias" | Out-Null
$tiempos = [ordered]@{}

function Etapa($nombre, [scriptblock]$bloque) {
    Write-Host "`n=== $nombre ===" -ForegroundColor Cyan
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & $bloque
    $sw.Stop()
    $tiempos[$nombre] = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    Write-Host ("    {0} s" -f $tiempos[$nombre]) -ForegroundColor DarkGray
}

function Guardar($archivo, $contenido) {
    [IO.File]::WriteAllText("$Rep\$archivo", ($contenido -join "`n"), (New-Object Text.UTF8Encoding($false)))
}

if (-not $SoloPytest) {
    Etapa "SAST - Semgrep" {
        # Rulesets públicos + reglas propias de Atlas (seguridad\semgrep_atlas.yml)
        $out = docker run --rm -v "${Repo}:/src:ro" -v "${Base}\seguridad:/reglas:ro" semgrep/semgrep semgrep scan `
            --metrics=off --json --quiet --config p/javascript --config p/nodejs --config p/owasp-top-ten --config p/jwt `
            --config p/react --config p/secrets --config /reglas/semgrep_atlas.yml /src
        Guardar "semgrep.json" $out
    }
    Etapa "Secretos - Gitleaks" {
        docker run --rm -v "${Repo}:/src:ro" -v "${Rep}:/out" zricethezav/gitleaks:latest dir /src `
            --report-format json --report-path /out/gitleaks.json --redact=60 --no-banner --exit-code 0
    }
    Etapa "SCA - npm audit" {
        foreach ($p in "BACKEND", "FRONTEND") {
            $out = docker run --rm -v "${Repo}\${p}:/app:ro" -w /app node:22-alpine npm audit --json --package-lock-only
            Guardar ("npm_audit_{0}.json" -f $p.ToLower()) $out
        }
    }
    Etapa "SCA - Trivy fs" {
        $out = docker run --rm -v "${Repo}:/src:ro" -v trivy-cache:/root/.cache aquasec/trivy:latest fs `
            --scanners vuln --format json --quiet /src
        Guardar "trivy_fs.json" $out
    }
    Etapa "IaC - Trivy config" {
        $out = docker run --rm -v "${Repo}:/src:ro" -v trivy-cache:/root/.cache aquasec/trivy:latest config `
            --format json --quiet /src
        Guardar "trivy_config.json" $out
    }
    Etapa "DAST - OWASP ZAP baseline" {
        docker run --rm -v "${Rep}:/zap/wrk:rw" zaproxy/zap-stable zap-baseline.py `
            -t http://host.docker.internal:3350 -J zap_frontend.json -r zap_frontend.html -I -m 2 | Out-Null
        docker run --rm -v "${Rep}:/zap/wrk:rw" zaproxy/zap-stable zap-baseline.py `
            -t http://host.docker.internal:4450/openapi.json -J zap_api.json -r zap_api.html -I -m 2 | Out-Null
    }
    Etapa "Carga - k6 (200 VU)" {
        $tok = (Invoke-RestMethod -Method Post -Uri http://localhost:4450/autenticacion/login `
                -ContentType "application/json" -Body '{"nombre_usuario":"admin","password":"admin"}').token
        docker run --rm -v "${Base}\pruebas\carga:/scripts:ro" -v "${Rep}:/out" -e API=http://host.docker.internal:4450 `
            -e TOKEN=$tok grafana/k6 run --quiet --summary-export=/out/k6_resumen.json /scripts/k6_carga.js
    }
}

Push-Location "$Base\pruebas"
Etapa "API - pytest (funcional, seguridad, no funcional)" {
    & $Py -m pytest api --ignore=api/test_zz_disponibilidad.py --html="$Rep\reporte_api.html" --self-contained-html
}
Etapa "Interfaz - Playwright + axe-core" {
    & $Py -m pytest ui --html="$Rep\reporte_ui.html" --self-contained-html
}
Etapa "Disponibilidad - caída controlada" {
    & $Py -m pytest api/test_zz_disponibilidad.py
}
Pop-Location

$tiempos | ConvertTo-Json | Set-Content -Encoding utf8 "$Rep\tiempos_etapas.json"
Write-Host "`nResultados: $Rep\resultados.json" -ForegroundColor Green
$tiempos.GetEnumerator() | Format-Table Name, Value -AutoSize

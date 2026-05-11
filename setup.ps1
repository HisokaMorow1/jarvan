# Setup automatizado de Jarvan en Windows + PowerShell.
# Maneja: venv, execution policy, pip por python -m, retry sin verificacion SSL.
#
# Uso (desde d:\jarvan):
#     .\setup.ps1
# o si esta bloqueada la ejecucion:
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Step "Verificando Python"
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "Python no encontrado en PATH. Instala Python 3.12 desde python.org y vuelve." -ForegroundColor Red
    exit 1
}
& python --version

Write-Step "Creando venv en .venv (si no existe)"
if (-not (Test-Path ".\.venv")) {
    & python -m venv .venv
} else {
    Write-Host "Ya existe .venv"
}

$pyexe = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pyexe)) {
    Write-Host "El venv no se creo correctamente." -ForegroundColor Red
    exit 1
}

Write-Step "Actualizando pip dentro del venv"
& $pyexe -m pip install --upgrade pip setuptools wheel

Write-Step "Instalando requirements.txt (intento 1: normal)"
$rc = 0
& $pyexe -m pip install -r requirements.txt
$rc = $LASTEXITCODE

if ($rc -ne 0) {
    Write-Step "Intento 2: con --trusted-host (por si es problema de certificado)"
    & $pyexe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r requirements.txt
    $rc = $LASTEXITCODE
}

if ($rc -ne 0) {
    Write-Step "Intento 3: mirror Tsinghua (rapido, suele pasar firewalls)"
    & $pyexe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
    $rc = $LASTEXITCODE
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "pip fallo en los 3 intentos. Posibles causas:" -ForegroundColor Yellow
    Write-Host "  - Sin internet en este equipo."
    Write-Host "  - Proxy/firewall de la red bloqueando pypi."
    Write-Host "  - Antivirus interfiriendo con la instalacion."
    Write-Host ""
    Write-Host "Plan B: usa hotspot del celular para la instalacion inicial," -ForegroundColor Yellow
    Write-Host "o pre-descarga wheels en otro PC con:" -ForegroundColor Yellow
    Write-Host "    pip download -r requirements.txt -d wheels" -ForegroundColor Gray
    Write-Host "y aqui:" -ForegroundColor Yellow
    Write-Host "    .\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt" -ForegroundColor Gray
    exit 1
}

Write-Step "Verificando Ollama"
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue)
if (-not $ollama) {
    Write-Host "Ollama no esta en PATH. Instalalo desde https://ollama.com" -ForegroundColor Yellow
} else {
    Write-Host "Ollama detectado:"
    & ollama list
}

Write-Step "Listo"
Write-Host "Activa el venv:" -ForegroundColor Green
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "Y ejecuta:" -ForegroundColor Green
Write-Host "    python main.py     (GUI)" -ForegroundColor Gray
Write-Host "    python cli.py      (texto)" -ForegroundColor Gray

# CivicRoute launcher. Double-click start.bat, or run:
#   powershell -ExecutionPolicy Bypass -File C:\Users\karth\civicroute\start.ps1
# Handles: wrong folder, missing packages, Docker not running / crashing, port already in use,
# a stale server from an earlier run, and opens the browser when the app is ready.
param([int]$Port = 8000, [switch]$NoDocker, [switch]$NoBrowser)

$root    = $PSScriptRoot
$backend = Join-Path $root "backend"
function Step($msg, $color = "Cyan") { Write-Host "==> $msg" -ForegroundColor $color }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. Python + packages
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python is not installed or not on PATH. Install Python 3.11+ from python.org (tick 'Add to PATH')."
}
python -c "import fastapi, uvicorn, sentence_transformers, psycopg, openai" 2>$null
if ($LASTEXITCODE -ne 0) {
    Step "Installing Python packages (one-time)..." Yellow
    python -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Fail "pip install failed - see the messages above." }
}
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Step "Web UI is not built (frontend\dist missing). The API will run; build the UI with: cd frontend; npm install; npm run build" Yellow
}

# Use the cached embedding model without network checks; on a fresh machine let it download once.
$model = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--intfloat--multilingual-e5-small"
if (Test-Path $model) { $env:HF_HUB_OFFLINE = "1" }
else { Step "First run: downloading the multilingual AI model (~470 MB, one time)..." Yellow }

# ---------------------------------------------------------------- 2. Database (optional)
function Test-Docker { docker info *> $null; return ($LASTEXITCODE -eq 0) }
$useDb = $false
if ($NoDocker) {
    Step "Skipping Docker (-NoDocker): using the built-in local index." Yellow
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    if (-not (Test-Docker)) {
        $dd = @("$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
                "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($dd) {
            Step "Docker Desktop is not running - starting it (up to 2 minutes)..."
            Start-Process $dd
            for ($i = 0; $i -lt 40 -and -not (Test-Docker); $i++) { Start-Sleep -Seconds 3 }
        }
    }
    if (Test-Docker) {
        Step "Starting the pgvector database..."
        docker compose -f (Join-Path $root "docker-compose.yml") up -d 2>&1 | Out-Null
        for ($i = 0; $i -lt 30; $i++) {
            if ((docker inspect -f "{{.State.Health.Status}}" civicroute-db 2>$null) -eq "healthy") { $useDb = $true; break }
            Start-Sleep -Seconds 2
        }
        if ($useDb) { Step "Database ready (pgvector)." Green }
        else { Step "Database did not become healthy - using the local index instead." Yellow }
    } else {
        Step "Docker engine is not available - using the built-in local index (the app works the same)." Yellow
        Write-Host "    If Docker Desktop shows an error dialog, close it fully and run:" -ForegroundColor DarkGray
        Write-Host '    Rename-Item "$env:LOCALAPPDATA\Docker\run" ("run.stale-" + (Get-Date -Format yyyyMMddHHmmss))' -ForegroundColor DarkGray
    }
} else {
    Step "Docker is not installed - using the built-in local index." Yellow
}
# auto = use DATABASE_URL from .env; memory = skip the database entirely (no connection delay)
$env:VECTOR_STORE = $(if ($useDb) { "auto" } else { "memory" })
$wantStore        = $(if ($useDb) { "PgVectorStore" } else { "MemoryStore" })

# ---------------------------------------------------------------- 3. Port / earlier server
function Get-Listener($p) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 }
$listener = Get-Listener $Port
if ($listener) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($proc -and $proc.CommandLine -match "app\.main:app" -and $proc.CommandLine -like "*civicroute*") {
        $health = $null
        try { $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 5 } catch { }
        if ($health -and $health.store -eq $wantStore) {
            Step "CivicRoute is already running on http://localhost:$Port - opening it." Green
            if (-not $NoBrowser) { Start-Process "http://localhost:$Port" }
            exit 0
        }
        Step "Stopping an earlier CivicRoute server (PID $($listener.OwningProcess)) so it restarts with the current settings..." Yellow
        Stop-Process -Id $listener.OwningProcess -Force
        for ($i = 0; $i -lt 10 -and (Get-Listener $Port); $i++) { Start-Sleep -Seconds 1 }
    } else {
        $other = $Port
        for ($p = $Port + 1; $p -le $Port + 20; $p++) { if (-not (Get-Listener $p)) { $Port = $p; break } }
        Step "Port $other is used by another program ($($proc.Name)) - using port $Port instead." Yellow
    }
}

# ---------------------------------------------------------------- 4. Run (browser opens when ready)
$url = "http://localhost:$Port"
if (-not $NoBrowser) {
    # A hidden helper process waits until the API answers, then opens the browser (Start-Job is unreliable
    # when PowerShell 5.1 is launched from a .bat file).
    $opener = "for (`$i = 0; `$i -lt 150; `$i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 " +
              "-Uri 'http://127.0.0.1:$Port/api/health' | Out-Null; Start-Process '$url'; exit } catch { Start-Sleep -Seconds 2 } }"
    Start-Process powershell -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $opener)
}
Step "Starting CivicRoute on $url (first start loads the AI model, about 1 minute; the browser opens automatically)." Green
Write-Host "    Press Ctrl+C in this window to stop the app." -ForegroundColor DarkGray
Set-Location $backend
# --app-dir puts the project path in the command line, so stop.bat / restarts only ever touch this app.
python -m uvicorn app.main:app --app-dir $backend --host 127.0.0.1 --port $Port
exit $LASTEXITCODE

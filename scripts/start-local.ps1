param([switch]$CheckOnly, [switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-processes.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $projectRoot 'backend'
$frontendDirectory = Join-Path $projectRoot 'frontend'
$databasePath = Join-Path $backendDirectory 'portfolio.db'
$pythonPath = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$nodePath = Join-Path $env:ProgramFiles 'nodejs/node.exe'
$vitePath = Join-Path $frontendDirectory 'node_modules/vite/bin/vite.js'

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.ConnectAsync('127.0.0.1', $Port)
        return ($pending.Wait(300) -and $client.Connected)
    } catch { return $false }
    finally { $client.Dispose() }
}

function Test-Service([string]$Kind) {
    try {
        if ($Kind -eq 'backend') {
            $response = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/' -TimeoutSec 2
            return ($response.payload.status -eq 'healthy' -and $response.payload.message -eq 'Portfolio Manager API is running')
        }
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -eq 200 -and $response.Content -match '<title>Portfolio Manager</title>')
    } catch { return $false }
}

try {
    foreach ($required in @($pythonPath, $nodePath, $vitePath, $databasePath, (Join-Path $backendDirectory 'run_local.py'))) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Brak pliku: $required" }
    }
    Write-Host 'Portfolio Manager - uruchamianie aplikacji'
    Write-Host "Folder: $projectRoot"
    Write-Host "Baza danych: $databasePath"

    $backendReady = Test-Service 'backend'
    $frontendReady = Test-Service 'frontend'
    if (-not $backendReady -and (Test-Port 5000)) { throw 'Port 5000 zajmuje inny program. Zwolnij port przed uruchomieniem backendu.' }
    if (-not $frontendReady -and (Test-Port 5173)) { throw 'Port 5173 zajmuje inny program. Zwolnij port przed uruchomieniem frontendu.' }
    if ($CheckOnly) {
        Write-Host "Sprawdzenie OK. Backend dziala: $backendReady. Frontend dziala: $frontendReady."
        exit 0
    }

    $backendProcess = $null
    $frontendProcess = $null
    if (-not $backendReady) {
        $previousPythonPath = $env:PYTHONPATH
        try {
            $env:PYTHONPATH = "$backendDirectory;$(Join-Path $backendDirectory '.runtime-deps');$(Join-Path $backendDirectory '.test-deps')"
            $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList ('"' + (Join-Path $backendDirectory 'run_local.py') + '"') -WorkingDirectory $backendDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $backendDirectory 'local-backend.stdout.log') -RedirectStandardError (Join-Path $backendDirectory 'local-backend.stderr.log') -PassThru
            Save-LocalServerProcess 'backend' $backendProcess.Id
            Write-Host 'Uruchamiam backend...'
        } finally { $env:PYTHONPATH = $previousPythonPath }
    } else { Write-Host 'Backend juz dziala - nie uruchamiam drugiej kopii.' }

    if (-not $frontendReady) {
        $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList ('"' + $vitePath + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort' -WorkingDirectory $frontendDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $frontendDirectory 'local-frontend.stdout.log') -RedirectStandardError (Join-Path $frontendDirectory 'local-frontend.stderr.log') -PassThru
        Save-LocalServerProcess 'frontend' $frontendProcess.Id
        Write-Host 'Uruchamiam frontend...'
    } else { Write-Host 'Frontend juz dziala - nie uruchamiam drugiej kopii.' }

    $deadline = (Get-Date).AddSeconds(40)
    do {
        if ($backendProcess -and $backendProcess.HasExited) { throw "Backend nie uruchomil sie. Sprawdz: $(Join-Path $backendDirectory 'local-backend.stderr.log')" }
        if ($frontendProcess -and $frontendProcess.HasExited) { throw "Frontend nie uruchomil sie. Sprawdz: $(Join-Path $frontendDirectory 'local-frontend.stderr.log')" }
        $backendReady = Test-Service 'backend'
        $frontendReady = Test-Service 'frontend'
        if ($backendReady -and $frontendReady) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    if (-not ($backendReady -and $frontendReady)) { throw 'Przekroczono czas uruchamiania. Sprawdz pliki local-backend.stderr.log i local-frontend.stderr.log.' }
    Write-Host 'Gotowe: http://127.0.0.1:5173/'
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173/' }
    exit 0
} catch {
    Write-Host "Nie udalo sie uruchomic aplikacji: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

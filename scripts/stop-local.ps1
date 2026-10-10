param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-processes.ps1')

try {
    Write-Host 'Portfolio Manager - wylaczanie serwerow'
    $records = @(Get-LocalServerRecords)
    if ($records.Count -eq 0) {
        Write-Host 'Brak zapisanych serwerow do wylaczenia.'
        exit 0
    }
    # Verify every process before stopping either service.
    $verified = @($records | ForEach-Object {
        $serverProcess = Get-VerifiedLocalServerProcess $_
        [pscustomobject]@{ Record = $_; Process = $serverProcess }
    })
    foreach ($server in $verified) {
        $label = if ($server.Record.Kind -eq 'backend') { 'Backend' } else { 'Frontend' }
        if (-not $server.Process) {
            Write-Host "$label juz jest wylaczony."
        } elseif ($CheckOnly) {
            Write-Host "$label rozpoznany poprawnie (proces $($server.Process.ProcessId))."
        } else {
            # Recheck the process identity immediately before stopping it.
            $currentProcess = Get-VerifiedLocalServerProcess $server.Record
            if ($currentProcess) {
                $nativeProcess = Get-Process -Id $currentProcess.ProcessId -ErrorAction SilentlyContinue
                if ($nativeProcess) {
                    # CIM truncates the sub-microsecond portion of the Windows timestamp.
                    $startDifference = $nativeProcess.StartTime.ToUniversalTime().Ticks - [long]$server.Record.StartedAt
                    if ([Math]::Abs($startDifference) -gt 10) {
                        throw 'Proces zmienil sie podczas wylaczania. Przerwano.'
                    }
                    Stop-Process -InputObject $nativeProcess -ErrorAction Stop
                    $nativeProcess.WaitForExit(5000) | Out-Null
                    if (-not $nativeProcess.HasExited) { throw "Nie udalo sie zatrzymac: $label" }
                }
            }
            Write-Host "$label wylaczony."
        }
    }
    if (-not $CheckOnly) {
        Remove-Item -LiteralPath $localProcessStatePath -ErrorAction SilentlyContinue
        Write-Host 'Gotowe. Backend i frontend sa wylaczone.'
    }
    exit 0
} catch {
    Write-Host "Nie udalo sie wylaczyc aplikacji: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

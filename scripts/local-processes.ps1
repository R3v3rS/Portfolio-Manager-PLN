$localProcessStatePath = Join-Path (Split-Path -Parent $PSScriptRoot) '.local-servers.json'

function Get-LocalServerRecords {
    if (Test-Path -LiteralPath $localProcessStatePath) {
        $savedRecords = Get-Content -LiteralPath $localProcessStatePath -Raw | ConvertFrom-Json
        foreach ($savedRecord in $savedRecords) { Write-Output $savedRecord }
        return
    }
    return @()
}

function Save-LocalServerProcess([string]$Kind, [int]$ServerProcessId) {
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ServerProcessId"
    if (-not $serverProcess) { throw "Nie znaleziono procesu: $ServerProcessId" }
    $records = @(Get-LocalServerRecords | Where-Object { $_.Kind -ne $Kind })
    $records += [pscustomobject]@{
        Kind = $Kind
        ProcessId = $ServerProcessId
        StartedAt = $serverProcess.CreationDate.ToUniversalTime().Ticks.ToString()
        ExecutablePath = $serverProcess.ExecutablePath
        CommandLine = $serverProcess.CommandLine
    }
    ConvertTo-Json -InputObject $records | Set-Content -LiteralPath $localProcessStatePath -Encoding UTF8
}

function Get-VerifiedLocalServerProcess($Record) {
    if ($Record.Kind -notin @('backend', 'frontend')) { throw 'Nieznany rodzaj serwera.' }
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$Record.ProcessId)"
    if (-not $serverProcess) { return $null }
    if ($serverProcess.CreationDate.ToUniversalTime().Ticks.ToString() -ne $Record.StartedAt -or
        $serverProcess.ExecutablePath -ne $Record.ExecutablePath -or
        $serverProcess.CommandLine -cne $Record.CommandLine) {
        throw "Proces $($Record.ProcessId) zostal zastapiony innym programem. Nie zostanie zatrzymany."
    }
    return $serverProcess
}

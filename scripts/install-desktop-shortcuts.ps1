$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot = Split-Path -Parent $PSScriptRoot
$iconDirectory = Join-Path $PSScriptRoot 'icons'
$desktopDirectory = [Environment]::GetFolderPath('Desktop')
New-Item -ItemType Directory -Path $iconDirectory -Force | Out-Null

function New-ServerIcon([string]$Name, [string]$Color, [bool]$Play) {
    $bitmap = New-Object System.Drawing.Bitmap 256, 256
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $shadow = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(65, 0, 0, 0))
    $background = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml($Color))
    $white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $graphics.FillEllipse($shadow, 12, 18, 232, 232)
    $graphics.FillEllipse($background, 12, 8, 232, 232)
    if ($Play) {
        $points = [System.Drawing.PointF[]]@(
            (New-Object System.Drawing.PointF 103, 66),
            (New-Object System.Drawing.PointF 190, 124),
            (New-Object System.Drawing.PointF 103, 182)
        )
        $graphics.FillPolygon($white, $points)
    } else {
        $graphics.FillRectangle($white, 80, 76, 96, 96)
    }
    $pngPath = Join-Path $iconDirectory "$Name.png"
    $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngBytes = [System.IO.File]::ReadAllBytes($pngPath)
    $stream = [System.IO.File]::Create((Join-Path $iconDirectory "$Name.ico"))
    $writer = New-Object System.IO.BinaryWriter $stream
    try {
        # A Windows ICO directory containing a 256px PNG image.
        $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]1)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$pngBytes.Length); $writer.Write([uint32]22)
        $writer.Write($pngBytes)
    } finally {
        $writer.Dispose(); $stream.Dispose()
        $graphics.Dispose(); $bitmap.Dispose()
        $shadow.Dispose(); $background.Dispose(); $white.Dispose()
    }
}

function Convert-FinanceIcon([string]$Name) {
    $sourceImage = [System.Drawing.Image]::FromFile((Join-Path $iconDirectory "$Name.png"))
    $entries = @()
    try {
        foreach ($size in @(16, 32, 48, 64, 128, 256)) {
            $bitmap = New-Object System.Drawing.Bitmap $size, $size
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $graphics.DrawImage($sourceImage, 0, 0, $size, $size)
            $memory = New-Object System.IO.MemoryStream
            $bitmap.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
            $entries += [pscustomobject]@{ Size = $size; Bytes = $memory.ToArray() }
            $memory.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
        }
        $stream = [System.IO.File]::Create((Join-Path $iconDirectory "$Name.ico"))
        $writer = New-Object System.IO.BinaryWriter $stream
        try {
            $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$entries.Count)
            $offset = 6 + 16 * $entries.Count
            foreach ($entry in $entries) {
                $dimension = if ($entry.Size -eq 256) { 0 } else { $entry.Size }
                $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
                $writer.Write([byte]0); $writer.Write([byte]0)
                $writer.Write([uint16]1); $writer.Write([uint16]32)
                $writer.Write([uint32]$entry.Bytes.Length); $writer.Write([uint32]$offset)
                $offset += $entry.Bytes.Length
            }
            foreach ($entry in $entries) { $writer.Write([byte[]]$entry.Bytes) }
        } finally { $writer.Dispose(); $stream.Dispose() }
    } finally { $sourceImage.Dispose() }
}

Convert-FinanceIcon 'finance-start'
Convert-FinanceIcon 'finance-stop'
$shortcutShell = New-Object -ComObject WScript.Shell
$launcherSettings = @(
    @{ Name = 'Włącz Portfolio Manager'; Script = 'start-local.ps1'; Icon = 'finance-start'; Description = 'Włącz backend i frontend Portfolio Manager' },
    @{ Name = 'Wyłącz Portfolio Manager'; Script = 'stop-local.ps1'; Icon = 'finance-stop'; Description = 'Wyłącz tylko backend i frontend Portfolio Manager' }
)
foreach ($launcher in $launcherSettings) {
    $shortcutPath = Join-Path $desktopDirectory ($launcher.Name + '.lnk')
    $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot $launcher.Script) + '"'
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = (Join-Path $iconDirectory ($launcher.Icon + '.ico')) + ',0'
    $shortcut.Description = $launcher.Description
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    $verifiedShortcut = $shortcutShell.CreateShortcut($shortcutPath)
    if ($verifiedShortcut.Arguments -ne $shortcut.Arguments -or $verifiedShortcut.IconLocation -ne $shortcut.IconLocation) {
        throw "Nie udalo sie zweryfikowac skrotu: $shortcutPath"
    }
    Write-Host "Gotowy skrot: $shortcutPath"
}

# Keep the previous command files in the project, leaving only the two clear shortcuts on the desktop.
$backupDirectory = Join-Path $PSScriptRoot 'desktop-launchers'
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
foreach ($originalName in @('Uruchom Portfolio Manager.cmd', 'Wylacz Portfolio Manager.cmd')) {
    $originalPath = Join-Path $desktopDirectory $originalName
    $backupPath = Join-Path $backupDirectory $originalName
    if ((Test-Path -LiteralPath $originalPath) -and -not (Test-Path -LiteralPath $backupPath)) {
        Move-Item -LiteralPath $originalPath -Destination $backupPath
    }
}

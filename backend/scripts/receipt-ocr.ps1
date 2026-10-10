param([Parameter(Mandatory=$true)][string]$ImagePath, [switch]$Diagnostic)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

$script:AsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await-Result($operation, [Type]$resultType) {
    $task = $script:AsTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}
function Await-Action($operation) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
    } | Select-Object -First 1
    $task = $method.Invoke($null, @($operation))
    $task.Wait()
}
try {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) { throw 'OCR language is unavailable.' }
    $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $streams = @()
    $pages = @()
    if ([IO.Path]::GetExtension($ImagePath) -eq '.pdf') {
        [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime] | Out-Null
        $pdf = Await-Result ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
        if ($pdf.PageCount -gt 3) { throw 'A receipt can contain at most three PDF pages.' }
        for ($i=0; $i -lt $pdf.PageCount; $i++) {
            $page = $pdf.GetPage($i)
            $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
            $options = [Windows.Data.Pdf.PdfPageRenderOptions]::new()
            $options.DestinationWidth = 1600
            Await-Action ($page.RenderToStreamAsync($stream, $options))
            $stream.Seek(0)
            $streams += $stream
            $pages += $page
        }
    } else {
        $streams += Await-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    }
    $lines = @()
    $wordPages = @()
    foreach ($stream in $streams) {
        $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $transform = [Windows.Graphics.Imaging.BitmapTransform]::new()
        $scale = [Math]::Min(1, [Windows.Media.Ocr.OcrEngine]::MaxImageDimension / [Math]::Max($decoder.PixelWidth, $decoder.PixelHeight))
        $transform.ScaledWidth = [Math]::Max(1, [Math]::Floor($decoder.PixelWidth * $scale))
        $transform.ScaledHeight = [Math]::Max(1, [Math]::Floor($decoder.PixelHeight * $scale))
        $bitmap = Await-Result ($decoder.GetSoftwareBitmapAsync(
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore,
            $transform,
            [Windows.Graphics.Imaging.ExifOrientationMode]::RespectExifOrientation,
            [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage
        )) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines += @($result.Lines | ForEach-Object { $_.Text })
        $words = @($result.Lines | ForEach-Object { $_.Words } | ForEach-Object {
            [pscustomobject]@{ text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y;
                width=$_.BoundingRect.Width; height=$_.BoundingRect.Height }
        })
        $wordPages += [pscustomobject]@{ words=$words; angle=$result.TextAngle;
            width=$bitmap.PixelWidth; height=$bitmap.PixelHeight }
        $bitmap.Dispose()
        $stream.Dispose()
    }
    foreach ($page in $pages) { $page.Dispose() }
    [pscustomobject]@{ text=($lines -join "`n"); pages=$wordPages; language=$engine.RecognizerLanguage.LanguageTag; local=$true } | ConvertTo-Json -Depth 6 -Compress
} catch {
    if ($Diagnostic) { [Console]::Error.WriteLine($_.Exception.ToString()) }
    [pscustomobject]@{ error='Local OCR could not read this file.'; text=''; local=$true } | ConvertTo-Json -Compress
    exit 1
}

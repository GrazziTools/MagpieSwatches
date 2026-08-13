<#
Runs every tests\test_*.py against both supported Blender versions and reports
PASS/FAIL per file. This is the release gate: ALL files green on BOTH
Blenders, not just one file (see CLAUDE.md's reporting rule).

--background exits 0 even when the script raises, so success is judged by
scanning stdout+stderr for "Traceback" or "RESULT: FAIL", not by exit code.

Usage:
    powershell -File tests\run_all.ps1
    powershell -File tests\run_all.ps1 -Versions 5.2
#>
param(
    [string[]]$Versions = @("4.2", "5.2")
)

$ErrorActionPreference = "Stop"
$testsDir = $PSScriptRoot
$anyBad = $false

foreach ($v in $Versions) {
    $blender = "C:\Program Files\Blender Foundation\Blender $v\blender.exe"
    if (-not (Test-Path $blender)) {
        Write-Host "SKIP    Blender $v not found at $blender" -ForegroundColor Yellow
        continue
    }
    Get-ChildItem (Join-Path $testsDir "test_*.py") | ForEach-Object {
        $out = Join-Path $env:TEMP "$($_.BaseName)_$v.log"
        # The script's own path (this repo lives under "Magpie Swatches", a
        # folder name with a space) must be individually quoted inside the
        # ArgumentList array -- unquoted, Start-Process rebuilds the child
        # command line by splitting on whitespace and the path arrives split
        # in two, which Blender then reports as a missing file.
        $proc = Start-Process $blender -ArgumentList @(
            "--background", "--factory-startup", "--python", "`"$($_.FullName)`""
        ) -NoNewWindow -Wait -PassThru `
          -RedirectStandardOutput $out -RedirectStandardError "$out.err"

        $text = (Get-Content $out -Raw -ErrorAction SilentlyContinue) +
                (Get-Content "$out.err" -Raw -ErrorAction SilentlyContinue)
        $bad = ($text -match "Traceback") -or ($text -match "RESULT: FAIL") -or
               ($proc.ExitCode -ne 0)

        if ($bad) {
            $anyBad = $true
            Write-Host ("FALHOU  {0} [{1}]  -> {2}" -f $_.Name, $v, $out) -ForegroundColor Red
        } else {
            Write-Host ("ok      {0} [{1}]" -f $_.Name, $v) -ForegroundColor Green
        }
    }
}

if ($anyBad) {
    Write-Host "`nPortao FALHOU -- ver os .log acima." -ForegroundColor Red
    exit 1
} else {
    Write-Host "`nPortao OK -- todos os arquivos verdes." -ForegroundColor Green
    exit 0
}

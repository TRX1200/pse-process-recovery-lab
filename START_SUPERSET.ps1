$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$taskPython = Join-Path $PSScriptRoot 'local/superset-venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Install the isolated Superset environment first. See docs/RF_MATCHING_KR.md.'
}
& $taskPython -m analytics_tools.serve_superset
exit $LASTEXITCODE

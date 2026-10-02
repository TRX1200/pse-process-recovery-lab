$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$labPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $labPython)) {
    throw 'Create .venv with Python 3.12 and install native_lab/requirements.txt first. See docs/NATIVE_SIMULATOR_KR.md.'
}
if (-not (Test-Path -LiteralPath 'sim_app\frontend\dist\index.html')) {
    throw 'Build the frontend first: cd sim_app/frontend; pnpm install; pnpm build'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $labPython -m native_lab.server

param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend\dist\index.html'))) {
    throw 'Build the interface first: cd sim_app/frontend; pnpm install; pnpm build'
}
$taskPython = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $taskPython) {
    throw 'Python 3.10+ is required. Install dependencies from sim_app/requirements.txt.'
}
& $taskPython.Source (Join-Path $PSScriptRoot 'server.py') --port $Port
exit $LASTEXITCODE

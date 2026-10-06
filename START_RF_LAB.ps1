param([int]$Port = 8768)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
& .\.venv\Scripts\python.exe -m rf_lab.server --port $Port

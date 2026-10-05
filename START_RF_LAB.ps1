$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
& .\.venv\Scripts\python.exe -m rf_lab.server --port 8767

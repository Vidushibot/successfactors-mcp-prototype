$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Run scripts\setup_windows.ps1 first." }
Start-Process -FilePath $python -ArgumentList "-m", "sf_mcp_poc.mcp_server" -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath $python -ArgumentList "-m", "sf_mcp_poc.main" -WorkingDirectory $root -WindowStyle Hidden
Start-Process -FilePath $python -ArgumentList "-m", "streamlit", "run", "src\sf_mcp_poc\streamlit_app.py", "--server.address", "127.0.0.1", "--server.port", "8501" -WorkingDirectory $root -WindowStyle Hidden
Write-Host "Streamlit: http://127.0.0.1:8501"
Write-Host "FastAPI:   http://127.0.0.1:8000"
Write-Host "API docs:  http://127.0.0.1:8000/docs"
Write-Host "MCP:       http://127.0.0.1:8001/mcp"

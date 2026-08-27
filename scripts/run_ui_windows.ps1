$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project environment not found. Run .\scripts\setup_windows.ps1 first."
}

$mcpServer = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if (-not $mcpServer) {
    Write-Host "Starting the read-only MCP server in the background..."
    Start-Process -FilePath $python -ArgumentList "-m", "sf_mcp_poc.mcp_server" -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

$backend = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $backend) {
    Write-Host "FastAPI is not running. Starting it in the background..."
    Start-Process -FilePath $python -ArgumentList "-m", "sf_mcp_poc.main" -WorkingDirectory $root -WindowStyle Hidden

    $ready = $false
    foreach ($attempt in 1..20) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
            if ($health.status -eq "ok") {
                $ready = $true
                break
            }
        }
        catch {
            # Continue briefly while FastAPI starts.
        }
    }
    if (-not $ready) {
        throw "FastAPI did not become healthy on http://127.0.0.1:8000."
    }
    Write-Host "FastAPI is healthy at http://127.0.0.1:8000"
}

Set-Location -LiteralPath $root
& $python -m streamlit run src\sf_mcp_poc\streamlit_app.py --server.address 127.0.0.1 --server.port 8501

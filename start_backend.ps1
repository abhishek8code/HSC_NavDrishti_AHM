#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start the NavDrishti backend server
.DESCRIPTION
    Starts the FastAPI backend on port 8002 with SQLite database. Frees the port if occupied.
#>

Write-Host "🚀 Starting NavDrishti Backend..." -ForegroundColor Cyan

# Set working directory
Set-Location $PSScriptRoot

# Configure environment
$env:DATABASE_URL = "sqlite:///./navdrishti.db"
$env:SQLALCHEMY_DATABASE_URL = $env:DATABASE_URL

# Check if virtual environment exists
$venvPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPath)) {
    Write-Host "❌ Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Free port 8002 if already in use
try {
    $listeners = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
    if ($listeners) {
        Write-Host "⚠️  Port 8002 is in use. Stopping owning processes..." -ForegroundColor Yellow
        $listeners | ForEach-Object {
            try {
                $pid = $_.OwningProcess
                if ($pid) {
                    Get-Process -Id $pid -ErrorAction SilentlyContinue | Stop-Process -Force
                    Write-Host "   • Killed PID $pid holding 8002" -ForegroundColor DarkYellow
                }
            } catch {}
        }
        Start-Sleep -Milliseconds 300
    }
} catch {}

# Start the backend
Write-Host "📡 Backend will be available at http://localhost:8002" -ForegroundColor Green
Write-Host "📄 API docs at http://localhost:8002/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

& $venvPath -m uvicorn Traffic_Backend.main:app --host 0.0.0.0 --port 8002 --reload

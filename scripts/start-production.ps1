$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $taskRoot 'backend')
try {
  & uv sync --locked --no-dev
  if ($LASTEXITCODE) { throw 'Dependency installation failed' }
  & '.\.venv\Scripts\python.exe' -m alembic upgrade head
  if ($LASTEXITCODE) { throw 'Migration failed' }
  & '.\.venv\Scripts\python.exe' -m alembic check
  if ($LASTEXITCODE) { throw 'Schema check failed' }
  & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
} finally { Pop-Location }

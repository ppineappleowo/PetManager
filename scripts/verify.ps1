param([switch]$Browsers)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Push-Location (Join-Path $taskRoot 'backend')
try {
  $env:RUN_POSTGRES_TESTS='1'
  $env:TEST_REDIS_URL='redis://127.0.0.1:6379/15'
  & '.\.venv\Scripts\python.exe' -m unittest discover -s tests
  if ($LASTEXITCODE) { throw 'Backend tests failed' }
  & '.\.venv\Scripts\python.exe' -m alembic check
  if ($LASTEXITCODE) { throw 'Migration drift detected' }
} finally { Pop-Location }
Push-Location (Join-Path $taskRoot 'frontend')
try {
  & node --test tests/unit.test.js
  if ($LASTEXITCODE) { throw 'Frontend tests failed' }
  & node node_modules/vite/bin/vite.js build
  if ($LASTEXITCODE) { throw 'Build failed' }
  if ($Browsers) {
    $env:RUN_API_E2E='1'
    & node node_modules/@playwright/test/cli.js test
    if ($LASTEXITCODE) { throw 'Browser tests failed' }
  }
} finally { Pop-Location }

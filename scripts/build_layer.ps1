# Construye la Lambda Layer de Pillow SIN Docker.
# Descarga las ruedas (wheels) precompiladas para Linux x86_64 / Python 3.12.
$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root "layer\python"
$reqs   = Join-Path $root "layer\requirements.txt"

if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Force -Path $target | Out-Null

python -m pip install `
    --platform manylinux2014_x86_64 `
    --platform manylinux_2_28_x86_64 `
    --implementation cp `
    --python-version 3.12 `
    --only-binary=:all: `
    --target $target `
    -r $reqs

if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de la layer" }
Write-Host "Layer lista en $target" -ForegroundColor Green

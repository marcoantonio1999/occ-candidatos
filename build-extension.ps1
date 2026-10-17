param([string]$Node = 'node')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $Node --test extension-tests/extension.test.mjs
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de la extensión.' }
$extensionFolder = Join-Path $PSScriptRoot 'extension'
$manifest = Get-Content -LiteralPath (Join-Path $extensionFolder 'manifest.json') -Raw | ConvertFrom-Json
$files = @('manifest.json','model.mjs','capture.mjs','worker.mjs','xlsx.mjs','panel.html','panel.css','panel.mjs','LEEME.md')
foreach ($file in $files) { if (-not (Test-Path -LiteralPath (Join-Path $extensionFolder $file))) { throw "Falta $file" } }
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'dist') -Force | Out-Null
$zip = Join-Path $PSScriptRoot ('dist\Extension-Candidatos-Manual-' + $manifest.version + '.zip')
if (Test-Path -LiteralPath $zip) { throw 'Ese ZIP ya existe. Conserva el anterior y prepara otra versión antes de publicar.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) { [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, (Join-Path $extensionFolder $file), $file) | Out-Null }
} finally { $archive.Dispose() }
Get-FileHash -LiteralPath $zip -Algorithm SHA256
Write-Host "Extensión lista: $zip"

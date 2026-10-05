param([string]$Python = 'python', [switch]$SkipAppBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $Python -m unittest discover -p 'test*.py'
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas.' }
if (-not $SkipAppBuild) {
    & $Python -m PyInstaller --noconfirm --clean --onefile --noconsole --name OCC-Candidatos --add-data 'pantalla.html;.' --collect-all selenium occ_app.py
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo construir la aplicacion.' }
}
$buildFolder = Join-Path $PSScriptRoot 'release-staging'
New-Item -ItemType Directory -Path $buildFolder -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dist\OCC-Candidatos.exe') -Destination $buildFolder -Force
$selfTest = Join-Path $buildFolder ('self-test-' + [Guid]::NewGuid().ToString('N') + '.txt')
$check = Start-Process -FilePath (Join-Path $buildFolder 'OCC-Candidatos.exe') -ArgumentList @('--self-test', ('"' + $selfTest + '"')) -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $selfTest)) { throw 'No paso la prueba del ejecutable.' }
$installer = Join-Path $PSScriptRoot 'dist\OCC-Candidatos-Instalador.exe'
& $Python -m PyInstaller --noconfirm --clean --onefile --noconsole --name OCC-Candidatos-Instalador --add-data 'dist\OCC-Candidatos.exe;.' --add-data 'licenses;licenses' occ_installer.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $installer)) { throw 'No se genero el instalador.' }
$installerTest = Join-Path $buildFolder ('installer-test-' + [Guid]::NewGuid().ToString('N') + '.txt')
$check = Start-Process -FilePath $installer -ArgumentList @('--self-test', ('"' + $installerTest + '"')) -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $installerTest)) { throw 'No paso la prueba del instalador.' }
Get-FileHash -LiteralPath $installer -Algorithm SHA256 | Format-List
Write-Host "Instalador listo: $installer"

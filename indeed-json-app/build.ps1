param([string]$Python='python')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -m unittest discover -s indeed-json-app -v
if($LASTEXITCODE -ne 0){throw 'Fallaron las pruebas'}
& $Python -m PyInstaller --noconfirm --clean --onefile --noconsole --name Indeed-JSON-BPower --exclude-module PIL --exclude-module numpy --exclude-module cryptography --collect-all pypdf indeed-json-app/app.py
if($LASTEXITCODE -ne 0){throw 'Falló la compilación de la app'}
& $Python -m PyInstaller --noconfirm --clean --onefile --noconsole --name Indeed-JSON-BPower-Instalador --add-data 'dist/Indeed-JSON-BPower.exe;.' --add-data 'indeed-json-app/licenses;licenses' indeed-json-app/installer.py
if($LASTEXITCODE -ne 0){throw 'Falló la compilación del instalador'}
Get-FileHash dist/Indeed-JSON-BPower*.exe -Algorithm SHA256

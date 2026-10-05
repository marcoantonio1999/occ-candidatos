@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR.ps1"
 if errorlevel 1 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 echo No se pudo preparar la herramienta. Revisa tu conexion y vuelve a abrir ABRIR.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" occ_app.py
pause

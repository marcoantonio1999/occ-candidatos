@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Primero ejecuta INSTALAR.bat. Necesitas Python instalado y Chrome.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" occ_app.py
pause

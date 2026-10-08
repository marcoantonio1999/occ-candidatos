"""Instalador por usuario: incluye la aplicación, no descarga Python."""
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = '1.1.0'
PAYLOAD = Path(__file__).resolve().parent / 'OCC-Candidatos.exe'


def install_payload(folder, payload=PAYLOAD):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'OCC-Candidatos-{VERSION}.exe'
    temporary = folder / f'OCC-Candidatos-{VERSION}.instalando'
    shutil.copyfile(payload, temporary)
    with temporary.open('r+b') as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    licenses = Path(__file__).resolve().parent / 'licenses'
    if licenses.exists():
        shutil.copytree(licenses, folder / 'licenses', dirs_exist_ok=True)
    return target


def shortcuts(target):
    # Los nombres de carpeta se pasan como datos, no como código de PowerShell.
    script = r'''
    $ErrorActionPreference = 'Stop'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($place in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        $link = $shell.CreateShortcut((Join-Path $place 'Candidatos de OCC.lnk'))
        $link.TargetPath = $env:OCC_INSTALL_APP
        $link.WorkingDirectory = $env:OCC_INSTALL_FOLDER
        $link.Description = 'Descargar candidatos de OCC y Computrabajo en Excel'
        $link.Save()
    }
    '''
    env = {**os.environ, 'OCC_INSTALL_APP': str(target), 'OCC_INSTALL_FOLDER': str(target.parent)}
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   env=env, capture_output=True, timeout=30, check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    message = ctypes.windll.user32.MessageBoxW
    if message(None, 'Se instalará Candidatos de OCC y Computrabajo y se actualizará el acceso de tu escritorio.\n\nNo necesitas instalar Python. Tus candidatos y tu avance anterior se conservan en esta computadora.\n\nPulsa Aceptar para instalar.', 'Instalar Candidatos', 0x41) != 1:
        return
    folder = Path(os.environ['LOCALAPPDATA']) / 'OCC-Candidatos'
    try:
        target = install_payload(folder)
    except Exception:
        message(None, 'No pudimos completar la instalación. Cierra Candidatos de OCC si está abierto y vuelve a intentar. Tu avance guardado no se borra.', 'Candidatos de OCC', 0x10)
        return
    try:
        shortcuts(target)
    except Exception:
        message(None, 'La herramienta se instaló, pero no pudimos crear el acceso del escritorio. Se abrirá ahora; solicita ayuda para crear el acceso después.', 'Candidatos de OCC', 0x30)
    try:
        subprocess.Popen([str(target)], cwd=folder, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        message(None, 'La herramienta se instaló. Abre Candidatos de OCC desde tu escritorio.', 'Candidatos de OCC', 0x40)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        assert PAYLOAD.exists() and PAYLOAD.stat().st_size > 1000000
        with PAYLOAD.open('rb') as handle:
            assert handle.read(2) == b'MZ'
        Path(sys.argv[2]).write_text('OK: aplicación incluida en el instalador', encoding='utf-8')
    else:
        main()

"""Separate per-user installer. No administrator rights or downloads."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
VERSION = '1.0.0'

PAYLOAD = Path(__file__).resolve().parent / 'Indeed-JSON-BPower.exe'


def install(folder, payload=PAYLOAD):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'Indeed-JSON-BPower-{VERSION}.exe'
    temp = folder / f'Indeed-JSON-BPower-{VERSION}.instalando'
    shutil.copyfile(payload, temp)
    with temp.open('r+b') as handle:
        os.fsync(handle.fileno())
    os.replace(temp, target)
    licenses = Path(__file__).resolve().parent / 'licenses'
    if licenses.exists():
        shutil.copytree(licenses, folder / 'licenses', dirs_exist_ok=True)
    return target


def shortcuts(target):
    script = r'''
    $ErrorActionPreference='Stop'
    $shell=New-Object -ComObject WScript.Shell
    foreach($place in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){
      $link=$shell.CreateShortcut((Join-Path $place 'Indeed JSON a Excel BPower.lnk'))
      $link.TargetPath=$env:INDEED_JSON_APP
      $link.WorkingDirectory=$env:INDEED_JSON_FOLDER
      $link.Description='Convertir JSON de Indeed a Excel localmente'
      $link.Save()
    }
    '''
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   env={**os.environ, 'INDEED_JSON_APP': str(target), 'INDEED_JSON_FOLDER': str(target.parent)},
                   capture_output=True, timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    box = ctypes.windll.user32.MessageBoxW
    folder = Path(os.environ['LOCALAPPDATA']) / 'Indeed-JSON-BPower'
    if box(None, f'Instalar Indeed JSON a Excel BPower {VERSION}\n\nSe instalará sólo para tu usuario en:\n{folder}\n\nEs independiente de Candidatos OCC y de la extensión. No necesita Python ni descarga componentes.\n\n¿Continuar?', 'Instalar Indeed JSON a Excel', 0x24) != 6:
        return
    try:
        target = install(folder)
        shortcuts(target)
    except Exception:
        box(None, 'No se pudo completar la instalación. Revisa permisos y espacio disponible. No se modificaron tus postulaciones.', 'Instalación incompleta', 0x10)
        return
    box(None, 'Instalación terminada. Encontrarás el acceso «Indeed JSON a Excel BPower» en el escritorio y en Inicio.', 'Indeed JSON a Excel', 0x40)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        if PAYLOAD.stat().st_size < 1_000_000 or PAYLOAD.open('rb').read(2) != b'MZ':
            raise SystemExit(2)
        Path(sys.argv[2]).write_text('OK ' + VERSION, encoding='utf-8')
    else:
        main()

"""Interfaz privada local. El avance se guarda antes de abrir cada perfil."""
import copy
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from occ_prueba import ROOT, URL, DISCOVER, norm, allowed_profile, extract_profile, extract_sections, select_candidates, unique, export_xlsx

ASSETS = Path(__file__).resolve().parent

def row_count(data):
    rows = data.get('rows', [])
    return len(rows if data.get('platform') == 'computrabajo' else unique(rows))


class Progress:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(exist_ok=True)
        self.path = self.folder / 'avance.json'
        self.lock = threading.RLock()
        self.data = None
        self.busy = False
        self.awaiting = False
        self.ready = threading.Event()
        self.pause = threading.Event()
        self.message = 'Elige una opción para comenzar.'
        for candidate in (self.path, self.path.with_suffix('.bak')):
            if candidate.exists():
                try:
                    data = json.loads(candidate.read_text(encoding='utf-8'))
                    if data.get('version') != 1 or data.get('mode') not in ('seen', 'unseen', 'all'):
                        raise ValueError('Formato inválido')
                    for key in ('candidates', 'rows', 'done'):
                        if not isinstance(data.get(key), list):
                            raise ValueError('Formato inválido')
                    self.data = data
                    self.message = 'Encontramos tu avance guardado. Puedes continuar o descargar lo recopilado.'
                    break
                except (ValueError, OSError, TypeError, AttributeError):
                    self.message = 'No pudimos leer el avance guardado. Conserva esta carpeta y solicita ayuda.'
        if self.data is None and self.path.exists():
            self.message = 'No pudimos leer el avance guardado. No inicies otra descarga en esta carpeta.'

    def save(self):
        with self.lock:
            raw = json.dumps(self.data, ensure_ascii=False, indent=2)
            temp = self.path.with_suffix('.tmp')
            with temp.open('w', encoding='utf-8') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            # Una copia anterior permite recuperarse si el archivo principal se daña.
            if self.path.exists():
                backup = self.path.with_suffix('.bak')
                backup_temp = self.path.with_suffix('.bak.tmp')
                backup_temp.write_bytes(self.path.read_bytes())
                os.replace(backup_temp, backup)
            os.replace(temp, self.path)

    def status(self):
        with self.lock:
            data = self.data or {}
            return dict(message=self.message, busy=self.busy, saved=bool(self.data),
                        vacancy=data.get('vacancy', ''), mode=data.get('mode', 'all'),
                        platform=data.get('platform', 'occ'), action=data.get('action', 'new'),
                        count=row_count(data), reviewed=len(data.get('done', [])),
                        total=len(data.get('selected', [])), pages=data.get('pages', 0),
                        complete=data.get('complete', False), waiting=self.busy and self.awaiting and not self.ready.is_set())

    def previous_rows(self, platform, vacancy, offer):
        from computrabajo import merge_rows
        rows = []
        for path in sorted(self.folder.glob('avance-anterior-*.json')):
            old = json.loads(path.read_text(encoding='utf-8'))
            if old.get('complete') and old.get('platform','occ') == platform and old.get('offer_id') == offer:
                rows = merge_rows(rows, old.get('rows',[]))
        return rows

    def begin(self, vacancy, mode, resume=False, consent=False, platform='occ', action='new'):
        with self.lock:
            if self.busy:
                raise ValueError('Ya hay una descarga en marcha.')
            if resume:
                if not self.data or self.data.get('complete'):
                    raise ValueError('No hay una descarga pendiente para continuar.')
            else:
                if platform not in ('occ','computrabajo') or action not in ('new','update'):
                    raise ValueError('Elige la plataforma y el tipo de descarga.')
                if platform == 'computrabajo' and mode != 'all':
                    raise ValueError('Computrabajo permite descargar todos los candidatos.')
                if platform == 'occ' and action != 'new':
                    raise ValueError('Actualizar Excel está disponible para Computrabajo.')
                if action == 'update':
                    histories = [self.data] if self.data else []
                    histories += [json.loads(x.read_text(encoding='utf-8')) for x in self.folder.glob('avance-anterior-*.json')]
                    if not any(x.get('complete') and x.get('platform') == platform and x.get('rows') for x in histories):
                        raise ValueError('Primero descarga una vacante de Computrabajo en esta computadora. Después podrás actualizar su Excel.')
                if self.data and not self.data.get('complete'):
                    raise ValueError('Primero continúa la descarga pendiente. Tu avance está protegido.')
                if self.path.exists() and self.data is None:
                    raise ValueError('Conserva tu avance y solicita ayuda antes de iniciar otra descarga.')
                vacancy = ' '.join(str(vacancy).split())
                if not vacancy or len(vacancy) > 160 or mode not in ('seen', 'unseen', 'all'):
                    raise ValueError('Escribe el nombre de la vacante y elige qué candidatos descargar.')
                if mode != 'seen' and not consent:
                    raise ValueError('Confirma el aviso sobre los candidatos no vistos.')
                if self.data:
                    # Conservar también los trabajos anteriores y sus Excel.
                    archive = self.folder / ('avance-anterior-' + str(time.time_ns()) + '.json')
                    archive.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
                self.data = dict(version=1, vacancy=vacancy, mode=mode, platform=platform, action=action, candidates=[], selected=[],
                                 rows=[], done=[], pages=0, listed=False, complete=False, skipped=0)
                self.save()
            self.busy = True
            self.awaiting = False
            self.ready.clear()
            self.pause.clear()
            self.message = 'Abriendo la plataforma. Espera a que aparezca su ventana.'
            worker = collect
            if self.data.get('platform') == 'computrabajo':
                from computrabajo import collect as worker
            threading.Thread(target=worker, args=(self,), daemon=True).start()

    def excel(self):
        with self.lock:
            if not self.data or not self.data['rows']:
                raise ValueError('Todavía no hay candidatos recopilados para descargar.')
            rows = copy.deepcopy(self.data['rows'])
            deduplicate = self.data.get('platform') != 'computrabajo'
        destination = self.folder / ('postulados-' + str(time.time_ns()) + '.xlsx')
        export_xlsx(rows, destination, deduplicate=deduplicate)
        return destination


def collect(progress):
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        import re
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--user-data-dir=' + str(ROOT / 'perfil-occ'))
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.get(URL)
        progress.message = 'En la ventana de OCC, inicia sesión y selecciona la vacante indicada. Después vuelve aquí y pulsa «Ya estoy en la vacante».'
        progress.awaiting = True
        while not progress.ready.wait(.3):
            if progress.pause.is_set():
                return
        data = progress.data
        progress.awaiting = False
        if urlsplit(driver.current_url).hostname != 'empresa.occ.com.mx':
            raise ValueError('Abre OCC e inicia sesión antes de continuar.')
        if not data['listed']:
            signatures = set()
            page = 0
            while not progress.pause.is_set():
                page_items = WebDriverWait(driver, 25).until(lambda d: d.execute_script(DISCOVER))
                signature = tuple(item['url'] for item in page_items)
                if signature in signatures:
                    raise ValueError('La lista repitió una página. Pausamos para no dejar candidatos fuera.')
                signatures.add(signature)
                with progress.lock:
                    known = {item['url'] for item in data['candidates']}
                    data['candidates'].extend(item for item in page_items if item['url'] not in known)
                    page += 1
                    data['pages'] = max(data['pages'], page)
                    progress.save()
                progress.message = f'Revisando página {page}. El avance se está guardando.'
                buttons = [el for el in driver.find_elements(By.CSS_SELECTOR, 'button') if el.is_displayed() and norm(el.text) == 'siguiente']
                if len(buttons) > 1:
                    raise ValueError('No pudimos identificar la siguiente página. Tu avance está guardado.')
                if not buttons or not buttons[0].is_enabled() or buttons[0].get_attribute('aria-disabled') == 'true':
                    with progress.lock:
                        data['selected'] = select_candidates(data['candidates'], data['mode'])
                        data['listed'] = True
                        progress.save()
                    break
                buttons[0].click()
                WebDriverWait(driver, 25).until(lambda d: tuple(item['url'] for item in d.execute_script(DISCOVER)) not in ((), signature))
            if progress.pause.is_set():
                return
        for candidate in data['selected']:
            if progress.pause.is_set():
                return
            url = candidate['url']
            if url in data['done']:
                continue
            if not allowed_profile(url):
                raise ValueError('OCC cambió un enlace. Pausamos la descarga para revisarlo.')
            # La lista completa y sus estados originales ya están en disco.
            progress.save()
            progress.message = f'Recopilando candidato {len(data["done"])+1} de {len(data["selected"])}. No cierres la ventana de OCC.'
            driver.get(url)
            body = WebDriverWait(driver, 25).until(lambda d: d.find_element(By.TAG_NAME, 'body').text or False)
            if re.search(r'(?i)captcha|verifica que eres humano|verifica que no eres un robot', body):
                raise ValueError('OCC solicita una verificación. Continúa la descarga y complétala en su ventana.')
            if not allowed_profile(driver.current_url):
                raise ValueError('Se cerró la sesión de OCC. Continúa e inicia sesión de nuevo.')
            if re.search(r'(?i)desbloquear|usar créditos|consumir créditos|comprar créditos', body):
                contact = None
            else:
                toggles = [el for el in driver.find_elements(By.CSS_SELECTOR, 'button,[role="button"]') if el.is_displayed() and norm(el.text) == 'datos de contacto']
                contact = extract_profile(body)
                if not contact and len(toggles) == 1:
                    toggles[0].click()
                    # Un corte de internet aquí pausa, no descarta al candidato.
                    contact = WebDriverWait(driver, 12).until(lambda d: extract_profile(d.find_element(By.TAG_NAME, 'body').text))
                if not contact:
                    raise ValueError('No pudimos leer los datos de un candidato. Tu avance está guardado; puedes continuar después.')
            with progress.lock:
                if contact:
                    full_text = driver.find_element(By.TAG_NAME, 'body').text
                    data['rows'].append({**contact, **extract_sections(full_text), 'vacancy': data['vacancy'],
                                         'url': url, 'review_state': candidate['review_state']})
                else:
                    data['skipped'] += 1
                data['done'].append(url)
                progress.save()
        with progress.lock:
            data['complete'] = True
            progress.save()
        if data['rows']:
            progress.excel()
        progress.message = f'Descarga terminada. {len(unique(data["rows"]))} candidatos listos para Excel. ' + (f'{data["skipped"]} perfiles no se recopilaron porque requieren desbloqueo.' if data['skipped'] else '')
    except ValueError as exc:
        progress.message = str(exc)
    except Exception:
        # No mostrar trazas, rutas internas ni mensajes técnicos a Vero.
        progress.message = 'La descarga se interrumpió. El avance guardado está a salvo. Revisa tu conexión y cierra la ventana de OCC de esta herramienta antes de pulsar «Continuar descarga».'
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if progress.pause.is_set():
            progress.message = 'Descarga pausada. Puedes continuar después o descargar lo recopilado.'
        progress.busy = False
        progress.awaiting = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Acceso no permitido.'})
        if self.path == '/':
            page = (ASSETS / 'pantalla.html').read_text(encoding='utf-8').replace('__TOKEN__', self.server.token)
            return self.reply(200, page.encode('utf-8'), 'text/html; charset=utf-8')
        if self.headers.get('X-OCC-Key') != self.server.token:
            return self.reply(403, {'error': 'Acceso no permitido.'})
        if self.path == '/estado':
            return self.reply(200, self.server.progress.status())
        if self.path == '/excel':
            try:
                destination = self.server.progress.excel()
                return self.reply(200, destination.read_bytes(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            except ValueError as exc:
                return self.reply(400, {'error': str(exc)})
        self.reply(404, {'error': 'Página no disponible.'})

    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-OCC-Key') != self.server.token:
            return self.reply(403, {'error': 'Acceso no permitido.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Solicitud no válida.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Solicitud no válida.')
            p = self.server.progress
            if self.path == '/iniciar':
                p.begin(data.get('vacancy', ''), data.get('mode', ''), consent=data.get('consent') is True,
                        platform=data.get('platform','occ'), action=data.get('action','new'))
            elif self.path == '/continuar':
                p.begin('', '', resume=True)
            elif self.path == '/listo':
                p.ready.set()
            elif self.path == '/pausar':
                p.pause.set()
                p.message = 'Guardando y pausando. Espera un momento.'
            else:
                return self.reply(404, {'error': 'Opción no disponible.'})
            self.reply(200, {'ok': True})
        except (ValueError, TypeError) as exc:
            self.reply(400, {'error': str(exc)})


def main():
    # Un segundo doble clic vuelve a la pantalla existente, sin iniciar otro trabajo.
    import msvcrt
    ROOT.mkdir(parents=True, exist_ok=True)
    lockfile = (ROOT / '.herramienta.lock').open('a+b')
    if lockfile.seek(0, 2) == 0:
        lockfile.write(b' ')
        lockfile.flush()
    lockfile.seek(0)
    try:
        msvcrt.locking(lockfile.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lockfile.seek(1)
        previous = lockfile.read().decode('ascii', errors='ignore').strip()
        if previous.startswith('http://127.0.0.1:') and previous.endswith('/'):
            webbrowser.open(previous)
        print('La herramienta ya esta abierta. Vuelve a su pantalla para continuar.')
        lockfile.close()
        return
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.token = secrets.token_hex(32)
    server.progress = Progress(ROOT / 'resultados')
    local_url = f'http://127.0.0.1:{server.server_port}/'
    lockfile.seek(1)
    lockfile.truncate()
    lockfile.write(local_url.encode('ascii'))
    lockfile.flush()
    webbrowser.open(local_url)
    print('La pantalla de descarga está abierta. Deja esta ventana abierta mientras trabajas.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        lockfile.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        # Verificar el ejecutable empaquetado sin abrir OCC ni acceder a candidatos.
        from selenium import webdriver
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        assert webdriver.ChromeOptions() is not None
        assert SeleniumManager()._get_binary().exists()
        assert 'Candidatos de OCC' in (ASSETS / 'pantalla.html').read_text(encoding='utf-8')
        Path(sys.argv[2]).write_text('OK: pantalla y navegador incluidos', encoding='utf-8')
    else:
        try:
            main()
        except Exception:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'No pudimos abrir la herramienta. Cierra la ventana anterior y vuelve a intentarlo. Tu avance guardado no se borra.', 'Candidatos de OCC', 0x10)

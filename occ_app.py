"""Interfaz privada local. El avance se guarda antes de abrir cada perfil."""
import copy
import json
import os
import secrets
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from diagnostics import DiagnosticLog

from occ_prueba import ROOT, URL, DISCOVER, norm, allowed_profile, extract_profile, extract_sections, select_candidates, unique, export_xlsx

ASSETS = Path(__file__).resolve().parent
VERSION = '1.2.3'

def row_count(data):
    rows = data.get('rows', [])
    return len(rows if data.get('platform') in ('computrabajo', 'indeed') else unique(rows))


class Progress:
    def __init__(self, folder, diagnostics=None):
        self.folder = Path(folder)
        self.folder.mkdir(exist_ok=True)
        self.path = self.folder / 'avance.json'
        self.lock = threading.RLock()
        self.data = None
        self.busy = False
        self.awaiting = False
        self.browser = None
        self.diagnostics = diagnostics or DiagnosticLog(self.folder / 'diagnosticos', VERSION)
        self.stage = 'idle'
        self.issue = ''
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
                    self.stage = 'saved_pending'
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
            pending = []
            for path in sorted(self.folder.glob('pendiente-*.json')):
                try:
                    old = json.loads(path.read_text(encoding='utf-8'))
                    pending.append(dict(id=path.stem, vacancy=old['vacancy'], platform=old.get('platform', 'occ')))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
            return dict(version=VERSION, stage=self.stage, issue=self.issue, diagnostic_available=self.diagnostics.available, pending=pending, message=self.message, busy=self.busy, saved=bool(self.data),
                        vacancy=data.get('vacancy', ''), mode=data.get('mode', 'all'),
                        platform=data.get('platform', 'occ'), action=data.get('action', 'new'),
                        count=row_count(data), reviewed=len(data.get('done', [])),
                        total=len(data.get('selected', [])), pages=data.get('pages', 0),
                        complete=data.get('complete', False), waiting=self.busy and self.awaiting and not self.ready.is_set())

    def park(self):
        """Conservar el trabajo pendiente sin obligar a terminarlo antes de otro."""
        with self.lock:
            if self.busy:
                raise ValueError('Primero pulsa Pausar y guardar y espera a que termine.')
            if not self.data:
                raise ValueError('No hay un avance para guardar aparte.')
            self.save()
            destination = self.folder / ('pendiente-' + secrets.token_hex(16) + '.json')
            backup = self.path.with_suffix('.bak')
            if backup.exists():
                os.replace(backup, destination.with_suffix('.bak'))
            os.replace(self.path, destination)
            self.data = None
            self.message = 'Avance anterior conservado. Elige Indeed u otra plataforma para una nueva descarga.'

    def restore(self, identifier):
        with self.lock:
            if self.busy or self.data or self.path.exists():
                raise ValueError('Guarda aparte el avance actual antes de recuperar otro.')
            if not isinstance(identifier, str) or not re.fullmatch(r'pendiente-[a-f0-9]{32}', identifier):
                raise ValueError('Pendiente no válido.')
            source = self.folder / (identifier + '.json')
            try:
                data = json.loads(source.read_text(encoding='utf-8'))
                if data.get('version') != 1 or data.get('mode') not in ('seen', 'unseen', 'all') or not all(isinstance(data.get(k), list) for k in ('candidates', 'rows', 'done')):
                    raise ValueError('Formato inválido')
            except (OSError, ValueError, TypeError, AttributeError):
                raise ValueError('No pudimos recuperar ese avance. El archivo se conserva.')
            os.replace(source, self.path)
            self.data = data
            self.message = 'Avance recuperado. Pulsa Continuar descarga cuando quieras retomarlo.'

    def previous_rows(self, platform, vacancy, offer):
        if platform == 'indeed':
            from indeed import merge_rows
        else:
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
                if platform not in ('occ','computrabajo','indeed') or action not in ('new','update'):
                    raise ValueError('Elige la plataforma y el tipo de descarga.')
                if platform in ('computrabajo', 'indeed') and mode != 'all':
                    raise ValueError('En esta plataforma elige todos los candidatos; conservamos su estado original sin suponer visto/no visto.')
                if platform == 'occ' and action != 'new':
                    raise ValueError('Actualizar Excel está disponible para Computrabajo e Indeed.')
                if action == 'update':
                    histories = [self.data] if self.data else []
                    histories += [json.loads(x.read_text(encoding='utf-8')) for x in self.folder.glob('avance-anterior-*.json')]
                    if not any(x.get('complete') and x.get('platform') == platform and x.get('rows') for x in histories):
                        raise ValueError('Primero descarga una vacante de esta plataforma en esta computadora. Después podrás actualizar su Excel.')
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
            # A manual continuation/new download owns the previous OCC window.
            # Never leave two drivers competing for the same Chrome profile.
            self.diagnostics.event('manual_resume' if resume else 'worker_start', platform=self.data.get('platform','occ'))
            self.close_browser('manual_resume' if resume else 'new_download')
            self.stage = 'opening_browser'
            self.issue = ''
            self.busy = True
            self.awaiting = False
            self.ready.clear()
            self.pause.clear()
            self.message = 'Abriendo la plataforma. Espera a que aparezca su ventana.'
            worker = collect
            if self.data.get('platform') == 'computrabajo':
                from computrabajo import collect as worker
            elif self.data.get('platform') == 'indeed':
                from indeed import collect as worker
            threading.Thread(target=self.run_worker, args=(worker,), daemon=True).start()

    def run_worker(self, worker):
        try:
            worker(self)
        except BaseException as exc:
            # This also covers an exception in another platform or in cleanup.
            self.diagnostics.event('worker_error', exc=exc, stage=self.stage, code='unhandled_worker')
            self.issue = 'unhandled_worker'
            self.message = 'El proceso se detuvo inesperadamente. Tu avance sigue guardado. Pulsa Descargar diagnóstico para revisar la causa.'
            self.busy = self.awaiting = False
        finally:
            self.diagnostics.event('worker_end', stage=self.stage, code=self.issue or 'ok')

    def close_browser(self, reason='manual_close'):
        browser, self.browser = self.browser, None
        if browser:
            self.diagnostics.event('browser_close', reason=reason, stage=self.stage)
            try:
                browser.quit()
            except Exception:
                pass

    def excel(self):
        with self.lock:
            if not self.data or not self.data['rows']:
                raise ValueError('Todavía no hay candidatos recopilados para descargar.')
            rows = copy.deepcopy(self.data['rows'])
            deduplicate = self.data.get('platform') not in ('computrabajo', 'indeed')
        destination = self.folder / ('postulados-' + str(time.time_ns()) + '.xlsx')
        export_xlsx(rows, destination, deduplicate=deduplicate)
        return destination


def read_occ_candidate(driver, progress):
    """Bounded wait for visible contact data; no reload or automatic retry."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
    last_body = ''
    clicked = False
    last_state = None

    def ready(current):
        nonlocal last_body, clicked, last_state
        if progress.pause.is_set():
            return {'paused': True}
        if not allowed_profile(current.current_url):
            raise ValueError('Se cerró la sesión de OCC o cambió la página. El candidato sigue pendiente; continúa manualmente cuando hayas revisado la ventana.')
        last_body = current.find_element(By.TAG_NAME, 'body').text
        if re.search(r'(?i)captcha|verifica que eres humano|verifica que no eres un robot', last_body):
            raise ValueError('OCC solicita una verificación humana. La descarga está pausada; revisa la ventana antes de continuar manualmente.')
        if re.search(r'(?i)desbloquear|usar créditos|consumir créditos|comprar créditos', last_body):
            return {'contact': None, 'body': last_body}
        if re.search(r'(?i)(?:perfil|currículum|curriculum|candidato) (?:ya )?(?:no (?:está |se encuentra )?disponible|eliminado)', last_body):
            raise ValueError('OCC indica que este perfil no está disponible. No se descartó el candidato ni se borró el avance; revisa la ventana antes de continuar.')
        contact = extract_profile(last_body)
        if contact:
            if hasattr(progress, 'diagnostics'):
                progress.diagnostics.event('profile_state', stage='contact_ready', has_contact=True)
            return {'contact': contact, 'body': last_body}
        # CV: 0 is also shown while OCC is loading: never treat it as proof that
        # the candidate is empty, and do not toggle its incomplete contact panel.
        placeholder = bool(re.search(r'(?im)^CV\s*:\s*0\s*$', last_body))
        if placeholder != last_state and hasattr(progress, 'diagnostics'):
            progress.diagnostics.event('profile_state', stage='contact_wait', cv_zero=placeholder, has_contact=False)
            last_state = placeholder
        if not clicked and not placeholder:
            toggles = [el for el in current.find_elements(By.CSS_SELECTOR, 'button,[role="button"]')
                       if el.is_displayed() and norm(el.text) == 'datos de contacto']
            expanded = len(toggles) == 1 and toggles[0].get_attribute('aria-expanded') == 'true'
            if len(toggles) == 1 and not expanded:
                try:
                    toggles[0].click()
                    clicked = True
                    if hasattr(progress, 'diagnostics'):
                        progress.diagnostics.event('profile_state', stage='contact_clicked', contact_open=False)
                except StaleElementReferenceException:
                    return False
        return False

    try:
        return WebDriverWait(driver, 25).until(ready)
    except TimeoutException:
        incomplete = bool(re.search(r'(?im)^CV\s*:\s*0\s*$', last_body))
        reason = ('OCC sigue mostrando el perfil incompleto (CV: 0), sin datos visibles.' if incomplete
                  else 'OCC no mostró datos de contacto que se puedan leer con seguridad.')
        if hasattr(progress, 'diagnostics'):
            progress.issue = 'profile_incomplete' if incomplete else 'contact_unreadable'
            progress.diagnostics.event('profile_paused', stage='contact_wait', code=progress.issue, cv_zero=incomplete)
        raise ValueError(reason + ' El candidato sigue pendiente y el avance está guardado. No se recargó ni se descartó automáticamente; revisa la ventana y pulsa Continuar descarga cuando quieras intentarlo de nuevo.') from None


def collect(progress):
    driver = None
    keep_browser = False
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        import re
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--user-data-dir=' + str(ROOT / 'perfil-occ'))
        # Keep Chrome alive if Selenium's Service object is finalized on a worker
        # exit. Explicit quit still closes it on completion/pause/manual resume.
        options.add_experimental_option('detach', True)
        driver = webdriver.Chrome(options=options)
        versions = getattr(driver, 'capabilities', {})
        progress.diagnostics.event('browser_started', browser_version=versions.get('browserVersion',''), driver_version=versions.get('chrome',{}).get('chromedriverVersion','').split(' ')[0])
        driver.set_page_load_timeout(45)
        progress.stage = 'opening_list'
        driver.get(URL)
        progress.message = 'En la ventana de OCC, inicia sesión y selecciona la vacante indicada. Después vuelve aquí y pulsa «Ya estoy en la vacante».'
        progress.awaiting = True
        progress.stage = 'waiting_ready'
        progress.diagnostics.event('waiting_ready', stage=progress.stage)
        while not progress.ready.wait(.3):
            if progress.pause.is_set():
                return
        data = progress.data
        progress.awaiting = False
        if urlsplit(driver.current_url).hostname != 'empresa.occ.com.mx':
            raise ValueError('Abre OCC e inicia sesión antes de continuar.')
        if not data['listed']:
            progress.stage = 'reading_list'
            progress.diagnostics.event('list_start', stage=progress.stage)
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
                progress.diagnostics.event('list_page', page=page, total=len(data['candidates']))
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
            progress.stage = 'reading_profile'
            progress.diagnostics.event('profile_start', stage=progress.stage, profile_number=len(data['done'])+1, total=len(data['selected']))
            progress.message = f'Recopilando candidato {len(data["done"])+1} de {len(data["selected"])}. No cierres la ventana de OCC.'
            driver.get(url)
            result = read_occ_candidate(driver, progress)
            if result.get('paused'):
                return
            contact = result['contact']
            with progress.lock:
                if contact:
                    full_text = result['body']
                    data['rows'].append({**contact, **extract_sections(full_text), 'vacancy': data['vacancy'],
                                         'url': url, 'review_state': candidate['review_state']})
                else:
                    data['skipped'] += 1
                data['done'].append(url)
                progress.save()
                progress.diagnostics.event('profile_saved', reviewed=len(data['done']), rows=len(data['rows']))
        with progress.lock:
            data['complete'] = True
            progress.save()
        if data['rows']:
            progress.excel()
        progress.message = f'Descarga terminada. {len(unique(data["rows"]))} candidatos listos para Excel. ' + (f'{data["skipped"]} perfiles no se recopilaron porque requieren desbloqueo.' if data['skipped'] else '')
        progress.stage = 'completed'
        progress.diagnostics.event('completed', rows=len(data['rows']), complete=True)
    except ValueError as exc:
        progress.message = str(exc)
        progress.issue = progress.issue or 'read_validation'
        progress.diagnostics.event('worker_error', exc=exc, stage=progress.stage, code=progress.issue)
        keep_browser = driver is not None
    except Exception as exc:
        # No mostrar trazas, rutas internas ni mensajes técnicos a Vero.
        progress.message = 'La descarga se interrumpió por un problema de carga o conexión. El avance guardado está a salvo y el candidato sigue pendiente. Revisa la ventana y tu conexión antes de pulsar «Continuar descarga»; no se reintentará automáticamente.'
        progress.issue = type(exc).__name__
        progress.diagnostics.event('worker_error', exc=exc, stage=progress.stage, code='browser_or_network')
        keep_browser = driver is not None
    finally:
        if driver and keep_browser and not progress.pause.is_set():
            progress.browser = driver
            progress.diagnostics.event('browser_retained', stage=progress.stage, code=progress.issue)
            progress.message += ' La ventana de OCC queda abierta para revisión; Continuar descarga la cerrará antes de abrir una sesión nueva.'
        elif driver:
            progress.diagnostics.event('browser_close', reason='user_pause' if progress.pause.is_set() else 'completed', stage=progress.stage)
            try:
                driver.quit()
            except Exception:
                pass
        if progress.pause.is_set():
            progress.diagnostics.event('pause_requested', stage=progress.stage)
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
        if self.path == '/diagnostico':
            self.server.progress.diagnostics.event('diagnostic_download', stage=self.server.progress.stage)
            return self.reply(200, self.server.progress.diagnostics.export(), 'text/plain; charset=utf-8')
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
            elif self.path == '/guardar-aparte':
                p.park()
            elif self.path == '/recuperar':
                p.restore(data.get('id'))
            elif self.path == '/listo':
                p.ready.set()
            elif self.path == '/pausar':
                p.pause.set()
                p.message = 'Guardando y pausando. Espera un momento.'
                p.diagnostics.event('pause_requested', stage=p.stage)
            elif self.path == '/cerrar':
                if p.busy:
                    raise ValueError('Primero pulsa Pausar y guardar y espera a que termine.')
                self.reply(200, {'ok':True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self.reply(404, {'error': 'Opción no disponible.'})
            self.reply(200, {'ok': True})
        except (ValueError, TypeError) as exc:
            self.reply(400, {'error': str(exc)})


def running_version(url):
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/', url):
        return 'unknown'
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=2) as response:
            html = response.read(128_000).decode('utf-8', errors='replace')
        match = re.search(r'VERSIÓN\s+([0-9]+(?:\.[0-9]+){1,3})', html)
        return match.group(1) if match else 'unknown'
    except Exception:
        return 'unknown'


class LocalServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        import sys
        self.progress.diagnostics.event('worker_error', exc=sys.exc_info()[1], stage='local_server', code='request_failed')


def main():
    # Un segundo doble clic vuelve a la pantalla existente, sin iniciar otro trabajo.
    import msvcrt
    ROOT.mkdir(parents=True, exist_ok=True)
    diagnostics = DiagnosticLog(ROOT / 'resultados' / 'diagnosticos', VERSION)
    diagnostics.event('app_start', pid=os.getpid())
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
        if re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/', previous):
            # No redirigir silenciosamente una actualización hacia el programa viejo.
            import ctypes
            active = running_version(previous)
            diagnostics.event('existing_instance', active_version=active, stage='startup')
            if active != VERSION:
                ctypes.windll.user32.MessageBoxW(None, f'La versión {VERSION} todavía NO está activa. Sigue abierta otra instancia (versión {active}).\n\nCierra la aplicación anterior, no solo su pestaña, y abre de nuevo el acceso del escritorio. El avance se conserva. No se abrirá la pantalla vieja como si fuera la actualización.', 'Actualización pendiente de activar', 0x30)
            else:
                webbrowser.open(previous)
        print('La herramienta ya esta abierta. Vuelve a su pantalla para continuar.')
        lockfile.close()
        return
    server = LocalServer(('127.0.0.1', 0), Handler)
    server.token = secrets.token_hex(32)
    server.progress = Progress(ROOT / 'resultados', diagnostics=diagnostics)
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
        diagnostics.event('app_stop', stage=server.progress.stage)
        server.progress.close_browser('app_shutdown')
        server.server_close()
        lockfile.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        # Verificar el ejecutable empaquetado sin abrir OCC ni acceder a candidatos.
        from selenium import webdriver
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        import indeed
        import pypdf
        assert webdriver.ChromeOptions() is not None
        assert SeleniumManager()._get_binary().exists()
        assert 'Candidatos de OCC' in (ASSETS / 'pantalla.html').read_text(encoding='utf-8')
        assert '<option value="indeed">Indeed</option>' in (ASSETS / 'pantalla.html').read_text(encoding='utf-8')
        assert indeed.URL.startswith('https://employers.indeed.com/')
        Path(sys.argv[2]).write_text('OK: pantalla y navegador incluidos', encoding='utf-8')
    else:
        try:
            main()
        except Exception as exc:
            DiagnosticLog(ROOT / 'resultados' / 'diagnosticos', VERSION).event('startup_error', exc=exc, stage='startup')
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'No pudimos abrir la herramienta. Cierra la ventana anterior y vuelve a intentarlo. Tu avance guardado no se borra.', 'Candidatos de OCC', 0x10)

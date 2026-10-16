"""Postulaciones visibles de Indeed. Sin API privada, mensajes ni cambios de estado."""
import re
from uuid import uuid4, UUID
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode, urlunsplit

from occ_prueba import norm, phone

URL = 'https://employers.indeed.com/jobs'
MAX_PDF_BYTES = 30_000_000


def portal_query(url, path):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'employers.indeed.com'
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.path.rstrip('/') != path):
        return {}
    return parse_qs(parsed.query)


def one_id(query, key):
    values = query.get(key, [])
    return values[0].lower() if len(values) == 1 and re.fullmatch(r'[a-fA-F0-9]{12}', values[0]) else ''


def offer_id(url):
    return one_id(portal_query(url, '/candidates'), 'id')


def profile_id(url):
    query = portal_query(url, '/candidates/view')
    candidate, offer = one_id(query, 'id'), one_id(query, 'legacyJobId')
    return offer + ':' + candidate if offer and candidate else ''


def record_key(row):
    key = profile_id(row.get('url', ''))
    if key:
        return key
    # Withdrawn rows have no applicant ID/link in the visible UI. An observation
    # UUID identifies the exported row, never purports to identify the person.
    offer = offer_id(row.get('url', ''))
    if row.get('withdrawn') is True and offer:
        try:
            observation = str(UUID(row.get('observation_id', '')))
        except (ValueError, TypeError, AttributeError):
            return ''
        return offer+':withdrawn:'+observation
    return ''


def first_page(url):
    if not offer_id(url) or portal_query(url, '/candidates').get('statusName') != ['All']:
        raise ValueError('En Indeed, abre una vacante y elige «Todas las postulaciones» antes de continuar.')
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    # The captured UI uses offset pagination. Preserve vacancy/status, reset the page.
    query.pop('offset', None)
    query.pop('page', None)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ''))


DISCOVER = r"""
const visible = n => n && n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden';
const items = [...document.querySelectorAll('a[data-testid="NameCell"]')].filter(visible).map(a => {
  const row = a.closest('[role="row"],tr');
  const state = row && row.querySelector('[data-testid="CandidateInfoColumn-status"]');
  return {url:a.href, name:a.innerText.trim(), review_state:visible(state) ? state.innerText.trim() : 'No identificado'};
});
const withdrawn = [...document.querySelectorAll('[data-testid="NameCell__withdrawn"]')].filter(visible)
  .map(n => ({name:n.innerText.trim(), review_state:'Postulación retirada'}));
const matches = [...document.body.innerText.matchAll(/Mostrando\s+(\d+)\s+(?:a|[-–])\s*(\d+)\s+de\s+(\d+)/gi)];
return {items, withdrawn, pagination:matches.length === 1 ? matches[0].slice(1).map(Number) : null};
"""


def merge_rows(previous, incoming):
    result = [dict(row) for row in previous]
    index = {record_key(row): i for i, row in enumerate(result)}
    if '' in index:
        raise ValueError('Un registro no tiene una postulación válida de Indeed.')
    for row in incoming:
        key = record_key(row)
        if not key:
            raise ValueError('Un registro no tiene una postulación válida de Indeed.')
        if key in index:
            result[index[key]] = {**result[index[key]], **{k: v for k, v in row.items() if v not in ('', None)}}
        else:
            index[key] = len(result)
            result.append(dict(row))
    return result


def phone_from_call_panel(text, expected_name):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    anchors = [i for i, line in enumerate(lines) if norm(line) == norm('Llamar a ' + expected_name)]
    if len(anchors) != 1:
        return ''
    values = [phone(line) for line in lines[anchors[0]+1:anchors[0]+5]
              if re.fullmatch(r'[+\d ()-]{10,25}', line)]
    values = list(dict.fromkeys(value for value in values if value))
    return values[0] if len(values) == 1 else ''


def read_cv(path):
    """Extract local text only. Scanned PDFs remain available, never fabricated/OCRed online."""
    from pypdf import PdfReader
    path = Path(path)
    if path.stat().st_size > MAX_PDF_BYTES:
        return {'cv_status': 'CV guardado; supera el límite de lectura automática.'}
    try:
        with path.open('rb') as handle:
            if handle.read(5) != b'%PDF-':
                return {'cv_status': 'Archivo guardado; no es un PDF legible.'}
        reader = PdfReader(path)
        if reader.is_encrypted:
            return {'cv_status': 'CV guardado; PDF protegido, requiere revisión.'}
        if len(reader.pages) > 50:
            return {'cv_status': 'CV guardado; más de 50 páginas, requiere revisión.'}
        text = '\n'.join(page.extract_text() or '' for page in reader.pages).strip()
    except Exception:
        return {'cv_status': 'CV guardado; no se pudo extraer el texto, requiere revisión.'}
    if not text:
        return {'cv_status': 'CV guardado; PDF sin texto extraíble (posible imagen). Requiere revisión.'}
    fields = {'cv_text': text[:30000], 'cv_status': 'Texto extraído del PDF.'}
    if len(text) > 30000:
        fields['cv_status'] = 'Texto resumido a 30,000 caracteres; consulta el CV completo guardado.'
    headings = {
        'experiencia laboral': 'experience', 'experiencia profesional': 'experience', 'work experience': 'experience',
        'educación': 'education', 'educacion': 'education', 'formación académica': 'education', 'education': 'education',
        'idiomas': 'languages', 'languages': 'languages', 'habilidades': 'skills', 'skills': 'skills',
        'certificaciones': 'certifications', 'certifications': 'certifications', 'cursos': 'courses',
        'información personal': None, 'datos personales': None, 'contacto': None, 'references': None,
    }
    current = None
    for line in text.splitlines():
        key = norm(line).rstrip(':')
        if key in headings:
            current = headings[key]
        elif current:
            fields[current] = (fields.get(current, '') + '\n' + line.strip()).strip()[:30000]
    return fields


def visible_buttons(driver, label):
    from selenium.webdriver.common.by import By
    return [button for button in driver.find_elements(By.CSS_SELECTOR, 'button')
            if button.is_displayed() and norm(button.text or button.get_attribute('aria-label') or '') == norm(label)]


def read_contact_phone(driver, expected_name):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    buttons = visible_buttons(driver, 'Llamar')
    if not buttons:
        return ''
    if len(buttons) != 1:
        raise ValueError('No pudimos identificar el teléfono del perfil. Tu avance está guardado.')
    buttons[0].click()  # Opens the number popover; never follows tel: or starts a call.
    try:
        def panel(d):
            text = d.find_element(By.TAG_NAME, 'body').text
            return text if any(norm(line) == norm('Llamar a '+expected_name) for line in text.splitlines()) else False
        return phone_from_call_panel(WebDriverWait(driver, 10).until(panel), expected_name)
    finally:
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)


def download_cv(driver, folder, pause):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    saved = list(folder.glob('CV.*'))
    if len(saved) == 1 and saved[0].suffix.lower() not in {'.crdownload', '.tmp'}:
        return saved[0]
    def visible_downloads(d):
        return [link for link in d.find_elements(By.CSS_SELECTOR, 'a[data-testid="download-resume-inline"]')
                if link.is_displayed()]
    from selenium.common.exceptions import TimeoutException
    try:
        links = WebDriverWait(driver, 20).until(visible_downloads)
    except TimeoutException:
        return None
    if len(links) != 1:
        raise ValueError('No pudimos identificar el CV del candidato. Tu avance está guardado.')
    # Browser downloads the same user-visible link, including blob: PDFs. No private API/cookies.
    driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(folder.resolve())})
    before = {path.name for path in folder.iterdir()}
    links[0].click()
    def completed(_):
        if pause.is_set():
            raise ValueError('Descarga pausada. Tu avance está guardado.')
        files = [path for path in folder.iterdir() if path.is_file() and path.name not in before
                 and path.suffix.lower() not in {'.crdownload', '.tmp'}]
        if any(path.name not in before for path in folder.glob('*.crdownload')):
            return False
        if len(files) > 1:
            raise ValueError('Se descargó más de un archivo; revisa la carpeta del candidato antes de continuar.')
        return files[0] if files and files[0].stat().st_size else False
    downloaded = WebDriverWait(driver, 60).until(completed)
    extension = downloaded.suffix.lower()
    if extension not in {'.pdf', '.doc', '.docx', '.rtf', '.txt'}:
        extension = '.bin'
    cached = folder / ('CV' + extension)
    # Preserve the portal's file; copy instead of overwriting any prior download.
    cached.write_bytes(downloaded.read_bytes())
    return cached


def collect(progress):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from occ_prueba import ROOT
    driver = None
    data = progress.data
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--user-data-dir=' + str(ROOT / 'perfil-indeed'))
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.get(URL)
        progress.awaiting = True
        progress.message = ('En Indeed, inicia sesión, abre la vacante y selecciona «Todas las postulaciones». '
                            'Después pulsa «Ya estoy en la vacante». No envía mensajes ni cambia estados de selección.')
        while not progress.ready.wait(.3):
            if progress.pause.is_set():
                return
        progress.awaiting = False
        listing = first_page(driver.current_url)
        offer = offer_id(listing)
        if data.get('offer_id') and data['offer_id'] != offer:
            raise ValueError('Esta no es la vacante de tu avance guardado. Abre la misma vacante de Indeed.')
        data['offer_id'] = offer
        progress.save()
        if data.get('action') == 'update' and not data.get('base_loaded'):
            previous = progress.previous_rows('indeed', data['vacancy'], offer)
            if not previous:
                raise ValueError('No encontramos una descarga anterior de esta misma vacante de Indeed.')
            # Withdrawn names cannot be safely matched across snapshots. The old
            # observations remain in archived progress/Excel, not merged by name.
            data['rows'] = merge_rows([row for row in previous if not row.get('withdrawn')], data['rows'])
            data['base_loaded'] = True
            progress.save()
        if not data['listed']:
            driver.get(listing)
            signatures = set()
            page = 0
            expected = None
            previous_end = 0
            withdrawn = []
            while not progress.pause.is_set():
                def page_ready(d):
                    value = d.execute_script(DISCOVER)
                    pagination = value.get('pagination')
                    if not pagination:
                        return False
                    size = len(value['items'])+len(value.get('withdrawn', []))
                    return value if size == pagination[1]-pagination[0]+1 else False
                info = WebDriverWait(driver, 30).until(page_ready)
                items = info['items']
                if not info.get('pagination'):
                    raise ValueError('No pudimos verificar el total de candidatos en Indeed. Tu avance está guardado.')
                start, end, total = info['pagination']
                if (expected is not None and total != expected) or start != previous_end+1:
                    raise ValueError('La lista cambió o no inicia en la primera página. Continúa para volver a comprobarla.')
                expected = total
                if any(not item.get('name') or not profile_id(item['url']).startswith(offer+':') for item in items):
                    raise ValueError('Hay un perfil de otra vacante o no identificable. Tu avance está guardado.')
                signature = (start, end, tuple(profile_id(item['url']) for item in items),
                             tuple(item['name'] for item in info.get('withdrawn', [])))
                if signature in signatures:
                    raise ValueError('Indeed repitió una página. Pausamos para no omitir postulaciones.')
                signatures.add(signature)
                withdrawn.extend(info.get('withdrawn', []))
                known = {profile_id(item['url']) for item in data['candidates']}
                data['candidates'].extend(item for item in items if profile_id(item['url']) not in known)
                page += 1
                previous_end = end
                data['pages'] = max(page, data['pages'])
                data['expected_total'] = expected
                progress.save()
                progress.message = f'Indeed: página {page}, {len(data["candidates"])} de {expected} postulaciones identificadas.'
                buttons = visible_buttons(driver, 'Siguiente')
                if len(buttons) != 1:
                    raise ValueError('No pudimos identificar la paginación de Indeed. Tu avance está guardado.')
                if not buttons[0].is_enabled() or buttons[0].get_attribute('aria-disabled') == 'true':
                    if end != total or len({profile_id(item['url']) for item in data['candidates']})+len(withdrawn) != total:
                        raise ValueError('El total recopilado no coincide con Indeed. No marcamos la descarga como completa.')
                    observations = [{**item, 'url': listing, 'withdrawn': True,
                        'observation_id': str(uuid4())} for item in withdrawn]
                    data['selected'] = list(data['candidates']) + observations
                    data['withdrawn_count'] = len(observations)
                    data['listed'] = True
                    progress.save()
                    break
                buttons[0].click()
                WebDriverWait(driver, 30).until(lambda d: (value if (value := page_ready(d))
                                                         and value['pagination'][0] != start else False))
        for candidate in data['selected']:
            if progress.pause.is_set():
                return
            url = candidate['url']
            done_key = record_key(candidate) if candidate.get('withdrawn') else url
            if done_key in data['done']:
                continue
            if candidate.get('withdrawn'):
                row = {**candidate, 'platform': 'Indeed', 'vacancy': data['vacancy'], 'phone': '',
                       'cv_status': 'Postulación retirada. Indeed no permite abrir el perfil ni descargar su CV. Identidad no verificable.'}
                with progress.lock:
                    data['rows'] = merge_rows(data['rows'], [row])
                    data['done'].append(done_key)
                    progress.save()
                continue
            key = profile_id(url)
            if not key.startswith(offer+':'):
                raise ValueError('Una postulación no pertenece a la vacante guardada.')
            progress.message = f'Indeed: recopilando {len(data["done"])+1} de {len(data["selected"])}. El avance se guarda por candidato.'
            driver.get(url)
            def confirmed(d):
                if profile_id(d.current_url) != key:
                    return False
                headings = d.find_elements(By.CSS_SELECTOR, '[data-testid="name-plate-name-item"] h2, [data-testid="name-plate-name-item"]')
                return next((heading.text for heading in headings if heading.is_displayed() and norm(heading.text) == norm(candidate['name'])), False)
            name = WebDriverWait(driver, 30).until(confirmed)
            number = read_contact_phone(driver, name)
            folder = progress.folder / 'cvs-indeed' / offer / key.split(':')[1]
            cv = download_cv(driver, folder, progress.pause)
            row = {**candidate, 'platform': 'Indeed', 'vacancy': data['vacancy'], 'phone': number,
                   'cv_file': str(cv.relative_to(progress.folder)) if cv else '',
                   **(read_cv(cv) if cv else {'cv_status': 'Requiere revisión: Indeed no mostró un CV descargable durante esta consulta.'})}
            with progress.lock:
                data['rows'] = merge_rows(data['rows'], [row])
                data['done'].append(url)
                progress.save()
        if progress.pause.is_set():
            return
        data['complete'] = True
        progress.save()
        if data['rows']:
            progress.excel()
        progress.message = (f'Listo. {len(data["rows"])} candidatos de Indeed en tu Excel. '
                            f'{data.get("withdrawn_count", 0)} postulaciones retiradas se incluyen sin perfil. '
                            'Los CV están en resultados/cvs-indeed. Los PDF sin texto quedan señalados para revisión.')
    except ValueError as exc:
        progress.message = str(exc)
    except Exception:
        progress.message = ('Indeed interrumpió la lectura o requiere revisar la sesión/verificación. '
                            'Tu avance está guardado. No se repiten automáticamente los intentos. '
                            'Pulsa «Continuar descarga» cuando puedas abrir la misma vacante.')
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if progress.pause.is_set():
            progress.message = 'Descarga pausada. Tu avance y los CV guardados están a salvo.'
        progress.busy = progress.awaiting = False

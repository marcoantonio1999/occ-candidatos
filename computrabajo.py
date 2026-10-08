"""Lectura de los perfiles visibles de la cuenta autorizada, sin enviar mensajes."""
import re
from urllib.parse import urlsplit, parse_qs
from occ_prueba import norm, phone

URL = 'https://empresa.mx.computrabajo.com/Company'

def profile_id(url):
    p = urlsplit(url)
    q = parse_qs(p.query)
    if (p.scheme != 'https' or p.hostname != 'empresa.mx.computrabajo.com'
            or p.path != '/Company/MatchCvDetail/MatchDetail' or p.username or p.password):
        return ''
    values = [q.get(k, [''])[0] for k in ('oi', 'ims')]
    return ':'.join(v.upper() for v in values) if all(re.fullmatch('[A-Fa-f0-9]{32}', v) for v in values) else ''

def offer_id(url):
    p = urlsplit(url)
    value = parse_qs(p.query).get('oi', [''])[0]
    if p.scheme == 'https' and p.hostname == 'empresa.mx.computrabajo.com' and p.path == '/Company/Offers/Match' and re.fullmatch('[A-Fa-f0-9]{32}', value):
        return value.upper()
    return ''

DISCOVER = r"""
return [...document.querySelectorAll('#MatchesList a.js-o-link.nom')]
 .filter(a=>a.getClientRects().length && getComputedStyle(a).visibility!=='hidden')
 .map(a=>({url:a.href,name:a.innerText.trim(),review_state:'No identificado'}));
"""

def extract(text, expected_name):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = next((x for x in lines if norm(x).startswith('currículum de ')), '')
    name = title[len('Currículum de '):].strip()
    if not name or norm(name) != norm(expected_name):
        raise ValueError('No pudimos confirmar el candidato abierto. Tu avance está guardado.')
    headings = {'experiencia profesional':'experience','formación':'education',
                'conocimientos y habilidades':'skills','otros':'skills','idiomas':'languages',
                'certificaciones':'certifications','cursos':'courses'}
    result = dict(name=name, phone='', platform='Computrabajo')
    current = None
    contact_lines = []
    for line in lines[lines.index(title)+1:]:
        n = norm(line)
        if n.startswith(('gestiona el cv', 'avisos legales', 'aviso de privacidad', '©', 'copyright', 'computrabajo ©')):
            current = None
        if n in headings:
            current = headings[n]
            result.setdefault(current, '')
            continue
        if current:
            result[current] += ('\n' if result[current] else '') + line
        elif not any(k in result for k in ('experience','education','languages')):
            contact_lines.append(line)
    # No extraer números de fechas, sueldos o empleos del resto del CV.
    numbers = [phone(x) for x in contact_lines if re.fullmatch(r'[+\d ()-]{10,25}', x)]
    numbers = list(dict.fromkeys(x for x in numbers if x))
    result['phone'] = numbers[0] if len(numbers) == 1 else ''
    return result

def merge_rows(previous, incoming):
    """Identidad del portal, no el nombre: dos homónimos no se fusionan."""
    result = [dict(row) for row in previous]
    index = {profile_id(row.get('url','')):i for i,row in enumerate(result) if profile_id(row.get('url',''))}
    for row in incoming:
        key = profile_id(row.get('url',''))
        if not key:
            raise ValueError('Un registro no tiene un enlace válido de Computrabajo.')
        if key in index:
            old = result[index[key]]
            result[index[key]] = {**old, **{k:v for k,v in row.items() if v not in ('',None)}}
        else:
            index[key] = len(result)
            result.append(dict(row))
    return result

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
        options.add_argument('--user-data-dir=' + str(ROOT / 'perfil-computrabajo'))
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.get(URL)
        progress.awaiting = True
        progress.message = 'En Computrabajo, inicia sesión y abre los candidatos de tu vacante. Después pulsa «Ya estoy en la vacante» aquí.'
        while not progress.ready.wait(.3):
            if progress.pause.is_set(): return
        progress.awaiting = False
        offer = offer_id(driver.current_url)
        if not offer:
            raise ValueError('Abre la lista de candidatos de una vacante en Computrabajo antes de continuar.')
        if data.get('offer_id') and data['offer_id'] != offer:
            raise ValueError('Esta no es la vacante de tu avance guardado. Abre la misma vacante y continúa.')
        data['offer_id'] = offer
        progress.save()
        if data.get('action') == 'update' and not data.get('base_loaded'):
            previous = progress.previous_rows('computrabajo', data['vacancy'], offer)
            if not previous:
                raise ValueError('No encontramos una descarga anterior de esta vacante en esta computadora. Selecciona la vacante anterior o solicita ayuda.')
            data['rows'] = merge_rows(previous, data['rows'])
            data['base_loaded'] = True
            progress.save()
        if not data['listed']:
            # Volver al inicio de la lista incluso si se seleccionó su página 2.
            listing_url = driver.current_url
            driver.get(listing_url)
            WebDriverWait(driver,25).until(lambda d:d.execute_script(DISCOVER))
            sections = driver.execute_script(r"""
return [...document.querySelectorAll('#MatchesList a[href]')]
 .filter(a=> /^(Recibidos|Seleccionados|Finalistas|Descartados)\s*\(/i.test(a.innerText.trim()))
 .map(a=>a.href);
""")
            sections = list(dict.fromkeys(x for x in sections if offer_id(x)==offer))
            if not sections:
                raise ValueError('Abre la lista de postulados de tu vacante, no los candidatos sugeridos. Tu avance está guardado.')
            if sections[0] != listing_url:
                driver.get(sections[0])
            signatures = set()
            page = 0
            section_index = 0
            while not progress.pause.is_set():
                items = WebDriverWait(driver,25).until(lambda d:d.execute_script(DISCOVER))
                items = [x for x in items if profile_id(x['url']).startswith(offer+':')]
                if not items: raise ValueError('No pudimos leer esta lista. Tu avance está guardado.')
                signature = tuple(profile_id(x['url']) for x in items)
                if signature in signatures: raise ValueError('La página se repitió. Pausamos para no omitir candidatos.')
                signatures.add(signature)
                known = {profile_id(x['url']) for x in data['candidates']}
                data['candidates'].extend(x for x in items if profile_id(x['url']) not in known)
                page += 1
                data['pages'] = max(page,data['pages'])
                progress.save()
                progress.message = f'Revisando página {page} de Computrabajo. Tu avance se guarda automáticamente.'
                buttons = [x for x in driver.find_elements(By.CSS_SELECTOR,'a.b_next') if x.is_displayed()]
                if len(buttons)>1: raise ValueError('No pudimos identificar la siguiente página. Tu avance está guardado.')
                if not buttons or not buttons[0].is_enabled() or buttons[0].get_attribute('aria-disabled')=='true' or 'disabled' in (buttons[0].get_attribute('class') or '').split():
                    section_index += 1
                    if section_index < len(sections):
                        driver.get(sections[section_index])
                        continue
                    data['selected'] = list(data['candidates'])
                    data['listed'] = True
                    progress.save()
                    break
                buttons[0].click()
                WebDriverWait(driver,25).until(lambda d:tuple(profile_id(x['url']) for x in d.execute_script(DISCOVER)) not in ((),signature))
        for candidate in data['selected']:
            if progress.pause.is_set(): return
            url = candidate['url']
            if url in data['done']: continue
            if not profile_id(url).startswith(offer+':'): raise ValueError('Un candidato pertenece a otra vacante. Pausamos la descarga.')
            progress.message = f'Recopilando candidato {len(data["done"])+1} de {len(data["selected"])}. No cierres Computrabajo.'
            driver.get(url)
            body = WebDriverWait(driver,25).until(lambda d:d.find_element(By.TAG_NAME,'body').text or False)
            if profile_id(driver.current_url) != profile_id(url) or re.search(r'(?i)captcha|verifica que eres humano|verifica que no eres un robot',body):
                raise ValueError('Revisa la sesión o verificación de Computrabajo. Tu avance está guardado.')
            if re.search(r'(?i)desbloquear|comprar créditos|consumir créditos',body):
                data['skipped'] += 1
            else:
                row = {**extract(body,candidate['name']), 'vacancy':data['vacancy'], 'url':url,'review_state':candidate['review_state']}
                with progress.lock:
                    data['rows'] = merge_rows(data['rows'],[row])
            data['done'].append(url)
            progress.save()
        if progress.pause.is_set(): return
        data['complete'] = True
        progress.save()
        if data['rows']: progress.excel()
        progress.message = f'Listo. {len(data["rows"])} candidatos en tu Excel.' + (f' {data["skipped"]} perfiles requieren desbloqueo y se omitieron.' if data['skipped'] else '')
    except ValueError as exc:
        progress.message = str(exc)
    except Exception:
        progress.message = 'La descarga se interrumpió. Tu avance está guardado. Revisa la conexión y pulsa «Continuar descarga».'
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
        if progress.pause.is_set(): progress.message = 'Descarga pausada. Puedes continuar después.'
        progress.busy = progress.awaiting = False

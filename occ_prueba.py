"""Prueba conservadora: exportar hasta tres postulados explícitamente vistos."""
import json
import re
import unicodedata
import zipfile
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

ROOT = (Path(os.environ['LOCALAPPDATA']) / 'OCC-Candidatos'
        if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent)
URL = 'https://empresa.occ.com.mx/empresas/candidatos/administrador?oi=40023555'

def norm(value):
    return ' '.join(unicodedata.normalize('NFC', value).casefold().split())

def allowed_profile(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'empresa.occ.com.mx' and bool(re.fullmatch(r'/empresas/candidatos/\d+/cv/\d+/\d+/?', parsed.path))

def seen_status(labels, complete_card=False):
    values = {norm(label) for label in labels}
    if values & {'sin ver', 'no visto', 'no revisado'}: return False
    # Regla de esta lista confirmada por el usuario: la tarjeta vista no lleva badge.
    return bool(values & {'visto', 'vista', 'vistos', 'vistas', 'revisado', 'revisada', 'ya visto'}) or complete_card

def phone(value):
    digits = re.sub(r'\D', '', value)
    if len(digits) == 13 and digits.startswith('521'): digits = digits[3:]
    elif len(digits) == 12 and digits.startswith('52'): digits = digits[2:]
    return digits if re.fullmatch(r'[2-9]\d{9}', digits) else ''

def extract_profile(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    indices = [i for i, line in enumerate(lines) if norm(line) == 'datos de contacto']
    if len(indices) != 1: return None
    index = indices[0]
    contact = []
    for line in lines[index + 1:index + 13]:
        if re.match(r'(?i)descarga(?:r)? cv|cv\s*:|experiencia laboral|educación', line): break
        contact.append(line)
    numbers = []
    for line in contact:
        number = phone(line)
        if number and number not in numbers: numbers.append(number)
    if len(numbers) != 1: return None
    before = lines[max(0, index - 12):index]
    location = next((i for i, line in enumerate(before) if re.search(r'(?i)ciudad de|estado de méxico|,\s*(méxico|jalisco|puebla|nuevo león)|\$.*MXN', line)), -1)
    name = before[location - 1] if location > 0 else ''
    if not re.fullmatch(r"[^\W\d_][^\d@\n]{2,100}", name, re.UNICODE) or re.search(r'(?i)vacante|experiencia|regresar|información', name): name = ''
    # Un nombre ambiguo no debe asociarse a otro candidato.
    return {'name': name, 'phone': numbers[0]}

def unique(rows):
    phones, names, output = set(), set(), []
    for row in rows:
        name = norm(row['name'])
        if row['phone'] in phones or (name and name in names): continue
        phones.add(row['phone'])
        if name: names.add(name)
        output.append(row)
    return output

def extract_sections(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = {
        'experiencia laboral': 'experience', 'educación': 'education', 'educacion': 'education',
        'idiomas': 'languages', 'sobre el candidato': 'about',
        'área de especialidad': 'specialty', 'area de especialidad': 'specialty',
        'información de tu vacante': None, 'habilidades': 'skills', 'conocimientos': 'skills',
        'certificaciones': 'certifications', 'cursos': 'courses',
    }
    sections, current = {}, None
    for line in lines:
        normalized = norm(line)
        if normalized in headings:
            current = headings[normalized]
            if current: sections.setdefault(current, [])
            continue
        if current:
            if normalized in {'me interesa', 'descartar', 'regresar', 'abrir en pestaña'}: continue
            # Ignorar navegación/acciones y no mezclar el pie del sitio con idiomas.
            if re.match(r'(?i)^(aviso de privacidad|términos y condiciones|todos los derechos|©|ayuda y contacto)', line): current = None; continue
            sections[current].append(line)
    result = {key: '\n'.join(value) for key, value in sections.items()}
    about = sections.get('about', [])
    desired = next((about[i + 1] for i, value in enumerate(about[:-1]) if norm(value) == 'puesto deseado'), '')
    result['desired_position'] = desired
    return result

HEADERS = ['Nombre', 'Telefono', 'Vacante', 'Plataforma', 'Estado de revisión', 'Experiencia laboral', 'Educación', 'Idiomas', 'Puesto deseado', 'Área de especialidad', 'Habilidades', 'Certificaciones', 'Cursos', 'Origen']
ROW_KEYS = ['name', 'phone', 'vacancy', 'platform', 'review_state', 'experience', 'education', 'languages', 'desired_position', 'specialty', 'skills', 'certifications', 'courses', 'url']

def review_state(item):
    if not item.get('complete_card'): return None
    labels = {norm(label) for label in item.get('labels', [])}
    return 'Sin ver' if labels & {'sin ver', 'no visto', 'no revisado'} else 'Visto'

def select_candidates(items, mode, limit=0):
    chosen, seen_urls = [], set()
    for item in items:
        state = review_state(item)
        if not state or not allowed_profile(item['url']): continue
        if mode == 'seen' and state != 'Visto': continue
        if mode == 'unseen' and state != 'Sin ver': continue
        if item['url'] in seen_urls: continue
        seen_urls.add(item['url']); chosen.append({**item, 'review_state': state})
    return chosen[:limit] if limit else chosen

def export_xlsx(rows, destination, deduplicate=True):
    """OOXML básico, solo texto: los nombres no se interpretan como fórmulas."""
    values = [HEADERS] + [[r.get(key, 'OCC' if key == 'platform' else '') for key in ROW_KEYS] for r in (unique(rows) if deduplicate else rows)]
    body = []
    for i, row in enumerate(values, 1):
        def xml_text(value):
            value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', str(value))
            if len(value) > 32767: raise ValueError('Una sección supera el límite de texto de Excel; no se recortó silenciosamente.')
            return escape(value)
        cells = ''.join(f'<c r="{chr(65+j)}{i}" t="inlineStr" s="1"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>' for j, value in enumerate(row))
        body.append(f'<row r="{i}">{cells}</row>')
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="35" customWidth="1"/><col min="2" max="2" width="16" customWidth="1"/><col min="3" max="3" width="35" customWidth="1"/><col min="4" max="4" width="15" customWidth="1"/><col min="5" max="13" width="45" customWidth="1"/><col min="14" max="14" width="60" customWidth="1"/></cols><sheetData>' + ''.join(body) + f'</sheetData><autoFilter ref="A1:N{len(values)}"/></worksheet>'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Postulados" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
        archive.writestr('xl/styles.xml', '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>')

# Solo DOM visible. No llamadas a endpoints privados ni lectura de cookies.
DISCOVER = r"""
const visible = n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden';
const found = [], rejected = [];
const profileButtons = [...document.querySelectorAll('button[onclick]')].filter(n=>visible(n) && /^Abrir en pestaña$/i.test(n.innerText.trim()));
for (const a of profileButtons) {
  const match = (a.getAttribute('onclick') || '').match(/window\.open\(['"]([^'"]+)['"]/);
  if (!match) continue;
  const url = new URL(match[1], location.origin).href;
  let card = a.parentElement;
  for (let depth = 0; card && depth < 9 && card !== document.body; depth++, card = card.parentElement) {
    const links = [...card.querySelectorAll('button[onclick]')].filter(n=>visible(n) && /^Abrir en pestaña$/i.test(n.innerText.trim()));
    if (links.length !== 1) break;
    const labels = [...card.querySelectorAll('span,small,div,p')].filter(visible).map(n => n.innerText.trim()).filter(t => /^(sin ver|no visto|no revisado|visto|vista|vistos|vistas|revisado|revisada|ya visto)$/i.test(t));
    const text = card.innerText;
    // No usar el contenedor del enlace: buscar la tarjeta completa con sus tres acciones.
    const complete = /abrir en pestaña/i.test(text) && /me interesa/i.test(text) && /descartar/i.test(text) && !!card.querySelector('input[type="checkbox"],[role="checkbox"]');
    if (complete) {
      if (/\bsin\s+ver\b|\bno\s+visto\b|\bno\s+revisado\b/i.test(text)) labels.push('Sin ver');
      found.push({url, labels, complete_card:true}); break;
    }
  }
}
return found;
"""

def main():
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    print('¿Qué candidatos deseas exportar?\n1. Solo vistos\n2. Solo no vistos\n3. Todos\n0. Cancelar')
    choice = input('Elige una opción: ').strip()
    modes = {'1': 'seen', '2': 'unseen', '3': 'all'}
    if choice not in modes:
        print('Cancelado. No se abrió OCC ni se descargaron datos.'); return
    mode = modes[choice]
    if mode != 'seen':
        print('AVISO: abrir los perfiles Sin ver para leer sus datos puede marcarlos como vistos en OCC. El Excel conservará el estado original.')
        if input('Escribe CONTINUAR para aceptar; Enter para cancelar: ').strip() != 'CONTINUAR':
            print('Cancelado. No se abrió ningún perfil.'); return
    raw_limit = input('Máximo de perfiles (Enter = 3 para prueba; 0 = todos los seleccionados): ').strip() or '3'
    if not raw_limit.isdigit():
        print('Cantidad inválida. No se inició la descarga.'); return
    limit = int(raw_limit)
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--user-data-dir=' + str(ROOT / 'perfil-occ'))
    driver = webdriver.Chrome(options=options)
    rows, report = [], {'opened': 0, 'excluded_unseen_or_unknown': 0, 'exported': 0, 'notes': []}
    try:
        driver.get(URL)
        input('Si OCC pide acceso, inicia sesión EN EL CHROME QUE SE ABRIÓ. Después pulsa Enter aquí. No abras candidatos.\n')
        driver.get(URL)
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        if urlparse(driver.current_url).hostname != 'empresa.occ.com.mx': raise RuntimeError('No se completó el acceso a OCC.')
        vacancy = input('Nombre exacto de la vacante de esta lista (por ejemplo Auxiliar Administrativo): ').strip()
        if not vacancy: raise RuntimeError('Falta la vacante; no se abrirán perfiles.')
        candidates = []
        report['pages_reviewed'] = 0
        page_signatures = set()
        import time
        for page in range(50):
            WebDriverWait(driver, 20).until(lambda d: d.execute_script(DISCOVER))
            page_items = driver.execute_script(DISCOVER)
            signature = tuple(item['url'] for item in page_items)
            if signature in page_signatures: break
            page_signatures.add(signature)
            report['pages_reviewed'] += 1
            for item in page_items:
                if item not in candidates: candidates.append(item)
            print('Página', page + 1, ':', len(page_items), 'tarjetas revisadas sin abrir perfiles.')
            next_buttons = [el for el in driver.find_elements(By.CSS_SELECTOR, 'button') if el.is_displayed() and norm(el.text) == 'siguiente']
            if len(next_buttons) != 1 or not next_buttons[0].is_enabled() or next_buttons[0].get_attribute('aria-disabled') == 'true': break
            next_buttons[0].click()
            try:
                WebDriverWait(driver, 20).until(lambda d: tuple(item['url'] for item in d.execute_script(DISCOVER)) not in ((), signature))
                time.sleep(0.5)
            except Exception:
                report['notes'].append('No cambió la página; se detuvo la paginación.'); break
        approved = select_candidates(candidates, mode, limit)
        report['excluded_unseen_or_unknown'] = sum(not seen_status(item['labels'], item.get('complete_card', False)) for item in candidates)
        if not approved:
            raise RuntimeError('No se reconocieron candidatos del filtro elegido. No se abrió ningún perfil.')
        print(f'Seleccionados: {len(approved)} perfiles. Filtro: {choice}.')
        for candidate in approved:
            url = candidate['url']
            driver.get(url)
            report['opened'] += 1
            WebDriverWait(driver, 25).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            body = driver.find_element(By.TAG_NAME, 'body').text
            if re.search(r'(?i)captcha|verifica que eres humano|verifica que no eres un robot', body): raise RuntimeError('Se requiere verificación humana; prueba detenida.')
            if not allowed_profile(driver.current_url): raise RuntimeError('OCC cambió la página o venció la sesión; prueba detenida.')
            # No pulsar botones de desbloqueo ni consumir créditos.
            if re.search(r'(?i)desbloquear|usar créditos|consumir créditos|comprar créditos', body):
                report['notes'].append('Perfil omitido: muestra controles de desbloqueo/créditos.'); continue
            toggles = [el for el in driver.find_elements(By.CSS_SELECTOR, 'button,[role="button"]') if el.is_displayed() and norm(el.text) == 'datos de contacto']
            contact = extract_profile(body)
            if not contact and len(toggles) == 1:
                toggles[0].click()
                try:
                    contact = WebDriverWait(driver, 8).until(lambda d: extract_profile(d.find_element(By.TAG_NAME, 'body').text))
                except Exception:
                    report['notes'].append('Perfil omitido: no se encontró un teléfono visible inequívoco.'); continue
            if contact:
                full_text = driver.find_element(By.TAG_NAME, 'body').text
                rows.append({**contact, **extract_sections(full_text), 'vacancy': vacancy, 'url': url, 'review_state': candidate['review_state']})
            else: report['notes'].append('Perfil omitido: nombre/teléfono no identificados con seguridad.')
    except Exception as error:
        report['notes'].append(str(error)); print('Aviso:', error)
    finally:
        output = ROOT / 'resultados'; output.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        report['exported'] = len(unique(rows))
        if rows:
            filename = output / f'postulados-{mode}-{stamp}.xlsx'
            export_xlsx(rows, filename); print('Excel:', filename)
        else: print('No se generó Excel: no hubo candidatos válidos. No se inventaron datos.')
        (output / f'informe-{stamp}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Exportados:', report['exported'], '| Perfiles abiertos:', report['opened'])
        input('Pulsa Enter para cerrar el Chrome de la prueba.\n')
        driver.quit()

if __name__ == '__main__': main()

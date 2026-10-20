"""Offline import of user-downloaded Indeed applications. No network access."""
import base64
import binascii
import hashlib
import json
import multiprocessing as mp
import re
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

VERSION = '1.0.0'
MAX_JSON = 45 * 1024 * 1024
MAX_PDF = 30 * 1024 * 1024
FIELDS = [
    ('name', 'Nombre', 32), ('email', 'Correo', 36), ('phone', 'Teléfono', 23),
    ('vacancy', 'Vacante', 34), ('company', 'Empresa', 24), ('location', 'Ubicación de la vacante', 28),
    ('applied', 'Fecha de postulación (UTC)', 28), ('experience', 'Experiencia (texto del CV)', 55),
    ('education', 'Educación (texto del CV)', 48), ('skills', 'Habilidades (texto del CV)', 45),
    ('languages', 'Idiomas (texto del CV)', 30), ('cv_file', 'Archivo CV (relativo al Excel)', 55),
    ('cv_status', 'Lectura del CV', 55), ('cv_text_file', 'Texto completo del CV (archivo)', 55),
    ('application_id', 'ID de postulación', 40), ('job_id', 'ID de vacante', 28),
    ('source', 'Archivo JSON de origen', 44), ('cv_text', 'Texto del CV (sin clasificación)', 80),
]


def text(value):
    return value.strip() if isinstance(value, str) else ''


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c)).strip().rstrip(':')


def sections(content):
    headings = {
        'experiencia': 'experience', 'experiencia laboral': 'experience',
        'experiencia profesional': 'experience', 'work experience': 'experience',
        'educacion': 'education', 'formacion': 'education', 'formacion academica': 'education',
        'education': 'education', 'estudios': 'education',
        'habilidades': 'skills', 'skills': 'skills', 'competencias': 'skills',
        'idiomas': 'languages', 'languages': 'languages',
        'contacto': None, 'contact': None, 'perfil': None, 'sobre mi': None,
        'referencias': None, 'certificaciones': None, 'cursos': None,
    }
    result, current = {}, None
    for line in content.splitlines():
        line = line.strip()
        if normalize(line) in headings:
            current = headings[normalize(line)]
        elif current and line:
            result[current] = (result.get(current, '') + '\n' + line).strip()
    return result


def _pdf_process(path, sender):
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            sender.send({'cv_status': 'PDF protegido; revisar el CV original.'})
            return
        if len(reader.pages) > 50:
            sender.send({'cv_status': 'Más de 50 páginas; revisar el CV original.'})
            return
        content = '\n'.join(page.extract_text() or '' for page in reader.pages).strip()
        if content:
            extracted = sections(content)
            status = ('Texto extraído; revisar secciones contra el CV original.' if extracted else
                      'Texto extraído; secciones no identificadas. Consulta Texto del CV / PDF.')
            sender.send({'cv_status': status, 'cv_text': content[:500000], **extracted})
        else:
            sender.send({'cv_status': 'Sin texto extraíble (posible escaneo); requiere OCR o revisión.'})
    except Exception:
        sender.send({'cv_status': 'No se pudo leer el PDF; revisar el archivo original.'})
    finally:
        sender.close()


def read_pdf(path, timeout=25):
    context = mp.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_pdf_process, args=(str(path), sender), daemon=True)
    try:
        process.start()
        sender.close()
        if receiver.poll(timeout):
            return receiver.recv()
        return {'cv_status': 'Lectura agotó el tiempo; CV conservado para revisión.'}
    except (EOFError, OSError):
        return {'cv_status': 'No se pudo iniciar la lectura del CV; archivo conservado.'}
    finally:
        receiver.close()
        sender.close()
        if process.pid:
            if process.is_alive():
                process.terminate()
            process.join(3)


def parse_application(path):
    if path.stat().st_size > MAX_JSON:
        raise ValueError('JSON supera 45 MB.')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('JSON inválido o codificación distinta de UTF-8.') from None
    if not isinstance(data, dict):
        raise ValueError('Se esperaba una postulación JSON de Indeed.')
    applicant, job = data.get('applicant'), data.get('job')
    if not isinstance(applicant, dict) or not isinstance(job, dict):
        raise ValueError('Faltan applicant/job de la postulación.')
    app_id, job_id = text(data.get('id')).lower(), text(job.get('jobId')) or text(job.get('jobKey'))
    if not re.fullmatch(r'[a-f0-9]{64}', app_id) or not job_id or not text(applicant.get('fullName')):
        raise ValueError('Falta un ID de postulación, vacante o nombre válido.')
    applied = ''
    millis = data.get('appliedOnMillis')
    if isinstance(millis, (int, float)) and not isinstance(millis, bool):
        try:
            applied = datetime.fromtimestamp(millis / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OverflowError, OSError):
            pass
    row = dict(name=text(applicant.get('fullName')), email=text(applicant.get('email')),
               phone=text(applicant.get('phoneNumber')), vacancy=text(job.get('jobTitle')),
               company=text(job.get('jobCompany')), location=text(job.get('jobLocation')),
               applied=applied, application_id=app_id, job_id=job_id, source=path.name)
    resume = applicant.get('resume')
    attachment = resume.get('file') if isinstance(resume, dict) else None
    return row, attachment if isinstance(attachment, dict) else None


def recover_cv(attachment, row, output):
    if not attachment:
        return {'cv_status': 'Sin CV adjunto en el JSON.'}
    encoded = attachment.get('data')
    if not isinstance(encoded, str) or not encoded:
        return {'cv_status': 'CV sin contenido en el JSON.'}
    if len(encoded) > (MAX_PDF * 4 // 3 + 8):
        return {'cv_status': 'CV supera 30 MB; no se recuperó.'}
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return {'cv_status': 'CV con Base64 inválido; no se recuperó.'}
    if not raw.startswith(b'%PDF-'):
        return {'cv_status': 'Adjunto no PDF; no se recuperó ni ejecutó.'}
    if len(raw) > MAX_PDF:
        return {'cv_status': 'CV supera 30 MB; no se recuperó.'}
    # Ignore supplied filenames entirely: traversal, executable extensions and collisions are impossible.
    token = hashlib.sha256((row['application_id'] + ':' + row['job_id']).encode()).hexdigest()[:24]
    relative = Path('CV') / (token + '.pdf')
    target = output / relative
    target.parent.mkdir(exist_ok=True)
    with target.open('xb') as handle:
        handle.write(raw)
    fields = read_pdf(target)
    content = fields.get('cv_text', '')
    if content:
        txt = relative.with_suffix('.txt')
        with (output / txt).open('x', encoding='utf-8') as handle:
            handle.write(content)
        fields['cv_text_file'] = str(txt)
    return {'cv_file': str(relative), **fields}


def column(index):
    result = ''
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


def xml_text(value):
    # Inline strings cannot run Excel formulas or external links.
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', str(value)))


def write_excel(rows, destination):
    headers = [f[1] for f in FIELDS]
    values = [headers] + [[r.get(key, '') for key, _, _ in FIELDS] for r in rows]
    body = []
    for i, row in enumerate(values, 1):
        cells = []
        for j, value in enumerate(row, 1):
            value = str(value)
            if len(value.encode('utf-16-le')) // 2 > 32767:
                value = value[:15000] + '\n[Sección larga: consultar el archivo TXT completo del CV.]'
            cells.append(f'<c r="{column(j)}{i}" t="inlineStr" s="{1 if i == 1 else 0}"><is><t xml:space="preserve">{xml_text(value)}</t></is></c>')
        body.append(f'<row r="{i}" ht="{32 if i == 1 else 75}" customHeight="1">' + ''.join(cells) + '</row>')
    cols = ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, (_, _, width) in enumerate(FIELDS, 1))
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<dimension ref="A1:{column(len(FIELDS))}{len(values)}"/>'
             '<sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane xSplit="1" ySplit="1" topLeftCell="B2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
             f'<cols>{cols}</cols><sheetData>{"".join(body)}</sheetData>'
             f'<autoFilter ref="A1:{column(len(FIELDS))}{len(values)}"/></worksheet>')
    styles = ('<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Arial"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF315546"/><bgColor indexed="64"/></patternFill></fill></fills>'
              '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2">'
              '<xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
              '<xf fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Postulaciones" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': sheet, 'xl/styles.xml': styles,
    }
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content)


def convert_folder(source, progress=lambda *args: None, cancelled=lambda: False):
    source = Path(source).resolve(strict=True)
    if not source.is_dir():
        raise ValueError('Selecciona una carpeta válida.')
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == '.json')
    if not files:
        raise ValueError('No hay archivos .json en esta carpeta. No se revisan subcarpetas.')
    output = Path(tempfile.mkdtemp(prefix='Indeed-Excel-' + datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=source))
    rows, seen, issues, duplicates = [], set(), [], 0
    for i, path in enumerate(files, 1):
        if cancelled():
            issues.append(('Proceso', 'Pausado por el usuario; vuelve a seleccionar la carpeta para regenerar todos los JSON.'))
            break
        progress(i, len(files))
        try:
            row, attachment = parse_application(path)
            key = (row['application_id'], row['job_id'])
            if key in seen:
                duplicates += 1
                continue
            row.update(recover_cv(attachment, row, output))
            rows.append(row)
            seen.add(key)
        except ValueError as error:
            issues.append((path.name, str(error)))
        except OSError:
            issues.append((path.name, 'No se pudo leer el JSON o guardar su CV. Revisa permisos/espacio.'))
    excel = output / 'Postulaciones.xlsx'
    if rows:
        write_excel(rows, excel)
    report = (f'Indeed JSON a Excel BPower {VERSION}\nJSON encontrados: {len(files)}\n'
              f'Postulaciones exportadas: {len(rows)}\nDuplicados omitidos: {duplicates}\nIncidencias: {len(issues)}\n'
              'No se modificaron los JSON originales. Fechas en UTC. Sin conexiones de red.\n'
              'Las secciones del CV son extracción de texto, no datos estructurados verificados.\n'
              'PDF escaneado: requiere OCR o revisión manual; esta versión no incluye OCR.\n\n'
              + '\n'.join(f'{name}: {reason}' for name, reason in issues))
    (output / 'LEEME-resultado.txt').write_text(report, encoding='utf-8')
    return dict(output=str(output), excel=str(excel) if rows else '', count=len(rows),
                total=len(files), duplicates=duplicates, errors=len(issues))

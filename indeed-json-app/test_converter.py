import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET
from unittest.mock import patch
from converter import convert_folder, parse_application, recover_cv, sections, write_excel, FIELDS


def application(id='a' * 64, job='vacante-1', resume=None):
    return dict(id=id, job=dict(jobId=job, jobTitle='Entrenador'), appliedOnMillis=1790647086316,
                applicant=dict(fullName='Persona de prueba', email='prueba@example.invalid', phoneNumber='+52 55 1234 5678', resume=resume))


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, data):
        path = self.folder / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8-sig')
        return path

    def test_real_schema_contacts_and_utc(self):
        row, cv = parse_application(self.put('a.json', application()))
        self.assertEqual(row['email'], 'prueba@example.invalid')
        self.assertEqual(row['phone'], '+52 55 1234 5678')
        self.assertEqual(row['applied'], '2026-09-29 01:58:06')
        self.assertIsNone(cv)

    def test_duplicate_app_but_not_different_job_or_application(self):
        self.put('a.json', application())
        self.put('b.JSON', application())
        self.put('c.json', application(job='vacante-2'))
        self.put('d.json', application(id='b' * 64))
        result = convert_folder(self.folder)
        self.assertEqual((result['count'], result['duplicates']), (3, 1))

    def test_malformed_files_continue_no_overwrite_original(self):
        self.put('good.json', application())
        (self.folder / 'bad.json').write_text('{', encoding='utf-8')
        (self.folder / 'existing.xlsx').write_bytes(b'preserve')
        one, two = convert_folder(self.folder), convert_folder(self.folder)
        self.assertEqual((one['count'], one['errors']), (1, 1))
        self.assertNotEqual(one['output'], two['output'])
        self.assertEqual((self.folder / 'existing.xlsx').read_bytes(), b'preserve')

    def test_empty_or_unknown_json(self):
        with self.assertRaises(ValueError):
            convert_folder(self.folder)
        self.put('unknown.json', {'hello': 'world'})
        self.assertEqual(convert_folder(self.folder)['count'], 0)

    def test_resume_bytes_preserved_and_filename_cannot_escape(self):
        raw = b'%PDF-1.4\nsynthetic'
        row, _ = parse_application(self.put('a.json', application()))
        with patch('converter.read_pdf', return_value={'cv_status': 'PDF de prueba'}):
            fields = recover_cv(dict(fileName='../../outside.exe', data=base64.b64encode(raw).decode()), row, self.folder)
        path = self.folder / fields['cv_file']
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(path.suffix, '.pdf')
        self.assertEqual(path.parent, self.folder / 'CV')

    def test_bad_base64_and_non_pdf(self):
        row = dict(application_id='a'*64, job_id='job')
        for data in ['**invalid**', base64.b64encode(b'MZexecutables').decode()]:
            fields = recover_cv({'data': data}, row, self.folder)
            self.assertNotIn('cv_file', fields)

    def test_pdf_extraction_scanned_and_broken(self):
        from pypdf import PdfWriter
        from converter import read_pdf
        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        pdf = self.folder / 'blank.pdf'
        writer.write(pdf)
        self.assertIn('Sin texto', read_pdf(pdf)['cv_status'])
        pdf.write_bytes(b'%PDF-broken')
        self.assertIn('No se pudo', read_pdf(pdf)['cv_status'])

    def test_sections_do_not_invent(self):
        self.assertEqual(sections('Algo sin encabezados'), {})
        self.assertEqual(sections('EXPERIENCIA\nEntrenador\nEducación\nUniversidad\nContacto\nNo incluir'),
                         {'experience': 'Entrenador', 'education': 'Universidad'})

    def test_excel_safe_strings_valid_xml_and_filters(self):
        path = self.folder / 'test.xlsx'
        write_excel([dict(name='=HYPERLINK("bad")', phone='00123', email='a&b@example.invalid', experience='CV\x00texto')], path)
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            self.assertEqual(sheet.findall('.//m:f', ns), [])
            self.assertEqual(sheet.find('.//m:c[@r="C2"]/m:is/m:t', ns).text, '00123')
            self.assertEqual(sheet.find('m:autoFilter', ns).get('ref'), 'A1:R2')

    def test_pause_preserves_completed_results(self):
        self.put('a.json', application())
        self.put('b.json', application(id='b'*64))
        calls = []
        result = convert_folder(self.folder, lambda *args: calls.append(args), lambda: len(calls) > 0)
        self.assertEqual(result['count'], 1)
        self.assertTrue(Path(result['excel']).exists())

    def test_oversized_json_documented(self):
        self.put('a.json', application())
        with patch('converter.MAX_JSON', 5):
            result = convert_folder(self.folder)
        self.assertEqual(result['errors'], 1)


if __name__ == '__main__':
    unittest.main()

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from indeed import (URL, DISCOVER, collect, first_page, offer_id, profile_id, record_key, merge_rows,
                    phone_from_call_panel, read_cv)
from occ_app import Progress, row_count
from occ_prueba import export_xlsx

OFFER = 'a'*12
LIST = 'https://employers.indeed.com/candidates?id='+OFFER+'&statusName=All'


def candidate(index):
    return {'url': 'https://employers.indeed.com/candidates/view?id='+str(index)*12+'&legacyJobId='+OFFER,
            'name': 'Persona de prueba '+str(index), 'review_state': 'Nuevos' if index == 1 else 'En evaluación'}


class IndeedTests(unittest.TestCase):
    def test_links_are_scoped_to_portal_and_application(self):
        self.assertEqual(offer_id(LIST), OFFER)
        self.assertEqual(profile_id(candidate(1)['url']), OFFER+':'+'1'*12)
        for bad in (LIST.replace('.com/', '.com.evil/'), LIST.replace('https:', 'http:'),
                    LIST.replace('employers.indeed.com', 'evil@employers.indeed.com'), LIST+'&id='+OFFER):
            self.assertFalse(offer_id(bad))
        self.assertFalse(profile_id(candidate(1)['url'].replace('legacyJobId', 'otherJob')))
        with self.assertRaises(ValueError):
            first_page(LIST.replace('All', 'New'))
        self.assertNotIn('offset=', first_page(LIST+'&offset=20'))

    def test_same_names_and_phones_do_not_merge_different_applications(self):
        a = {**candidate(1), 'name': 'Homónimo', 'phone': ''}
        b = {**candidate(2), 'name': 'Homónimo', 'phone': ''}
        rows = merge_rows([a], [b, {**a, 'phone': '5512345678'}])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['phone'], '5512345678')
        self.assertEqual(merge_rows(rows, [{**a, 'phone': ''}])[0]['phone'], '5512345678')
        self.assertEqual(row_count({'platform': 'indeed', 'rows': rows}), 2)
        with self.assertRaises(ValueError):
            merge_rows([], [{'url': 'https://evil.invalid', 'name': 'Persona'}])

    def test_phone_only_comes_from_the_opened_candidates_call_panel(self):
        self.assertEqual(phone_from_call_panel('Otro número 5599999999\nLlamar a Persona\n+52 55 1234 5678', 'Persona'), '5512345678')
        self.assertEqual(phone_from_call_panel('Llamar a Otra persona\n+52 55 1234 5678', 'Persona'), '')
        self.assertEqual(phone_from_call_panel('Llamar a Persona\n5512345678\n5587654321', 'Persona'), '')
        self.assertEqual(phone_from_call_panel('Llamar a Persona\nNo disponible', 'Persona'), '')

    def test_withdrawn_names_are_observations_not_invented_profile_identities(self):
        from uuid import uuid4
        a = {'name': 'Homónimo', 'url': LIST, 'withdrawn': True, 'observation_id': str(uuid4())}
        b = {**a, 'observation_id': str(uuid4())}
        self.assertFalse(profile_id(a['url']))
        self.assertNotEqual(record_key(a), record_key(b))
        self.assertEqual(len(merge_rows([a], [b])), 2)
        self.assertFalse(record_key({**a, 'observation_id': 'invalid'}))

    def test_scanned_pdf_is_not_reported_as_extracted_data(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'CV.pdf'
            writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.write(path)
            fields = read_cv(path)
            self.assertNotIn('experience', fields)
            self.assertNotIn('cv_text', fields)
            self.assertIn('sin texto', fields['cv_status'])

    def test_pdf_text_is_preserved_and_only_explicit_sections_are_split(self):
        text = 'Persona\nExperiencia laboral\nAnalista\nEducación\nEscuela ficticia\nIdiomas\nEspañol'
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: text)])
        with tempfile.TemporaryDirectory() as folder, patch('pypdf.PdfReader', return_value=reader):
            path = Path(folder)/'CV.pdf'; path.write_bytes(b'%PDF-test')
            result = read_cv(path)
        self.assertEqual(result['experience'], 'Analista')
        self.assertEqual(result['education'], 'Escuela ficticia')
        self.assertEqual(result['cv_text'], text)

    def test_xlsx_keeps_cv_reference_and_all_homonyms_as_text(self):
        rows = [{**candidate(i), 'platform': 'Indeed', 'phone': '', 'cv_text': '=not_a_formula()',
                 'cv_file': 'cvs-indeed/test/CV.pdf', 'cv_status': 'Revisión'} for i in (1, 2)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'candidatos.xlsx'
            export_xlsx(rows, path, deduplicate=False)
            with zipfile.ZipFile(path) as archive:
                xml = archive.read('xl/worksheets/sheet1.xml').decode()
            self.assertEqual(xml.count('<row '), 3)
            self.assertIn('A1:Q3', xml)
            self.assertIn('=not_a_formula()', xml)
            self.assertNotIn('<f>', xml)
            self.assertIn('Archivo CV', xml)

    def test_begin_dispatches_indeed_worker_and_preserves_vacancy_history(self):
        with tempfile.TemporaryDirectory() as folder, patch('occ_app.threading.Thread') as thread:
            p = Progress(folder)
            with self.assertRaises(ValueError):
                p.begin('Vacante', 'all', platform='indeed')
            with self.assertRaises(ValueError):
                p.begin('Vacante', 'seen', platform='indeed', consent=True)
            p.begin('Vacante', 'all', platform='indeed', consent=True)
            self.assertEqual(thread.call_args.kwargs['target'], p.run_worker)
            self.assertEqual(thread.call_args.kwargs['args'], (collect,))
            p.data.update(complete=True, offer_id=OFFER, rows=[{**candidate(1), 'phone': ''}])
            p.save(); p.busy = False
            p.begin('Vacante', 'all', platform='indeed', action='update', consent=True)
            self.assertEqual(len(p.previous_rows('indeed', 'Vacante', OFFER)), 1)
            self.assertEqual(p.previous_rows('indeed', 'Vacante', 'b'*12), [])
            self.assertEqual(Progress(folder).data['platform'], 'indeed')

    def fake_browser(self, *, wrong_total=False, withdrawn=False):
        rows = [candidate(i) for i in (1, 2, 3)]
        class Driver:
            current_url = LIST
            page = 0
            opened = []
            fail = True
            def get(self, url):
                self.current_url = LIST if url == URL else url
                self.page = 0
                if profile_id(url):
                    self.opened.append(url)
                    if self.fail and url == rows[1]['url']:
                        raise OSError('Test interruption')
            def set_page_load_timeout(self, value): pass
            def quit(self): pass
            def execute_script(self, script):
                assert script == DISCOVER
                return {'items': rows[:2] if self.page == 0 else rows[2:],
                        'withdrawn': [{'name':'Retirada de prueba', 'review_state':'Postulación retirada'}] if withdrawn and self.page == 1 else [],
                        'pagination': [1, 2, 4 if wrong_total or withdrawn else 3] if self.page == 0 else [3, 4 if withdrawn else 3, 4 if wrong_total or withdrawn else 3]}
            def find_elements(self, by, selector):
                if 'name-plate' in selector:
                    item = next(row for row in rows if row['url'] == self.current_url)
                    return [SimpleNamespace(text=item['name'], is_displayed=lambda: True)]
                assert selector == 'button'
                def click(): self.page = 1
                return [SimpleNamespace(text='Siguiente', is_displayed=lambda: True, is_enabled=lambda: self.page == 0,
                    get_attribute=lambda name: 'true' if self.page == 1 else 'false', click=click)]
        class Wait:
            def __init__(self, driver, _): self.driver = driver
            def until(self, callback):
                value = callback(self.driver)
                if not value: raise TimeoutError('Test timeout')
                return value
        driver = Driver()
        options = SimpleNamespace(add_argument=lambda value: None)
        modules = {'selenium': SimpleNamespace(webdriver=SimpleNamespace(Chrome=lambda **kw: driver, ChromeOptions=lambda: options)),
                   'selenium.webdriver.common.by': SimpleNamespace(By=SimpleNamespace(CSS_SELECTOR='css')),
                   'selenium.webdriver.support.ui': SimpleNamespace(WebDriverWait=Wait)}
        return driver, modules

    def progress(self, folder):
        p = Progress(folder)
        p.data = dict(version=1, platform='indeed', action='new', vacancy='Prueba', mode='all',
                      candidates=[], selected=[], rows=[], done=[], pages=0, listed=False, complete=False, skipped=0)
        p.ready.set()
        return p

    @patch('indeed.download_cv', return_value=None)
    @patch('indeed.read_contact_phone', return_value='')
    def test_full_pagination_and_restart_do_not_repeat_saved_candidates(self, number, cv):
        driver, modules = self.fake_browser()
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', modules):
            p = self.progress(folder)
            collect(p)
            self.assertEqual(len(p.data['selected']), 3)
            self.assertEqual(p.data['done'], [candidate(1)['url']])
            self.assertFalse(p.data['complete'])
            restarted = Progress(folder); restarted.ready.set(); driver.fail = False; driver.opened = []
            collect(restarted)
            self.assertTrue(restarted.data['complete'])
            self.assertNotIn(candidate(1)['url'], driver.opened)
            self.assertEqual(len(restarted.data['rows']), 3)
            self.assertEqual(restarted.data['rows'][0]['review_state'], 'Nuevos')
            self.assertTrue(restarted.excel().exists())

    @patch('indeed.download_cv')
    @patch('indeed.read_contact_phone')
    def test_missing_page_is_not_reported_complete(self, number, cv):
        driver, modules = self.fake_browser(wrong_total=True)
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', modules):
            p = self.progress(folder); collect(p)
            self.assertFalse(p.data['listed'])
            self.assertFalse(p.data['complete'])
            self.assertIn('no coincide', p.message)
            self.assertEqual(p.data['done'], [])
            cv.assert_not_called()

    @patch('indeed.download_cv', return_value=None)
    @patch('indeed.read_contact_phone', return_value='')
    def test_withdrawn_rows_are_included_without_opening_a_nonexistent_profile(self, number, cv):
        driver, modules = self.fake_browser(withdrawn=True)
        driver.fail = False
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', modules):
            p = self.progress(folder); collect(p)
            self.assertTrue(p.data['complete'])
            self.assertEqual(len(p.data['rows']), 4)
            self.assertEqual(p.data['withdrawn_count'], 1)
            self.assertEqual(len(driver.opened), 3)
            self.assertEqual(p.data['rows'][-1]['review_state'], 'Postulación retirada')
            self.assertEqual(p.data['rows'][-1]['phone'], '')

    def test_ui_contains_indeed_and_mobile_layout_and_no_idle_polling(self):
        html = (Path(__file__).parent/'pantalla.html').read_text(encoding='utf-8')
        self.assertIn('<option value="indeed">Indeed</option>', html)
        self.assertIn('max-width:600px', html)
        self.assertNotIn('setInterval(refresh', html)
        self.assertIn('s.busy&&!document.hidden', html)


if __name__ == '__main__':
    unittest.main()

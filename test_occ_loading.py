import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from selenium.common.exceptions import TimeoutException
from occ_app import Progress, collect, read_occ_candidate

URL = 'https://empresa.occ.com.mx/empresas/candidatos/1/cv/2/3'
EMPTY = 'MXN Actual aproximado\nDatos de contacto\nDescarga CV\nCV: 0\nInformación de tu vacante'
GOOD = 'Persona de Prueba\nCuauhtémoc, Ciudad de México\n$8,000 MXN\nDatos de contacto\n5512345678\nDescarga CV\nCV: 123'

class FiniteWait:
    def __init__(self, driver, seconds): self.driver = driver
    def until(self, condition):
        for _ in range(4):
            result = condition(self.driver)
            if result: return result
        raise TimeoutException()

class LoadingTests(unittest.TestCase):
    def driver(self, bodies, expanded='false'):
        texts = iter(bodies)
        body = SimpleNamespace(text=bodies[-1])
        toggle = Mock(text='Datos de contacto')
        toggle.is_displayed.return_value = True
        toggle.get_attribute.return_value = expanded
        def element(*args):
            body.text = next(texts, bodies[-1]); return body
        return SimpleNamespace(current_url=URL, find_element=element, find_elements=lambda *args:[toggle],
                               get=Mock(), quit=Mock(), set_page_load_timeout=Mock()), toggle

    def test_loading_profile_waits_for_real_data_without_clicking_cv_zero(self):
        driver, toggle = self.driver([EMPTY, EMPTY, GOOD])
        with patch('selenium.webdriver.support.ui.WebDriverWait', FiniteWait):
            result = read_occ_candidate(driver, SimpleNamespace(pause=SimpleNamespace(is_set=lambda:False)))
        self.assertEqual(result['contact']['phone'], '5512345678')
        toggle.click.assert_not_called()
        driver.get.assert_not_called()

    def test_open_contact_panel_is_never_collapsed_and_collapsed_panel_clicks_once(self):
        for expanded, expected in [('true',0),('false',1)]:
            driver, toggle = self.driver(['Datos de contacto\nDescarga CV\nCV: 123']*3+[GOOD], expanded)
            with patch('selenium.webdriver.support.ui.WebDriverWait', FiniteWait):
                self.assertIsNotNone(read_occ_candidate(driver, SimpleNamespace(pause=SimpleNamespace(is_set=lambda:False)))['contact'])
            self.assertEqual(toggle.click.call_count, expected)

    def progress(self, folder):
        p = Progress(folder)
        p.data = dict(version=1,vacancy='Prueba ficticia',mode='all',platform='occ',candidates=[],
                      selected=[{'url':URL,'review_state':'Visto'}],rows=[],done=[],pages=0,listed=True,complete=False,skipped=0)
        p.save();p.ready.set();p.busy=True
        return p

    def collect_with(self, p, driver):
        with patch('selenium.webdriver.Chrome',return_value=driver), patch('selenium.webdriver.support.ui.WebDriverWait',FiniteWait):
            collect(p)

    def test_cv_zero_pauses_keeps_browser_and_does_not_discard_or_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.progress(folder);driver,toggle=self.driver([EMPTY])
            self.collect_with(p,driver)
            self.assertIn('CV: 0',p.message)
            self.assertIn('ventana de OCC queda abierta',p.message)
            self.assertEqual(p.data['done'],[]);self.assertEqual(p.data['skipped'],0)
            self.assertFalse(p.data['complete']);self.assertFalse(p.busy)
            self.assertIs(p.browser,driver);driver.quit.assert_not_called()
            self.assertEqual(driver.get.call_count,2) # Initial list and one profile only.
            self.assertEqual(Progress(folder).data['done'],[])
            p.close_browser();driver.quit.assert_called_once();self.assertIsNone(p.browser)

    def test_verification_and_unavailable_profile_pause_without_reading_other_candidates(self):
        for body in ['Verifica que eres humano','Perfil no disponible']:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as folder:
                p=self.progress(folder);driver,_=self.driver([body]);self.collect_with(p,driver)
                self.assertEqual(p.data['done'],[]);self.assertFalse(p.data['complete'])
                self.assertIs(p.browser,driver);driver.quit.assert_not_called();p.close_browser()

    def test_manual_resume_closes_retained_browser_before_starting_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.progress(folder);p.busy=False;old=Mock();p.browser=old
            with patch('occ_app.threading.Thread') as thread:
                p.begin('', '', resume=True)
                old.quit.assert_called_once();thread.return_value.start.assert_called_once()
            self.assertIsNone(p.browser)

    def test_success_closes_browser_and_records_candidate_once(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.progress(folder);driver,_=self.driver([GOOD]);self.collect_with(p,driver)
            self.assertTrue(p.data['complete']);self.assertEqual(p.data['done'],[URL])
            self.assertEqual(len(p.data['rows']),1);driver.quit.assert_called_once()
            self.assertIsNone(p.browser)

    def test_legacy_contact_is_collected_and_continues_without_omitting(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.progress(folder)
            next_url=URL.rsplit('/',1)[0]+'/4'
            p.data['selected'].append(dict(url=next_url,review_state='Visto'))
            driver,_=self.driver([GOOD.replace('5512345678','04455- 12345678')])
            driver.get.side_effect=lambda url:setattr(driver,'current_url',url)
            self.collect_with(p,driver)
            self.assertTrue(p.data['complete'],p.message)
            self.assertEqual(p.data['done'],[URL,next_url])
            self.assertEqual(len(p.data['rows']),2)
            self.assertEqual(p.data['rows'][0]['phone'],'5512345678')
            self.assertFalse(p.data.get('omitted_profiles'))
            self.assertFalse(p.status()['can_skip'])
            self.assertEqual(p.issue,'')

    def test_pause_stops_wait_without_writing_candidate_and_closes_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            p=self.progress(folder);driver,_=self.driver([EMPTY]);p.pause.set()
            self.collect_with(p,driver)
            self.assertEqual(p.data['done'],[]);self.assertIsNone(p.browser)
            driver.quit.assert_called_once()

if __name__=='__main__': unittest.main()

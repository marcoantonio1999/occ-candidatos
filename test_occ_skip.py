import copy
import tempfile
import unittest
from unittest.mock import Mock, patch
import test_occ_loading as loading
from occ_app import Progress, collect


class SkipTests(unittest.TestCase):
    def paused(self, folder):
        helper = loading.LoadingTests()
        p = helper.progress(folder)
        driver, toggle = helper.driver([loading.EMPTY])
        helper.collect_with(p, driver)
        self.assertTrue(p.status()['can_skip'])
        return p, driver

    def run_inline(self, p, driver):
        token = p.skip_token
        def thread(*, target, args, **kwargs):
            result = Mock()
            result.start.side_effect = lambda: target(*args)
            return result
        with patch('occ_app.threading.Thread', side_effect=thread), \
             patch('selenium.webdriver.Chrome') as chrome, \
             patch('selenium.webdriver.support.ui.WebDriverWait', loading.FiniteWait):
            p.skip_profile(token)
            chrome.assert_not_called()

    def test_skip_keeps_rows_and_browser_and_visits_only_next_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            p, driver = self.paused(folder)
            next_url = loading.URL.rsplit('/',1)[0] + '/4'
            p.data['selected'].append(dict(url=next_url, review_state='Visto'))
            old_rows = [dict(name='Persona anterior', phone='5599999999',url=loading.URL+'/old')]
            p.data['rows'] = copy.deepcopy(old_rows)
            driver.find_element = lambda *args: type('Body',(),{'text':loading.GOOD})()
            driver.get.reset_mock()
            driver.get.side_effect = lambda url: setattr(driver,'current_url',url)
            self.run_inline(p,driver)
            driver.get.assert_called_once_with(next_url)
            driver.quit.assert_called_once()
            self.assertTrue(p.data['complete'])
            self.assertEqual(p.data['rows'][0],old_rows[0])
            self.assertEqual(len(p.data['rows']),2)
            self.assertEqual(p.data['done'],[loading.URL,next_url])
            self.assertEqual(p.data['skipped'],0) # Not mislabeled as requiring credits.
            saved=Progress(folder).data
            self.assertEqual(saved['omitted_profiles'],[dict(url=loading.URL,reason='profile_incomplete',decision='manual')])
            self.assertFalse(p.status()['can_skip'])
            self.assertIn(b'profile_omitted',p.diagnostics.export())
            self.assertNotIn(loading.URL.encode(),p.diagnostics.export())

    def test_stale_or_duplicate_click_does_not_omit_another_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            p,driver=self.paused(folder)
            with self.assertRaises(ValueError):p.skip_profile('stale-token')
            self.assertEqual(p.data['done'],[])
            token=p.skip_token
            self.run_inline(p,driver)
            with self.assertRaises(ValueError):p.skip_profile(token)
            self.assertEqual(p.data['done'],[loading.URL])

    def test_verification_or_busy_or_changed_page_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            p,driver=self.paused(folder)
            token=p.skip_token
            p.issue='read_validation'
            self.assertFalse(p.status()['can_skip'])
            with self.assertRaises(ValueError):p.skip_profile(token)
            p.issue='profile_incomplete';p.busy=True
            with self.assertRaises(ValueError):p.skip_profile(token)
            p.busy=False;driver.current_url='https://empresa.occ.com.mx/login'
            with self.assertRaises(ValueError):p.skip_profile(token)
            self.assertEqual(p.data['done'],[])

    def test_failed_checkpoint_does_not_advance_or_start_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            p,driver=self.paused(folder)
            with patch.object(p,'save',side_effect=OSError()),patch('occ_app.threading.Thread') as thread:
                with self.assertRaises(ValueError):p.skip_profile(p.skip_token)
                thread.assert_not_called()
            self.assertEqual(p.data['done'],[])
            self.assertEqual(Progress(folder).data['done'],[])
            self.assertIs(p.browser,driver)

    def test_next_incomplete_profile_requires_a_new_manual_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            p,driver=self.paused(folder)
            next_url=loading.URL.rsplit('/',1)[0]+'/4'
            p.data['selected'].append(dict(url=next_url,review_state='Visto'))
            driver.get.side_effect=lambda url:setattr(driver,'current_url',url)
            old_token=p.skip_token
            self.run_inline(p,driver)
            self.assertEqual(p.data['done'],[loading.URL])
            self.assertFalse(p.data['complete'])
            self.assertTrue(p.status()['can_skip'])
            self.assertNotEqual(p.skip_token,old_token)
            self.assertIs(p.browser,driver)
            driver.quit.assert_not_called()


if __name__=='__main__':unittest.main()

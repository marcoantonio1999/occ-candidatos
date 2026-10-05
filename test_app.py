import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from occ_app import Progress, Handler, collect


class LocalAppTests(unittest.TestCase):
    def make_progress(self, folder):
        p = Progress(folder)
        p.data = dict(version=1, vacancy='Auxiliar', mode='all', candidates=[], selected=[],
                      rows=[], done=[], pages=0, listed=True, complete=False, skipped=0)
        return p

    def test_checkpoint_survives_restart_and_keeps_original_state(self):
        with tempfile.TemporaryDirectory() as folder:
            p = self.make_progress(folder)
            p.data['rows'] = [dict(name='Ana', phone='5512345678', review_state='Sin ver')]
            p.data['done'] = ['profile-a']
            p.save()
            restarted = Progress(folder)
            self.assertEqual(restarted.data['done'], ['profile-a'])
            self.assertEqual(restarted.data['rows'][0]['review_state'], 'Sin ver')
            self.assertEqual(restarted.status()['count'], 1)
            self.assertTrue(restarted.excel().exists())

    def test_atomic_failure_preserves_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            p = self.make_progress(folder)
            p.save()
            p.data['pages'] = 2
            import os
            replace = os.replace
            def fail_temp(source, dest):
                if Path(source).suffix == '.tmp' and Path(dest).suffix == '.json':
                    raise OSError('Simulated interruption')
                return replace(source, dest)
            with patch('occ_app.os.replace', side_effect=fail_temp):
                with self.assertRaises(OSError):
                    p.save()
            self.assertEqual(Progress(folder).data['pages'], 0)

    def test_corrupt_primary_recovers_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            p = self.make_progress(folder)
            p.save()
            p.data['pages'] = 2
            p.save()
            p.path.write_text('{broken', encoding='utf-8')
            self.assertEqual(Progress(folder).data['pages'], 0)

    def test_unseen_requires_consent_and_pending_work_is_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Progress(folder)
            with self.assertRaises(ValueError):
                p.begin('Auxiliar', 'unseen')
            p = self.make_progress(folder)
            with self.assertRaises(ValueError):
                p.begin('Otra vacante', 'seen')

    def test_local_server_rejects_foreign_hosts_and_missing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.token = 'test-token'
            server.progress = self.make_progress(folder)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                with urllib.request.urlopen(url + '/') as response:
                    self.assertIn(b'test-token', response.read())
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(url + '/estado')
                self.assertEqual(exc.exception.code, 403)
                request = urllib.request.Request(url + '/estado', headers={'X-OCC-Key':'test-token'})
                with urllib.request.urlopen(request) as response:
                    self.assertTrue(json.load(response)['saved'])
                request = urllib.request.Request(url + '/estado', headers={'Host':'evil.test','X-OCC-Key':'test-token'})
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(request)
                self.assertEqual(exc.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()

    def test_resume_skips_saved_profiles_and_network_failure_keeps_pending(self):
        base = 'https://empresa.occ.com.mx/empresas/candidatos/1/cv/2/'
        with tempfile.TemporaryDirectory() as folder:
            p = self.make_progress(folder)
            p.data['selected'] = [dict(url=base+'3', review_state='Visto'), dict(url=base+'4', review_state='Sin ver')]
            p.data['done'] = [base+'3']
            p.save()
            p.ready.set()
            calls = []
            def get(url):
                calls.append(url)
                if url == base+'4':
                    raise OSError('Internet disconnected')
            driver = SimpleNamespace(get=get, set_page_load_timeout=lambda n: None, current_url=base+'3', quit=lambda: None)
            options = SimpleNamespace(add_argument=lambda value: None)
            modules = {'selenium':SimpleNamespace(webdriver=SimpleNamespace(Chrome=lambda **kw:driver, ChromeOptions=lambda:options)),
                       'selenium.webdriver.common.by':SimpleNamespace(By=SimpleNamespace()),
                       'selenium.webdriver.support.ui':SimpleNamespace(WebDriverWait=object)}
            with patch.dict('sys.modules', modules):
                collect(p)
            self.assertNotIn(base+'3', calls)
            self.assertIn(base+'4', calls)
            restarted = Progress(folder)
            self.assertEqual(restarted.data['done'], [base+'3'])
            self.assertFalse(restarted.data['complete'])
            self.assertIn('avance guardado', p.message)


if __name__ == '__main__':
    unittest.main()

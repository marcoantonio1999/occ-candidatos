import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
from diagnostics import DiagnosticLog
from occ_app import Progress, Handler, running_version, VERSION
from http.server import ThreadingHTTPServer

class DiagnosticTests(unittest.TestCase):
    def test_errors_exclude_messages_source_locals_urls_and_private_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            log=DiagnosticLog(folder,VERSION)
            try:
                private='candidate@example.com password-token-secret 5512345678 https://example.com/private'
                raise RuntimeError(private)
            except RuntimeError as exc:
                log.event('worker_error',exc=exc,stage='reading_profile',body=private,url=private,password=private)
            data=log.export().decode()
            for text in ['candidate@example.com','password-token-secret','5512345678','example.com/private',folder]:
                self.assertNotIn(text,data)
            record=json.loads(log.path.read_text().splitlines()[-1])
            self.assertEqual(record['exception'],'RuntimeError')
            self.assertEqual(record['frames'][-1]['file'],'test_diagnostics.py')
            self.assertNotIn('body',record);self.assertNotIn('url',record)

    def test_rotation_is_bounded_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            log=DiagnosticLog(folder,VERSION,max_bytes=500)
            for i in range(100):log.event('profile_start',profile_number=i)
            files=list(Path(folder).glob('*.log'))
            self.assertLessEqual(len(files),2)
            self.assertTrue(all(f.stat().st_size<800 for f in files))
            self.assertIn(b'profile_start',DiagnosticLog(folder,VERSION).export())

    def test_logging_failure_does_not_interrupt_download(self):
        with tempfile.TemporaryDirectory() as folder:
            log=DiagnosticLog(folder,VERSION)
            with patch('diagnostics.Path.open',side_effect=OSError('readonly')):
                log.event('app_start')
            self.assertFalse(log.available)

    def test_unhandled_worker_is_logged_and_becomes_visible_in_status(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Progress(folder);p.busy=True;p.stage='reading_profile'
            def crash(_):raise RuntimeError('PRIVATE DATA MUST NOT BE LOGGED')
            p.run_worker(crash)
            self.assertFalse(p.busy)
            self.assertEqual(p.status()['issue'],'unhandled_worker')
            self.assertIn(b'RuntimeError',p.diagnostics.export())
            self.assertNotIn(b'PRIVATE DATA',p.diagnostics.export())

    def test_diagnostic_download_needs_local_host_and_key_and_works_without_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            server.token='fictional-local-key';server.progress=Progress(folder)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}/diagnostico'
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url)
                req=urllib.request.Request(url,headers={'X-OCC-Key':server.token})
                with urllib.request.urlopen(req) as result:
                    self.assertEqual(result.status,200);self.assertIn(b'diagnostic_download',result.read())
                req=urllib.request.Request(url,headers={'X-OCC-Key':server.token,'Host':'foreign.test'})
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(req)
                self.assertEqual(server.progress.status()['count'],0)
            finally:server.shutdown();server.server_close()

    def test_version_detection_is_local_only_and_does_not_export_page_token(self):
        with patch('urllib.request.urlopen') as request:
            self.assertEqual(running_version('http://127.0.0.1:80@foreign.test/'),'unknown')
            request.assert_not_called()
            request.return_value.__enter__.return_value.read.return_value=b'VERSI\xc3\x93N 1.2.2 SECRET_TOKEN'
            self.assertEqual(running_version('http://127.0.0.1:1234/'),'1.2.2')

if __name__=='__main__':unittest.main()

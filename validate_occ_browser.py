"""Optional integration check: real Chrome, local synthetic pages, no OCC traffic."""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import occ_app


class Fixture(BaseHTTPRequestHandler):
    body = 'Datos de contacto<br>Descarga CV<br>CV: 0'

    def log_message(self, *args):
        pass

    def do_GET(self):
        content = ('<html><body>' + self.body + '</body></html>').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    real_chrome = webdriver.Chrome
    drivers = []

    def chrome(options):
        assert options.experimental_options['detach'] is True
        # Isolated temporary profile; never open the user's authenticated Chrome.
        options.arguments[:] = [arg for arg in options.arguments if not arg.startswith('--user-data-dir=')]
        options.add_argument('--headless=new')
        if os.environ.get('OCC_TEST_CHROME'):
            options.binary_location = os.environ['OCC_TEST_CHROME']
        driver = real_chrome(options=options, service=webdriver.ChromeService(os.environ['OCC_TEST_CHROMEDRIVER']))
        drivers.append(driver)
        return driver

    try:
        for good in (False, True):
            Fixture.body = ('Persona Ficticia<br>Ciudad de México<br>$8,000 MXN<br>Datos de contacto<br>5512345678<br>Descarga CV<br>CV: 123'
                            if good else 'Datos de contacto<br>Descarga CV<br>CV: 0')
            with tempfile.TemporaryDirectory() as folder:
                p = occ_app.Progress(folder)
                profile = base + '/profile'
                p.data = dict(version=1, vacancy='Ficticia', mode='all', platform='occ', candidates=[],
                              selected=[dict(url=profile, review_state='Visto')], rows=[], done=[],
                              pages=0, listed=True, complete=False, skipped=0)
                p.save()
                p.ready.set()
                p.busy = True
                with patch('selenium.webdriver.Chrome', chrome), patch('occ_app.URL', base + '/list'), \
                     patch('occ_app.urlsplit', return_value=SimpleNamespace(hostname='empresa.occ.com.mx')), \
                     patch('occ_app.allowed_profile', side_effect=lambda url: url == profile), \
                     patch('selenium.webdriver.support.ui.WebDriverWait', side_effect=lambda driver, seconds: WebDriverWait(driver, .6)):
                    p.run_worker(occ_app.collect)
                assert not p.busy
                if not good:
                    assert p.issue == 'profile_incomplete', p.issue
                    assert not p.data['done'] and not p.data['complete']
                    assert p.browser is drivers[-1]
                    assert p.browser.window_handles
                    assert p.browser.current_url == profile
                    log = p.diagnostics.export().decode()
                    assert 'profile_paused' in log and 'browser_retained' in log
                    assert profile not in log and '5512345678' not in log
                    p.close_browser('manual_resume')
                    assert drivers[-1].service.process.poll() is not None
                else:
                    assert p.data['complete'] and len(p.data['rows']) == 1, p.message
                    assert p.browser is None
                    assert drivers[-1].service.process.poll() is not None
                print(json.dumps(dict(realChrome=True, complete=good, browserRetained=not good,
                                      progressPreserved=True, noOCCTraffic=True)))
    finally:
        for driver in drivers:
            try:
                driver.quit()
            except Exception:
                pass
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()

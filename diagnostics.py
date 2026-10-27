"""Local bounded diagnostics. Deliberately excludes exception messages and locals."""
import json
import re
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

EVENTS = {'app_start','app_stop','existing_instance','worker_start','worker_end','worker_error',
          'browser_started','browser_close','browser_retained','profile_start','profile_state',
          'profile_saved','list_start','list_page','waiting_ready','manual_resume','pause_requested',
          'startup_error','checkpoint_error','diagnostic_download','profile_paused','completed'}
TEXT_KEYS = {'stage','code','reason','exception','active_version','browser_version','driver_version','platform'}
INT_KEYS = {'profile_number','reviewed','total','page','rows','pid'}
BOOL_KEYS = {'cv_zero','has_contact','contact_open','service_alive','complete'}

def safe_word(value):
    return re.sub(r'[^a-zA-Z0-9_.-]', '', str(value))[:64]

class DiagnosticLog:
    def __init__(self, folder, version, max_bytes=256_000):
        self.folder, self.version = Path(folder), version
        self.path = self.folder / 'diagnostico.log'
        self.max_bytes = max_bytes
        self.lock = threading.RLock()
        self.available = True

    def event(self, event, exc=None, **fields):
        if event not in EVENTS:
            return
        record = {'time_utc': datetime.now(timezone.utc).isoformat(), 'version': self.version, 'event': event}
        for key, value in fields.items():
            if key in TEXT_KEYS:
                record[key] = safe_word(value)
            elif key in INT_KEYS and isinstance(value, int) and not isinstance(value, bool):
                record[key] = value
            elif key in BOOL_KEYS and isinstance(value, bool):
                record[key] = value
        if exc is not None:
            record['exception'] = safe_word(type(exc).__name__)
            # No formatted exception, URL, source code, arguments, local variables,
            # user directory, page contents, cookies or candidate identifiers.
            record['frames'] = [{'file': safe_word(Path(f.filename).name), 'line': f.lineno,
                                 'function': safe_word(f.name)} for f in traceback.extract_tb(exc.__traceback__)[-10:]]
        try:
            with self.lock:
                self.folder.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                    self.path.replace(self.folder / 'diagnostico-anterior.log')
                with self.path.open('a', encoding='utf-8') as output:
                    output.write(json.dumps(record, ensure_ascii=True) + '\n')
                    output.flush()
                self.available = True
        except OSError:
            # Never lose a download because the diagnostic disk is unavailable.
            self.available = False

    def export(self):
        with self.lock:
            chunks = ['Diagnostico local de Candidatos. Sin datos de candidatos ni sesiones.\n']
            for path in (self.folder/'diagnostico-anterior.log', self.path):
                if path.exists():
                    chunks.append(path.read_text(encoding='utf-8')[-self.max_bytes*2:])
            return ''.join(chunks).encode('utf-8')

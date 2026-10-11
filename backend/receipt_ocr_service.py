"""Run the installed Windows OCR locally. Never send receipt data over the network."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from receipt_image_processing import prepare_images, recognition_score, reconstruct_text


def powershell_path():
    return Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def available():
    return os.name == 'nt' and powershell_path().is_file()


def extract(path):
    if not available():
        return '', ['Lokalny odczyt tekstu wymaga Windows z zainstalowanym językiem OCR. Wpisz dane ręcznie.']
    script = Path(__file__).parent / 'scripts/receipt-ocr.ps1'
    def read(candidate, timeout):
        process = subprocess.run(
            [str(powershell_path()), '-NoProfile', '-NonInteractive', '-File', str(script), '-ImagePath', str(candidate.resolve())],
            capture_output=True, text=True, encoding='utf-8-sig', timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False,
        )
        result = json.loads(process.stdout.strip())
        if process.returncode or result.get('error'):
            raise ValueError('OCR unavailable')
        return reconstruct_text(result)[:60000]

    try:
        deadline = time.monotonic()+45
        with tempfile.TemporaryDirectory(prefix='receipt-ocr-') as temporary:
            try:
                paths = [path] if path.suffix.lower() == '.pdf' else prepare_images(path, Path(temporary))
            except (ImportError, OSError, ValueError):
                paths = [path]
            candidates = []
            for candidate in paths:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    break
                try:
                    candidates.append(read(candidate, min(remaining, 15) if len(paths) > 1 else remaining))
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    continue
            text = max(candidates, key=recognition_score) if candidates else ''
        return text, [] if text.strip() else ['Nie odczytano tekstu ze zdjęcia. Sprawdź ostrość lub wpisz dane ręcznie.']
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return '', ['Nie udało się odczytać pliku lokalnie. Zdjęcie zachowano; możesz wpisać dane ręcznie. PDF może mieć najwyżej 3 strony.']

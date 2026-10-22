"""Gemini adapter with persisted request IDs and an atomic estimated spending cap."""
import json
import hashlib
import math
import os
import re
import uuid
from datetime import datetime, timezone

from api.exceptions import ApiError, ValidationError
from database import get_db


def now():
    return datetime.now(timezone.utc).isoformat()


def request_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Brak poprawnego identyfikatora żądania. Otwórz formularz ponownie.') from None


def number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValidationError(f'{label}: podaj liczbę od {low} do {high}.')
    return float(value)


def settings():
    row = get_db().execute('SELECT * FROM investment_ai_settings WHERE id=1').fetchone()
    value = json.loads(row['value']) if row else dict(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite'), daily_budget_usd=.25,
        input_usd_per_million=.25, output_usd_per_million=1.5, max_output_tokens=4096)
    usage = get_db().execute('SELECT COALESCE(SUM(cost_usd),0) FROM investment_ai_runs WHERE day=?', (now()[:10],)).fetchone()[0]
    return dict(value, version=row['version'] if row else 0, used_usd=round(usage, 6),
                configured=bool(os.getenv('GEMINI_API_KEY')), budget_day=now()[:10],
                price_note='Szacowanie według zapisanych stawek USD za milion tokenów, bez podatków. Limit dotyczy tej aplikacji, dzień według UTC. Sprawdź taryfę po zmianie modelu.')


def save_settings(data):
    model = data.get('model', '')
    if not isinstance(model, str) or not re.fullmatch(r'gemini-[a-zA-Z0-9.\-]{2,90}', model):
        raise ValidationError('Podaj identyfikator modelu Gemini.')
    value = dict(model=model, daily_budget_usd=number(data.get('daily_budget_usd'), 'Limit dzienny USD', 0, 100),
                 input_usd_per_million=number(data.get('input_usd_per_million'), 'Stawka wejścia', .001, 1000),
                 output_usd_per_million=number(data.get('output_usd_per_million'), 'Stawka wyjścia', .001, 1000),
                 max_output_tokens=int(number(data.get('max_output_tokens'), 'Limit odpowiedzi', 512, 8192)))
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        current = settings()
        if type(data.get('version')) is not int or data['version'] != current['version']:
            raise ApiError('ai_settings_changed', 'Ustawienia zostały zmienione. Wczytaj je ponownie.', status=409)
        db.execute('INSERT INTO investment_ai_settings(id,value,version) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value,version=excluded.version',
                   (json.dumps(value), current['version'] + 1))
        db.commit()
    except Exception:
        db.rollback(); raise
    return settings()


def generate(rid, kind, prompt, schema, system, video_url=None, before_reserve=None):
    rid = request_id(rid); db = get_db()
    fingerprint=hashlib.sha256(json.dumps([kind,prompt,schema,system,video_url],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    old = db.execute('SELECT * FROM investment_ai_runs WHERE id=?', (rid,)).fetchone()
    if old:
        if old['state'] == 'done' and old['kind'] == kind and old['fingerprint']==fingerprint:
            return json.loads(old['result'])
        raise ApiError('ai_request_exists', 'To żądanie jest w toku lub zakończyło się błędem. Ponów jako nową analizę.', status=409)
    if not os.getenv('GEMINI_API_KEY'):
        raise ApiError('ai_not_configured', 'Ustaw GEMINI_API_KEY w konfiguracji backendu. Podsumowanie danych działa bez klucza.', status=503)
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ApiError('ai_sdk_missing', 'Brakuje biblioteki google-genai. Zaktualizuj zależności backendu.', status=503) from None
    cfg = settings()
    if cfg['daily_budget_usd']<=0:
        raise ApiError('ai_budget_exceeded','Generowanie AI jest wyłączone przez dzienny limit 0 USD.',status=429)
    reserved=False
    contents = [prompt]
    if video_url:
        contents.insert(0, types.Part.from_uri(file_uri=video_url, mime_type='video/mp4'))
    try:
        with genai.Client(api_key=os.environ['GEMINI_API_KEY'], http_options=types.HttpOptions(timeout=60000,retry_options=types.HttpRetryOptions(attempts=1))) as client:
            count = client.models.count_tokens(model=cfg['model'], contents=[system, *contents])
            tokens = int(count.total_tokens or 0)
            if tokens <= 0 or tokens > 150000:
                raise ValidationError('Materiał jest za długi (limit 150 tys. tokenów). Wklej krótszy fragment z oznaczeniem czasu.')
            estimate = (tokens * cfg['input_usd_per_million'] + cfg['max_output_tokens'] * cfg['output_usd_per_million']) / 1_000_000
            try:
                db.execute('BEGIN IMMEDIATE')
                if before_reserve:
                    before_reserve()
                latest = settings()
                if db.execute('SELECT 1 FROM investment_ai_runs WHERE id=?',(rid,)).fetchone():
                    raise ApiError('ai_request_exists','To żądanie zostało już rozpoczęte. Wczytaj rozmowę ponownie.',status=409)
                if latest['version'] != cfg['version']:
                    raise ApiError('ai_settings_changed', 'Zmieniono ustawienia podczas przygotowania analizy. Ponów.', status=409)
                if latest['used_usd'] + estimate > cfg['daily_budget_usd']:
                    raise ApiError('ai_budget_exceeded', 'Ta analiza przekroczyłaby ustawiony dzienny limit kosztów AI.', status=429)
                db.execute('INSERT INTO investment_ai_runs(id,day,model,kind,state,cost_usd,created_at,fingerprint) VALUES(?,?,?,?,?,?,?,?)',
                           (rid, now()[:10], cfg['model'], kind, 'running', estimate, now(),fingerprint))
                db.commit()
                reserved=True
            except Exception:
                db.rollback(); raise
            response = client.models.generate_content(model=cfg['model'], contents=contents,
                config=types.GenerateContentConfig(system_instruction=system, temperature=.2,
                    max_output_tokens=cfg['max_output_tokens'], response_mime_type='application/json', response_json_schema=schema))
            result = json.loads(response.text or '')
            usage = response.usage_metadata
            incoming = int(getattr(usage, 'prompt_token_count', 0) or tokens)
            outgoing = int(getattr(usage, 'candidates_token_count', 0) or 0) + int(getattr(usage, 'thoughts_token_count', 0) or 0)
            cost = (incoming * cfg['input_usd_per_million'] + outgoing * cfg['output_usd_per_million']) / 1_000_000 if usage else estimate
            db.execute('UPDATE investment_ai_runs SET state=?,cost_usd=?,input_tokens=?,output_tokens=?,result=? WHERE id=?',
                       ('done', cost, incoming, outgoing, json.dumps(result, ensure_ascii=False), rid))
            db.commit()
            return result
    except (ValidationError, ApiError):
        raise
    except Exception as exc:
        # Retain the reserved estimate after uncertain provider failures; no automatic paid retry.
        if reserved:
            db.execute("UPDATE investment_ai_runs SET state='failed' WHERE id=? AND state='running'", (rid,)); db.commit()
        code = getattr(exc, 'code', None)
        message = ('Dostawca AI osiągnął limit zapytań. Spróbuj później.' if code == 429 else
                   'Model lub klucz AI jest niedostępny. Sprawdź ustawienia.' if code in (400, 401, 403, 404) else
                   'Nie udało się zakończyć analizy AI. Zachowano wcześniejsze rozmowy. Możesz spróbować ponownie.')
        raise ApiError('ai_provider_error', message, status=502) from None

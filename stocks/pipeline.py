from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json

from stocks.market import DEFAULT_SYMBOLS, BENCHMARK, sessions, validate, metrics
from stocks.summary import facts_for, select_with_openai, validate_selection, render
from stocks.live import EODHDProvider
from stocks.storage import connect, read, save


def yesterday(now=None):
    now = now or datetime.now(ZoneInfo('Europe/Budapest'))
    return now.astimezone(ZoneInfo('Europe/Budapest')).date() - timedelta(days=1)


def run(config, target=None, use_ai=False, selector=None, symbols=None):
    target = target or yesterday()
    if target > yesterday():
        return {'status': 'FAILED', 'errors': ['Only previous completed days can be analyzed.']}
    if len(sessions(target, target)) == 0:
        return {'status': 'NO_SESSION', 'target': str(target),
                'message': 'No trading session on the target date. No report was generated.'}
    requested = symbols if symbols is not None else config.get('REPORT_SYMBOLS', ','.join(DEFAULT_SYMBOLS)).split(',')
    symbols = tuple(dict.fromkeys([s.strip().upper() for s in requested if s.strip()] + [BENCHMARK]))
    if symbols == (BENCHMARK,) and not requested:
        return {'status': 'FAILED', 'errors': ['Select at least one stock.']}
    frame = EODHDProvider(config).history(symbols, target - timedelta(days=100), target)
    errors = validate(frame, target, symbols)
    if errors:
        return {'status': 'FAILED', 'errors': errors}
    facts = facts_for(metrics(frame), target)
    mode = ('ai' if use_ai else 'template') + ':eodhd:bud:en'
    from pathlib import Path
    prompt = (Path(__file__).resolve().parents[1] / 'prompts/daily_summary.txt').read_text(encoding='utf-8')
    snapshot = frame.to_json(orient='records', date_format='iso')
    key = hashlib.sha256(json.dumps([str(target), mode, config['OPENAI_MODEL'], prompt, snapshot, 'v2-en'], sort_keys=True).encode()).hexdigest()
    engine = connect(config['DATABASE_URL'])
    try:
        existing = read(engine, key)
        if existing:
            return json.loads(existing['payload'])
        ids = (selector or select_with_openai)(facts, config) if use_ai else list(facts)
        errors = validate_selection(ids, facts)
        if errors:
            return {'status': 'FAILED', 'errors': errors}
        result = dict(status='PASSED', target=str(target), mode=mode, summary=render(ids, facts),
                      fact_ids=ids, facts=facts, snapshot=json.loads(snapshot), language='en',
                      symbols=list(symbols), source='EODHD/BUD', model=config['OPENAI_MODEL'] if use_ai else None,
                      prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
        save(engine, key, target, mode, result)
        return result
    finally:
        engine.dispose()

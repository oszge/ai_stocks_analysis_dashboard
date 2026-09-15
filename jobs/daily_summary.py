"""Standalone worker; keep one instance running outside Streamlit."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import time
from stocks.config import settings
from stocks.pipeline import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true', help='Daily 08:00 Europe/Budapest worker')
    parser.add_argument('--template', action='store_true', help='Use verified templates without an OpenAI call')
    parser.add_argument('--symbols', help='Comma-separated stock symbols; defaults to REPORT_SYMBOLS')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    completed = None
    while True:
        now = datetime.now(ZoneInfo('Europe/Budapest'))
        if not args.watch or (now.hour >= 8 and completed != now.date()):
            try:
                result = run(settings(), use_ai=not args.template,
                             symbols=args.symbols.split(',') if args.symbols else None)
                logging.info('Daily report: %s', result['status'])
                if result['status'] in ('PASSED', 'NO_SESSION'):
                    completed = now.date()
                elif not args.watch:
                    raise SystemExit(1)
            except Exception as exc:
                # Do not log provider payloads, credentials, or connection strings.
                logging.error('Daily report failed (%s)', type(exc).__name__)
                if not args.watch:
                    raise SystemExit(1) from None
            if not args.watch:
                break
            if completed != now.date():
                time.sleep(300)
        time.sleep(30)


if __name__ == '__main__':
    main()

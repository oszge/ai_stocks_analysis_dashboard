from datetime import datetime, timezone
import json
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, select, insert
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
reports = Table('daily_reports', metadata,
    Column('run_key', String(64), primary_key=True), Column('target', String(10), nullable=False),
    Column('status', String(32), nullable=False), Column('mode', String(64), nullable=False),
    Column('created_at', String(40), nullable=False), Column('payload', Text, nullable=False))

def connect(url):
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if url.startswith('sqlite:///'):
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine

def read(engine, key):
    with engine.connect() as conn:
        row = conn.execute(select(reports).where(reports.c.run_key == key)).mappings().first()
        return dict(row) if row else None

def save(engine, key, target, mode, payload):
    try:
        with engine.begin() as conn:
            conn.execute(insert(reports).values(run_key=key, target=str(target), mode=mode,
                status='PASSED', created_at=datetime.now(timezone.utc).isoformat(),
                payload=json.dumps(payload, ensure_ascii=False)))
    except IntegrityError:
        if read(engine, key) is None:
            raise

def recent(engine):
    with engine.connect() as conn:
        return [dict(x) for x in conn.execute(select(reports).order_by(reports.c.created_at.desc()).limit(20)).mappings()]

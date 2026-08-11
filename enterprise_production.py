"""Production service layer for DEEP-Seek.

Optional production path: PostgreSQL + Redis + workers. The local SQLite POS remains
available when production infrastructure is not configured.
"""
from __future__ import annotations
import os, json, hashlib, secrets, time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

D=Decimal('0.01')
def money(v): return Decimal(str(v or 0)).quantize(D, rounding=ROUND_HALF_UP)
def utcnow(): return datetime.now(timezone.utc)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError:
    create_engine=sessionmaker=text=None

class ProductionStore:
    def __init__(self, url=None):
        self.url=url or os.getenv('DATABASE_URL','')
        if not self.url: raise RuntimeError('DATABASE_URL is required for production mode')
        if self.url.startswith('postgres://'): self.url='postgresql+psycopg://'+self.url[len('postgres://'):]
        if self.url.startswith('postgresql://'): self.url='postgresql+psycopg://'+self.url[len('postgresql://'):]
        self.engine=create_engine(self.url,pool_pre_ping=True,pool_size=int(os.getenv('DB_POOL_SIZE','10')),max_overflow=int(os.getenv('DB_MAX_OVERFLOW','20')),pool_recycle=1800)
        self.Session=sessionmaker(bind=self.engine,expire_on_commit=False)
    def ping(self):
        with self.engine.connect() as c: return bool(c.execute(text('SELECT 1')).scalar())

SCHEMA_SQL='''
CREATE TABLE IF NOT EXISTS production_migrations(version VARCHAR(64) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS production_jobs(id UUID PRIMARY KEY, kind VARCHAR(80) NOT NULL, payload JSONB NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0, run_after TIMESTAMPTZ NOT NULL DEFAULT now(), last_error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_jobs_ready ON production_jobs(status,run_after);
CREATE TABLE IF NOT EXISTS security_sessions(id UUID PRIMARY KEY, user_id VARCHAR(128) NOT NULL, refresh_hash VARCHAR(128) NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_sessions_user ON security_sessions(user_id,revoked_at);
CREATE TABLE IF NOT EXISTS security_events(id UUID PRIMARY KEY, user_id VARCHAR(128), event VARCHAR(80) NOT NULL, ip VARCHAR(80), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), details JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS approval_requests(id UUID PRIMARY KEY, kind VARCHAR(80) NOT NULL, entity_id VARCHAR(128) NOT NULL, requested_by VARCHAR(128) NOT NULL, amount NUMERIC(18,2), status VARCHAR(20) NOT NULL DEFAULT 'PENDING', approved_by VARCHAR(128), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS bank_reconciliations(id UUID PRIMARY KEY, account_code VARCHAR(40) NOT NULL, statement_ref VARCHAR(200), statement_date DATE NOT NULL, amount NUMERIC(18,2) NOT NULL, matched_journal_id VARCHAR(128), status VARCHAR(20) NOT NULL DEFAULT 'UNMATCHED');
CREATE TABLE IF NOT EXISTS recurring_expenses(id UUID PRIMARY KEY, name VARCHAR(200) NOT NULL, account_code VARCHAR(40) NOT NULL, amount NUMERIC(18,2) NOT NULL, frequency VARCHAR(20) NOT NULL, next_due DATE NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS fixed_assets(id UUID PRIMARY KEY, asset_no VARCHAR(100) UNIQUE NOT NULL, name VARCHAR(200) NOT NULL, account_code VARCHAR(40) NOT NULL, cost NUMERIC(18,2) NOT NULL, residual NUMERIC(18,2) NOT NULL DEFAULT 0, useful_months INTEGER NOT NULL, acquired_on DATE NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS tax_returns(id UUID PRIMARY KEY, period VARCHAR(20) NOT NULL, tax_code VARCHAR(40) NOT NULL, output_tax NUMERIC(18,2) NOT NULL DEFAULT 0, input_tax NUMERIC(18,2) NOT NULL DEFAULT 0, adjustments NUMERIC(18,2) NOT NULL DEFAULT 0, status VARCHAR(20) NOT NULL DEFAULT 'DRAFT', submitted_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS inventory_serials(serial_no VARCHAR(200) PRIMARY KEY, product_id VARCHAR(128) NOT NULL, store_id VARCHAR(128) NOT NULL, lot_id VARCHAR(128), status VARCHAR(30) NOT NULL DEFAULT 'IN_STOCK', received_at TIMESTAMPTZ NOT NULL DEFAULT now(), sold_source_id VARCHAR(128));
CREATE TABLE IF NOT EXISTS stock_counts(id UUID PRIMARY KEY, store_id VARCHAR(128) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'DRAFT', created_by VARCHAR(128) NOT NULL, approved_by VARCHAR(128), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS customer_credit(customer_id VARCHAR(128) PRIMARY KEY, credit_limit NUMERIC(18,2) NOT NULL DEFAULT 0, balance NUMERIC(18,2) NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS promotions(id UUID PRIMARY KEY, name VARCHAR(200) NOT NULL, rules JSONB NOT NULL, starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS loyalty_tiers(id UUID PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, min_points NUMERIC(18,2) NOT NULL, multiplier NUMERIC(10,4) NOT NULL DEFAULT 1);
'''

def bootstrap_sql(store: ProductionStore):
    with store.engine.begin() as c:
        for statement in SCHEMA_SQL.split(';'):
            s=statement.strip()
            if s: c.execute(text(s))

def enqueue(store: ProductionStore, kind:str, payload:dict, delay=0):
    jid=secrets.token_hex(16)
    with store.engine.begin() as c:
        c.execute(text("INSERT INTO production_jobs(id,kind,payload,run_after) VALUES(:id,:kind,:payload,now()+(:delay * interval '1 second'))"),{'id':jid,'kind':kind,'payload':json.dumps(payload),'delay':delay})
    return jid

def create_refresh_session(store,user_id,ttl_hours=24*30):
    raw=secrets.token_urlsafe(48); h=hashlib.sha256(raw.encode()).hexdigest(); sid=secrets.token_hex(16)
    with store.engine.begin() as c:
        c.execute(text("INSERT INTO security_sessions(id,user_id,refresh_hash,expires_at) VALUES(:id,:u,:h,:e)"),{'id':sid,'u':user_id,'h':h,'e':utcnow()+timedelta(hours=ttl_hours)})
    return sid,raw

def revoke_sessions(store,user_id):
    with store.engine.begin() as c: c.execute(text("UPDATE security_sessions SET revoked_at=now() WHERE user_id=:u AND revoked_at IS NULL"),{'u':user_id})

def fixed_asset_monthly_depreciation(cost,residual,useful_months):
    months=max(int(useful_months),1); return money((Decimal(str(cost))-Decimal(str(residual)))/months)

def aging_bucket(days):
    return '0-30' if days<=30 else '31-60' if days<=60 else '61-90' if days<=90 else '91-120' if days<=120 else '120+'

def route_request(provider,origin,destination,waypoints=None):
    """Provider-independent contract. Provider adapters live in integrations/."""
    return {'provider':provider,'origin':origin,'destination':destination,'waypoints':waypoints or [],'status':'CONFIGURE_PROVIDER'}

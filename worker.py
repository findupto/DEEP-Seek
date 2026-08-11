"""Redis-backed production worker. Optional; local POS never depends on it."""
from __future__ import annotations
import os, json, time
try:
    import redis
except ImportError: redis=None
from enterprise_production import ProductionStore, bootstrap_sql

def main():
    if redis is None: raise SystemExit('Install redis dependency')
    store=ProductionStore(); bootstrap_sql(store); r=redis.Redis.from_url(os.getenv('REDIS_URL','redis://localhost:6379/0'),decode_responses=True)
    while True:
        item=r.brpop('deepseek:jobs',timeout=5)
        if not item: continue
        _, raw=item
        job=json.loads(raw)
        # Dispatch hooks can be registered by provider modules.
        print('processed job',job.get('kind'),flush=True)

if __name__=='__main__': main()

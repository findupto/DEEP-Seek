"""Enterprise HTTP API with local fallback and production PostgreSQL readiness."""
import os, secrets, hashlib
from pathlib import Path
from enterprise_completion_patch import connect, apply_sync, audit, p_and_l, trial_balance, verify_audit
try:
    from fastapi import FastAPI, HTTPException, Header
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from fastapi.responses import FileResponse
    from enterprise_production import ProductionStore, bootstrap_sql
except ImportError:
    FastAPI = None

DB=os.getenv('POS_DB','pos.db'); API_TOKEN=os.getenv('POS_API_TOKEN','')
PROD_DB=os.getenv('DATABASE_URL','')
if FastAPI:
    app=FastAPI(title='DEEP-Seek Enterprise POS API',version='2.0.0')
    origins=[x.strip() for x in os.getenv('POS_CORS','*').split(',') if x.strip()]
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['*'],allow_headers=['*'])
    def auth(token):
        if API_TOKEN and not token: raise HTTPException(401,'API token required')
        if API_TOKEN and not secrets.compare_digest(token or '',API_TOKEN): raise HTTPException(403,'Invalid API token')
    def production():
        if not PROD_DB: return None
        try:
            s=ProductionStore(PROD_DB); bootstrap_sql(s); return s
        except Exception: return None
    class SyncItem(BaseModel): key:str=Field(min_length=8,max_length=200); payload:dict
    class GPSItem(BaseModel): rider_id:str; lat:float; lon:float; accuracy:float|None=None; recorded_at:str|None=None
    @app.get('/health')
    def health():
        c=connect(DB); ok=verify_audit(c); c.close(); return {'ok':ok,'service':'DEEP-Seek','version':'2.0.0','mode':'production' if PROD_DB else 'local'}
    @app.get('/ready')
    def ready():
        s=production()
        if PROD_DB and not s: raise HTTPException(503,'database not ready')
        if s and not s.ping(): raise HTTPException(503,'database not ready')
        return {'ready':True,'database':'postgresql' if s else 'sqlite'}
    @app.get('/api/pnl')
    def pnl(store_id:str|None=None,x_api_token:str|None=Header(default=None)): auth(x_api_token); c=connect(DB); out=p_and_l(c,store_id); c.close(); return out
    @app.get('/api/trial-balance')
    def tb(store_id:str|None=None,x_api_token:str|None=Header(default=None)): auth(x_api_token); c=connect(DB); out=trial_balance(c,store_id); c.close(); return out
    @app.post('/api/sync')
    def sync(item:SyncItem,x_api_token:str|None=Header(default=None)):
        auth(x_api_token); c=connect(DB); out=apply_sync(c,item.key,item.payload,lambda p:{'accepted':True,'payload_hash':hashlib.sha256(str(sorted(p.items())).encode()).hexdigest()}); audit(c,'api','SYNC','sync',item.key,item.payload); c.close(); return out
    @app.post('/api/gps')
    def gps(item:GPSItem,x_api_token:str|None=Header(default=None)):
        auth(x_api_token); c=connect(DB); c.execute('CREATE TABLE IF NOT EXISTS ent_gps(id INTEGER PRIMARY KEY AUTOINCREMENT,rider_id TEXT,lat REAL,lon REAL,accuracy REAL,recorded_at TEXT)'); c.execute('INSERT INTO ent_gps(rider_id,lat,lon,accuracy,recorded_at) VALUES(?,?,?,?,COALESCE(?,datetime("now")))',(item.rider_id,item.lat,item.lon,item.accuracy,item.recorded_at)); c.commit(); c.close(); return {'accepted':True}
    @app.get('/api/gps/{rider_id}')
    def gps_history(rider_id:str,x_api_token:str|None=Header(default=None)): auth(x_api_token); c=connect(DB); c.execute('CREATE TABLE IF NOT EXISTS ent_gps(id INTEGER PRIMARY KEY AUTOINCREMENT,rider_id TEXT,lat REAL,lon REAL,accuracy REAL,recorded_at TEXT)'); rows=[dict(r) for r in c.execute('SELECT * FROM ent_gps WHERE rider_id=? ORDER BY id DESC LIMIT 200',(rider_id,))]; c.close(); return rows
    @app.get('/')
    def web():
        p=Path(__file__).with_name('pwa').joinpath('index.html'); return FileResponse(p) if p.exists() else {'service':'DEEP-Seek','api':'/health'}
else: app=None

if __name__=='__main__':
    if not app: raise SystemExit('Install enterprise requirements')
    import uvicorn; uvicorn.run(app,host=os.getenv('POS_HOST','0.0.0.0'),port=int(os.getenv('POS_PORT','8080')))

"""Enterprise HTTP API with safe-by-default authentication and local fallback.

The desktop POS remains fully local-first. The API is optional and is intended
for a controlled LAN/cloud deployment with POS_API_TOKEN configured.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from enterprise_completion_patch import connect, apply_sync, audit, p_and_l, trial_balance, verify_audit

try:
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from fastapi.responses import FileResponse
    from enterprise_production import ProductionStore, bootstrap_sql
except ImportError:
    FastAPI = None

DB = os.getenv("POS_DB", "pos.db")
API_TOKEN = os.getenv("POS_API_TOKEN", "").strip()
ALLOW_ANONYMOUS = os.getenv("POS_API_ALLOW_ANONYMOUS", "").strip().lower() in {"1", "true", "yes"}
PROD_DB = os.getenv("DATABASE_URL", "").strip()
VERSION = "2.1.0"

if FastAPI:
    app = FastAPI(title="DEEP-Seek Enterprise POS API", version=VERSION)

    configured_origins = [x.strip() for x in os.getenv("POS_CORS", "").split(",") if x.strip()]
    origins = configured_origins or ["http://localhost", "http://127.0.0.1"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Token"],
    )

    def auth(token: str | None) -> None:
        """Require an API token unless anonymous mode is explicitly enabled."""
        if ALLOW_ANONYMOUS:
            return
        if not API_TOKEN:
            raise HTTPException(503, "API authentication is not configured")
        if not secrets.compare_digest(token or "", API_TOKEN):
            raise HTTPException(401, "Invalid API token")

    def production():
        if not PROD_DB:
            return None
        try:
            store = ProductionStore(PROD_DB)
            bootstrap_sql(store)
            return store
        except Exception:
            return None

    class SyncItem(BaseModel):
        key: str = Field(min_length=8, max_length=200)
        payload: dict

    class GPSItem(BaseModel):
        rider_id: str = Field(min_length=1, max_length=120)
        lat: float = Field(ge=-90, le=90)
        lon: float = Field(ge=-180, le=180)
        accuracy: float | None = Field(default=None, ge=0, le=100000)
        recorded_at: str | None = Field(default=None, max_length=64)

    @app.get("/health")
    def health():
        try:
            c = connect(DB)
            ok = verify_audit(c)
            c.close()
            return {"ok": ok, "service": "DEEP-Seek", "version": VERSION, "mode": "production" if PROD_DB else "local"}
        except Exception as exc:
            raise HTTPException(503, f"health check failed: {exc}")

    @app.get("/ready")
    def ready():
        store = production()
        if PROD_DB and not store:
            raise HTTPException(503, "database not ready")
        if store and not store.ping():
            raise HTTPException(503, "database not ready")
        return {"ready": True, "database": "postgresql" if store else "sqlite"}

    @app.get("/api/pnl")
    def pnl(store_id: str | None = None, x_api_token: str | None = Header(default=None)):
        auth(x_api_token)
        c = connect(DB)
        try:
            return p_and_l(c, store_id)
        finally:
            c.close()

    @app.get("/api/trial-balance")
    def tb(store_id: str | None = None, x_api_token: str | None = Header(default=None)):
        auth(x_api_token)
        c = connect(DB)
        try:
            return trial_balance(c, store_id)
        finally:
            c.close()

    @app.post("/api/sync")
    def sync(item: SyncItem, x_api_token: str | None = Header(default=None)):
        auth(x_api_token)
        c = connect(DB)
        try:
            out = apply_sync(
                c,
                item.key,
                item.payload,
                lambda payload: {
                    "accepted": True,
                    "payload_hash": hashlib.sha256(
                        str(sorted(payload.items())).encode()
                    ).hexdigest(),
                },
            )
            audit(c, "api", "SYNC", "sync", item.key, item.payload)
            return out
        finally:
            c.close()

    def _ensure_gps(c):
        c.execute(
            "CREATE TABLE IF NOT EXISTS ent_gps(" 
            "id INTEGER PRIMARY KEY AUTOINCREMENT," 
            "rider_id TEXT NOT NULL,lat REAL NOT NULL,lon REAL NOT NULL," 
            "accuracy REAL,recorded_at TEXT NOT NULL)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_ent_gps_rider ON ent_gps(rider_id,id DESC)")

    @app.post("/api/gps")
    def gps(item: GPSItem, x_api_token: str | None = Header(default=None)):
        auth(x_api_token)
        c = connect(DB)
        try:
            _ensure_gps(c)
            c.execute(
                "INSERT INTO ent_gps(rider_id,lat,lon,accuracy,recorded_at) "
                "VALUES(?,?,?,?,COALESCE(?,datetime('now')))" ,
                (item.rider_id, item.lat, item.lon, item.accuracy, item.recorded_at),
            )
            c.commit()
            return {"accepted": True}
        finally:
            c.close()

    @app.get("/api/gps/{rider_id}")
    def gps_history(rider_id: str, x_api_token: str | None = Header(default=None)):
        auth(x_api_token)
        if not rider_id or len(rider_id) > 120:
            raise HTTPException(400, "invalid rider id")
        c = connect(DB)
        try:
            _ensure_gps(c)
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM ent_gps WHERE rider_id=? ORDER BY id DESC LIMIT 200",
                    (rider_id,),
                )
            ]
        finally:
            c.close()

    @app.get("/")
    def web():
        p = Path(__file__).with_name("pwa").joinpath("index.html")
        return FileResponse(p) if p.exists() else {"service": "DEEP-Seek", "api": "/health"}
else:
    app = None


if __name__ == "__main__":
    if not app:
        raise SystemExit("Install enterprise requirements")
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("POS_HOST", "0.0.0.0"),
        port=int(os.getenv("POS_PORT", "8080")),
    )

"""
main.py — FastAPI backend for the BTC Options Backtester.

Endpoints:
  GET  /                        → serves dashboard.html
  POST /api/auth/login          → get JWT token
  GET  /api/market/spot         → live spot + funding
  GET  /api/market/option-chain → structured live chain
  GET  /api/market/candles      → historical OHLC
  POST /api/backtest/run        → run a backtest
  GET  /api/backtest/list       → list saved backtests
  GET  /api/backtest/{id}       → load a backtest
  DEL  /api/backtest/{id}       → delete a backtest
  GET  /api/paper/positions     → open paper positions + live P&L
  POST /api/paper/enter         → enter a paper trade
  POST /api/paper/close/{id}    → close a paper position
  GET  /api/paper/history       → closed trades
  GET  /api/scheduler/jobs      → list scheduled jobs
  POST /api/scheduler/create    → create a scheduled job
  POST /api/scheduler/pause/{id}→ pause job
  POST /api/scheduler/resume/{id}→ resume job
  DEL  /api/scheduler/{id}      → delete job
  WS   /ws/live                 → live price stream (every 10s)
"""
import json
import logging
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI, Depends, HTTPException, WebSocket,
    WebSocketDisconnect, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import config
import database as db
from database import get_db, init_db, Backtest, PaperTrade, ScheduledJob
from delta_client import (
    get_spot_ticker, get_option_chain, get_candles,
    structure_option_chain
)
from backtest_engine import run_backtest, price_leg, normalize_leg
from paper_trader import compute_unrealized_pnl, check_exit_conditions
import scheduler as sched

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("main")

# ══════════════════════════════════════════════════════════════════
# APP INIT
# ══════════════════════════════════════════════════════════════════
app = FastAPI(
    title="BTC Options Backtester API",
    description="Live market data, backtesting, paper trading, and scheduling for Delta Exchange.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (dashboard.html, market_data.js, etc.) from parent dir
import os
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ══════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════
oauth2    = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

HASHED_PW = _hash_pw(config.APP_PASSWORD)


def create_token(username: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=config.TOKEN_EXPIRE_MIN)
    return jwt.encode({"sub": username, "exp": exp}, config.SECRET_KEY, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2)) -> str:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ══════════════════════════════════════════════════════════════════
# IN-MEMORY CACHE (live data)
# ══════════════════════════════════════════════════════════════════
_cache: Dict[str, Any] = {
    "spot":      None,
    "chain":     None,
    "candles":   None,
    "last_spot": 0.0,
    "last_chain": 0.0,
    "last_candles": 0.0,
}


async def refresh_spot():
    try:
        ticker = await get_spot_ticker()
        _cache["spot"] = ticker
        _cache["last_spot"] = asyncio.get_event_loop().time()
    except Exception as e:
        logger.warning(f"refresh_spot failed: {e}")


async def refresh_chain():
    try:
        raw  = await get_option_chain()
        spot = float((_cache.get("spot") or {}).get("mark_price", 77000))
        _cache["chain"] = structure_option_chain(raw, spot)
        _cache["last_chain"] = asyncio.get_event_loop().time()
    except Exception as e:
        logger.warning(f"refresh_chain failed: {e}")


async def refresh_candles():
    try:
        _cache["candles"] = await get_candles(days=1000)
        _cache["last_candles"] = asyncio.get_event_loop().time()
    except Exception as e:
        logger.warning(f"refresh_candles failed: {e}")


# ══════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def on_startup():
    init_db()
    # Pre-warm cache
    await asyncio.gather(refresh_spot(), refresh_chain(), refresh_candles())

    # Start background refresh loops
    asyncio.create_task(_spot_refresh_loop())
    asyncio.create_task(_chain_refresh_loop())

    # Init scheduler
    sched.init_scheduler(fire_callback=_on_job_fire)

    # Reload existing active jobs from DB
    _db = next(get_db())
    try:
        jobs = _db.query(ScheduledJob).filter(ScheduledJob.status == "active").all()
        for j in jobs:
            try:
                sched.add_job(j.id, j.cron_expr, json.loads(j.strategy), json.loads(j.params))
                logger.info(f"  Restored job #{j.id}: {j.name}")
            except Exception as e:
                logger.warning(f"  Could not restore job #{j.id}: {e}")
    finally:
        _db.close()

    logger.info("🚀 BTC Backtester backend ready.")


@app.on_event("shutdown")
async def on_shutdown():
    if sched.scheduler:
        sched.scheduler.shutdown(wait=False)


async def _spot_refresh_loop():
    while True:
        await asyncio.sleep(config.PRICE_REFRESH_SECS)
        await refresh_spot()


async def _chain_refresh_loop():
    while True:
        await asyncio.sleep(config.CHAIN_REFRESH_SECS)
        await refresh_chain()


# ══════════════════════════════════════════════════════════════════
# WEBSOCKET — live price broadcast
# ══════════════════════════════════════════════════════════════════
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c != ws]

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            spot_data = _cache.get("spot") or {}
            spot  = float(spot_data.get("mark_price",  77000))
            fund  = float(spot_data.get("funding_rate", 0.005))
            vol24 = float(spot_data.get("volume",       0))
            await ws.send_json({
                "type":         "price",
                "spot":         round(spot, 2),
                "funding_rate": round(fund, 6),
                "funding_ann":  round(fund * 3 * 365 * 100, 2),
                "volume_24h":   round(vol24, 2),
                "ts":           datetime.utcnow().isoformat(),
            })
            await asyncio.sleep(config.PRICE_REFRESH_SECS)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# Broadcast live prices to all WS clients every PRICE_REFRESH_SECS
async def _ws_broadcast_loop():
    while True:
        await asyncio.sleep(config.PRICE_REFRESH_SECS)
        spot_data = _cache.get("spot") or {}
        spot  = float(spot_data.get("mark_price",  77000))
        fund  = float(spot_data.get("funding_rate", 0.005))
        await ws_manager.broadcast({
            "type":  "price",
            "spot":  round(spot, 2),
            "fund":  round(fund, 6),
            "fund_ann": round(fund * 3 * 365 * 100, 2),
            "ts":    datetime.utcnow().isoformat(),
        })

        # Auto-check open paper positions for exit conditions
        _sdb = next(get_db())
        try:
            open_pos = _sdb.query(PaperTrade).filter(PaperTrade.status == "open").all()
            for pos in open_pos:
                reason = check_exit_conditions(pos.to_dict(), spot)
                if reason:
                    _close_paper_trade(pos, spot, reason, _sdb)
                    await ws_manager.broadcast({
                        "type":       "position_closed",
                        "id":         pos.id,
                        "reason":     reason,
                        "pnl":        pos.realized_pnl,
                    })
        finally:
            _sdb.close()


# ══════════════════════════════════════════════════════════════════
# STATIC → serve dashboard
# ══════════════════════════════════════════════════════════════════
@app.get("/", response_class=FileResponse, include_in_schema=False)
async def serve_dashboard():
    path = os.path.join(STATIC_DIR, "dashboard.html")
    return FileResponse(path)


@app.get("/market_data.js", response_class=FileResponse, include_in_schema=False)
async def serve_market_data():
    path = os.path.join(STATIC_DIR, "market_data.js")
    return FileResponse(path)


# ══════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════
@app.post("/api/auth/login", tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != config.APP_USERNAME or _hash_pw(form.password) != HASHED_PW:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": create_token(form.username), "token_type": "bearer"}


@app.get("/api/auth/status", tags=["Auth"])
async def auth_status(user: str = Depends(get_current_user)):
    return {"user": user, "ok": True}


# ══════════════════════════════════════════════════════════════════
# MARKET DATA ROUTES
# ══════════════════════════════════════════════════════════════════
@app.get("/api/market/spot", tags=["Market"])
async def api_spot():
    """Live BTC spot price, funding rate, and 24h volume."""
    if not _cache["spot"]:
        await refresh_spot()
    d = _cache["spot"] or {}
    spot = float(d.get("mark_price", 77000))
    fund = float(d.get("funding_rate", 0.005))
    return {
        "spot":         round(spot, 2),
        "funding_rate": round(fund, 6),
        "funding_ann":  round(fund * 3 * 365 * 100, 2),
        "mark_price":   round(float(d.get("mark_price", spot)), 2),
        "index_price":  round(float(d.get("spot_price", spot)), 2),
        "volume_24h":   round(float(d.get("volume", 0)), 2),
        "ts":           datetime.utcnow().isoformat(),
    }


@app.get("/api/market/option-chain", tags=["Market"])
async def api_option_chain():
    """Structured live BTC option chain: { expiry: { strike: {C:{...}, P:{...}} } }"""
    if not _cache["chain"]:
        await refresh_chain()
    return _cache["chain"] or {}


@app.get("/api/market/candles", tags=["Market"])
async def api_candles(resolution: str = "1d", days: int = 1000):
    """Historical BTC OHLC candles (oldest → newest)."""
    if resolution == "1d" and _cache["candles"] and days <= 1000:
        return _cache["candles"]
    return await get_candles(days=days, resolution=resolution)


# ══════════════════════════════════════════════════════════════════
# BACKTEST ROUTES
# ══════════════════════════════════════════════════════════════════
class BacktestRequest(BaseModel):
    name:          str         = "My Backtest"
    legs:          List[Dict]  = Field(..., description="Strategy legs")
    capital:       float       = 10_000
    lots:          int         = 1
    dte_days:      int         = 7
    sigma:         float       = 0.35
    sl_pct:        float       = 50.0
    tp_pct:        float       = 50.0
    max_days:      int         = 7
    slippage_bps:  float       = 20.0
    entry_mode:    str         = "daily"
    start_date:    Optional[str] = "2024-01-01"
    end_date:      Optional[str] = None
    save:          bool         = True


@app.post("/api/backtest/run", tags=["Backtest"])
async def api_run_backtest(
    req: BacktestRequest,
    database: Session = Depends(get_db),
):
    """Run a full backtest on the server. Optionally save results to DB."""
    # Get candles
    candles = _cache.get("candles") or await get_candles(days=1000)
    if not candles:
        raise HTTPException(500, "No candle data available")

    spot_data = _cache.get("spot") or {}
    fund_rate = float(spot_data.get("funding_rate", 0.005))

    result = run_backtest(
        candles      = candles,
        legs         = req.legs,
        capital      = req.capital,
        lots         = req.lots,
        dte_days     = req.dte_days,
        sigma        = req.sigma / 100 if req.sigma > 1 else req.sigma,  # accept % or decimal
        sl_pct       = req.sl_pct / 100 if req.sl_pct > 1 else req.sl_pct,
        tp_pct       = req.tp_pct / 100 if req.tp_pct > 1 else req.tp_pct,
        max_days     = req.max_days,
        slippage_bps = req.slippage_bps,
        entry_mode   = req.entry_mode,
        start_date   = req.start_date,
        end_date     = req.end_date,
        funding_rate = fund_rate,
    )

    m = result["metrics"]

    if req.save:
        bt = Backtest(
            name       = req.name,
            strategy   = json.dumps(req.legs),
            params     = json.dumps(req.dict(exclude={"legs", "name", "save"})),
            total_pnl  = m["total_pnl"],
            total_ret  = m["total_ret"],
            ann_ret    = m["ann_ret"],
            sharpe     = m["sharpe"],
            max_dd     = m["max_dd"],
            win_rate   = m["win_rate"],
            num_trades = m["num_trades"],
            final_eq   = m["final_equity"],
            results    = json.dumps(result),
        )
        database.add(bt)
        database.commit()
        database.refresh(bt)
        result["backtest_id"] = bt.id

    return result


@app.get("/api/backtest/list", tags=["Backtest"])
async def api_list_backtests(database: Session = Depends(get_db)):
    """List all saved backtests (summary only, no full trade log)."""
    bts = database.query(Backtest).order_by(Backtest.created_at.desc()).all()
    return [b.to_dict() for b in bts]


@app.get("/api/backtest/{bt_id}", tags=["Backtest"])
async def api_get_backtest(bt_id: int, database: Session = Depends(get_db)):
    """Load a saved backtest with full results."""
    bt = database.query(Backtest).filter(Backtest.id == bt_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    return bt.to_full_dict()


@app.delete("/api/backtest/{bt_id}", tags=["Backtest"])
async def api_delete_backtest(bt_id: int, database: Session = Depends(get_db)):
    bt = database.query(Backtest).filter(Backtest.id == bt_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    database.delete(bt)
    database.commit()
    return {"deleted": bt_id}


# ══════════════════════════════════════════════════════════════════
# PAPER TRADING ROUTES
# ══════════════════════════════════════════════════════════════════
class PaperEnterRequest(BaseModel):
    name:    str        = "Manual Trade"
    legs:    List[Dict]
    capital: float      = 10_000
    lots:    int        = 1
    sl_pct:  float      = 50.0
    tp_pct:  float      = 50.0
    dte_days: int       = 7


def _price_entry(legs: list, spot: float, dte_days: int) -> tuple:
    """Returns (entry_prices, net_premium)."""
    from config import DEFAULT_CONTRACT_SIZE
    norm_legs = [normalize_leg(l) for l in legs]
    T       = dte_days / 365.0
    prices  = [price_leg(spot, l, T) for l in norm_legs]
    premium = sum(
        (1 if l["dir"] == "SELL" else -1) * prices[i] * (l.get("qty", 1) or 1) * DEFAULT_CONTRACT_SIZE
        for i, l in enumerate(norm_legs) if l.get("kind") != "future"
    )
    return prices, premium


def _close_paper_trade(pos: PaperTrade, spot: float, reason: str, database: Session):
    """Compute exit prices, finalize P&L, update DB."""
    from config import DEFAULT_CONTRACT_SIZE
    raw_legs     = json.loads(pos.legs) if isinstance(pos.legs, str) else pos.legs
    legs         = [normalize_leg(l) for l in raw_legs]
    entry_prices = json.loads(pos.entry_prices) if isinstance(pos.entry_prices, str) else pos.entry_prices
    T_left       = 0.0  # at close we use intrinsic
    exit_prices  = [price_leg(spot, l, T_left) for l in legs]

    pnl = 0.0
    for i, l in enumerate(legs):
        qty = (l.get("qty", 1) or 1) * pos.lots * DEFAULT_CONTRACT_SIZE
        ep  = entry_prices[i] if i < len(entry_prices) else 0.0
        xp  = exit_prices[i] if i < len(exit_prices) else 0.0
        if l.get("kind") == "future":
            pnl += (1 if l["dir"] == "BUY" else -1) * (spot - ep) * qty
        else:
            pnl += (1 if l["dir"] == "SELL" else -1) * (ep - xp) * qty

    pos.status       = "closed"
    pos.closed_at    = datetime.utcnow()
    pos.exit_spot    = spot
    pos.exit_prices  = json.dumps([round(p, 4) for p in exit_prices])
    pos.realized_pnl = round(pnl, 4)
    pos.exit_reason  = reason
    database.commit()


@app.post("/api/paper/enter", tags=["Paper Trading"])
async def api_paper_enter(
    req: PaperEnterRequest,
    database: Session = Depends(get_db),
):
    spot_data = _cache.get("spot") or {}
    spot = float(spot_data.get("mark_price", 77000))

    prices, premium = _price_entry(req.legs, spot, req.dte_days)

    pt = PaperTrade(
        name         = req.name,
        legs         = json.dumps(req.legs),
        entry_spot   = spot,
        entry_prices = json.dumps([round(p, 4) for p in prices]),
        capital      = req.capital,
        lots         = req.lots,
        premium      = round(premium, 4),
        sl_pct       = req.sl_pct,
        tp_pct       = req.tp_pct,
    )
    database.add(pt)
    database.commit()
    database.refresh(pt)

    d = pt.to_dict()
    d["entry_spot"] = spot
    return d


@app.get("/api/paper/positions", tags=["Paper Trading"])
async def api_paper_positions(database: Session = Depends(get_db)):
    """All open positions with live unrealized P&L."""
    spot_data = _cache.get("spot") or {}
    spot = float(spot_data.get("mark_price", 77000))
    open_pos = database.query(PaperTrade).filter(PaperTrade.status == "open").all()
    result = []
    for p in open_pos:
        d   = p.to_dict()
        pnl = compute_unrealized_pnl(d, spot)
        d.update(pnl)
        result.append(d)
    return result


@app.post("/api/paper/close/{pos_id}", tags=["Paper Trading"])
async def api_paper_close(
    pos_id: int,
    database: Session = Depends(get_db),
):
    pos = database.query(PaperTrade).filter(PaperTrade.id == pos_id).first()
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos.status == "closed":
        raise HTTPException(400, "Already closed")

    spot_data = _cache.get("spot") or {}
    spot = float(spot_data.get("mark_price", 77000))
    _close_paper_trade(pos, spot, "manual", database)
    return pos.to_dict()


@app.get("/api/paper/history", tags=["Paper Trading"])
async def api_paper_history(database: Session = Depends(get_db)):
    closed = (
        database.query(PaperTrade)
        .filter(PaperTrade.status == "closed")
        .order_by(PaperTrade.closed_at.desc())
        .all()
    )
    return [p.to_dict() for p in closed]


@app.get("/api/paper/pnl", tags=["Paper Trading"])
async def api_paper_pnl(database: Session = Depends(get_db)):
    """Summary: realized + unrealized P&L."""
    spot_data = _cache.get("spot") or {}
    spot = float(spot_data.get("mark_price", 77000))

    closed  = database.query(PaperTrade).filter(PaperTrade.status == "closed").all()
    open_ps = database.query(PaperTrade).filter(PaperTrade.status == "open").all()

    realized   = sum(p.realized_pnl or 0 for p in closed)
    unrealized = sum(compute_unrealized_pnl(p.to_dict(), spot)["unrealized_pnl"] for p in open_ps)

    return {
        "realized_pnl":   round(realized, 4),
        "unrealized_pnl": round(unrealized, 4),
        "total_pnl":      round(realized + unrealized, 4),
        "open_positions": len(open_ps),
        "closed_trades":  len(closed),
        "current_spot":   spot,
    }


# ══════════════════════════════════════════════════════════════════
# SCHEDULER ROUTES
# ══════════════════════════════════════════════════════════════════
class ScheduleCreateRequest(BaseModel):
    name:      str
    cron_expr: str        = "0 9 * * 1"   # default: Mon 9AM IST
    legs:      List[Dict]
    params:    Dict       = {}


@app.post("/api/scheduler/create", tags=["Scheduler"])
async def api_scheduler_create(
    req: ScheduleCreateRequest,
    database: Session = Depends(get_db),
):
    job = ScheduledJob(
        name      = req.name,
        cron_expr = req.cron_expr,
        strategy  = json.dumps(req.legs),
        params    = json.dumps(req.params),
        status    = "active",
    )
    database.add(job)
    database.commit()
    database.refresh(job)

    sched.add_job(job.id, req.cron_expr, req.legs, req.params)
    job.next_run = datetime.fromisoformat(sched.get_next_run(job.id)) if sched.get_next_run(job.id) else None
    database.commit()

    return job.to_dict()


@app.get("/api/scheduler/jobs", tags=["Scheduler"])
async def api_scheduler_jobs(database: Session = Depends(get_db)):
    jobs = database.query(ScheduledJob).filter(ScheduledJob.status != "deleted").order_by(ScheduledJob.created_at.desc()).all()
    result = []
    for j in jobs:
        d = j.to_dict()
        d["next_run"] = sched.get_next_run(j.id)
        result.append(d)
    return result


@app.post("/api/scheduler/pause/{job_id}", tags=["Scheduler"])
async def api_scheduler_pause(job_id: int, database: Session = Depends(get_db)):
    j = database.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    sched.pause_job(job_id)
    j.status = "paused"
    database.commit()
    return {"id": job_id, "status": "paused"}


@app.post("/api/scheduler/resume/{job_id}", tags=["Scheduler"])
async def api_scheduler_resume(job_id: int, database: Session = Depends(get_db)):
    j = database.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    sched.resume_job(job_id)
    j.status = "active"
    database.commit()
    return {"id": job_id, "status": "active"}


@app.delete("/api/scheduler/{job_id}", tags=["Scheduler"])
async def api_scheduler_delete(job_id: int, database: Session = Depends(get_db)):
    j = database.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    sched.remove_job(job_id)
    j.status = "deleted"
    database.commit()
    return {"deleted": job_id}


# ══════════════════════════════════════════════════════════════════
# SCHEDULER JOB FIRE CALLBACK
# ══════════════════════════════════════════════════════════════════
async def _on_job_fire(job_id: int, strategy: list, params: dict):
    """Called by APScheduler when a cron job fires. Opens a paper trade."""
    _db = next(get_db())
    try:
        j = _db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
        if not j or j.status != "active":
            return

        spot_data = _cache.get("spot") or {}
        spot = float(spot_data.get("mark_price", 77000))
        dte  = int(params.get("dte_days", 7))

        prices, premium = _price_entry(strategy, spot, dte)

        pt = PaperTrade(
            name         = f"Auto: {j.name}",
            legs         = json.dumps(strategy),
            entry_spot   = spot,
            entry_prices = json.dumps([round(p, 4) for p in prices]),
            capital      = float(params.get("capital", 10000)),
            lots         = int(params.get("lots", 1)),
            premium      = round(premium, 4),
            sl_pct       = float(params.get("sl_pct", 50)),
            tp_pct       = float(params.get("tp_pct", 50)),
        )
        _db.add(pt)

        # Update job stats
        run_log = json.loads(j.run_log)
        run_log.append({"time": datetime.utcnow().isoformat(), "spot": spot, "premium": round(premium, 4)})
        j.run_log   = json.dumps(run_log[-50:])  # keep last 50
        j.last_run  = datetime.utcnow()
        j.total_runs += 1
        _db.commit()

        # Broadcast to WS clients
        await ws_manager.broadcast({
            "type":    "scheduled_trade",
            "job_id":  job_id,
            "job_name": j.name,
            "spot":    spot,
            "premium": round(premium, 4),
        })
        logger.info(f"  Job #{job_id} opened paper trade at spot={spot:.2f}, premium={premium:.4f}")

    finally:
        _db.close()

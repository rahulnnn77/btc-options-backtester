"""
database.py — SQLAlchemy models and DB initialisation.
Tables: backtests, paper_trades, scheduled_jobs
"""
import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Text, Boolean, event
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_URL
import os

# Ensure data/ directory exists
os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")) or ".", exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for better concurrent reads
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── BACKTESTS ──────────────────────────────────────────────────────
class Backtest(Base):
    __tablename__ = "backtests"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Strategy definition (JSON)
    strategy    = Column(Text, nullable=False)   # [{dir, label, kind, ...}, ...]
    params      = Column(Text, nullable=False)   # {capital, dte, iv, sl, tp, ...}

    # Results summary
    total_pnl   = Column(Float, default=0)
    total_ret   = Column(Float, default=0)
    ann_ret     = Column(Float, default=0)
    sharpe      = Column(Float, default=0)
    max_dd      = Column(Float, default=0)
    win_rate    = Column(Float, default=0)
    num_trades  = Column(Integer, default=0)
    final_eq    = Column(Float, default=0)

    # Full results blob (equity curve, trade log, etc.)
    results     = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "strategy":   json.loads(self.strategy),
            "params":     json.loads(self.params),
            "total_pnl":  round(self.total_pnl, 4),
            "total_ret":  round(self.total_ret, 4),
            "ann_ret":    round(self.ann_ret, 4),
            "sharpe":     round(self.sharpe, 4),
            "max_dd":     round(self.max_dd, 4),
            "win_rate":   round(self.win_rate, 2),
            "num_trades": self.num_trades,
            "final_eq":   round(self.final_eq, 2),
        }

    def to_full_dict(self):
        d = self.to_dict()
        d["results"] = json.loads(self.results) if self.results else {}
        return d


# ── PAPER TRADES ───────────────────────────────────────────────────
class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(200), default="Manual Trade")
    status       = Column(String(20), default="open")   # open | closed

    entered_at   = Column(DateTime, default=datetime.utcnow)
    closed_at    = Column(DateTime, nullable=True)

    # Strategy legs at entry
    legs         = Column(Text, nullable=False)          # JSON list of legs
    entry_spot   = Column(Float, nullable=False)

    # Prices at entry (one per leg)
    entry_prices = Column(Text, nullable=False)          # JSON list of floats

    # Prices at exit
    exit_prices  = Column(Text, nullable=True)
    exit_spot    = Column(Float, nullable=True)

    # Financials
    capital      = Column(Float, default=10000)
    lots         = Column(Integer, default=1)
    premium      = Column(Float, default=0)              # net premium collected/paid
    realized_pnl = Column(Float, nullable=True)
    exit_reason  = Column(String(50), nullable=True)

    # Settings at entry
    sl_pct       = Column(Float, default=50)
    tp_pct       = Column(Float, default=50)

    def to_dict(self):
        return {
            "id":           self.id,
            "name":         self.name,
            "status":       self.status,
            "entered_at":   self.entered_at.isoformat() if self.entered_at else None,
            "closed_at":    self.closed_at.isoformat() if self.closed_at else None,
            "legs":         json.loads(self.legs),
            "entry_spot":   self.entry_spot,
            "entry_prices": json.loads(self.entry_prices),
            "exit_prices":  json.loads(self.exit_prices) if self.exit_prices else None,
            "exit_spot":    self.exit_spot,
            "capital":      self.capital,
            "lots":         self.lots,
            "premium":      round(self.premium, 4),
            "realized_pnl": round(self.realized_pnl, 4) if self.realized_pnl is not None else None,
            "exit_reason":  self.exit_reason,
            "sl_pct":       self.sl_pct,
            "tp_pct":       self.tp_pct,
        }


# ── SCHEDULED JOBS ─────────────────────────────────────────────────
class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    cron_expr   = Column(String(100), nullable=False)   # e.g. "0 9 * * 1" = Mon 9AM
    status      = Column(String(20), default="active")  # active | paused | deleted

    strategy    = Column(Text, nullable=False)           # JSON legs
    params      = Column(Text, nullable=False)           # capital, dte, sl, tp, etc.

    created_at  = Column(DateTime, default=datetime.utcnow)
    last_run    = Column(DateTime, nullable=True)
    next_run    = Column(DateTime, nullable=True)
    total_runs  = Column(Integer, default=0)
    total_pnl   = Column(Float, default=0)

    # Log of each run
    run_log     = Column(Text, default="[]")

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "cron_expr":  self.cron_expr,
            "status":     self.status,
            "strategy":   json.loads(self.strategy),
            "params":     json.loads(self.params),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_run":   self.last_run.isoformat() if self.last_run else None,
            "next_run":   self.next_run.isoformat() if self.next_run else None,
            "total_runs": self.total_runs,
            "total_pnl":  round(self.total_pnl, 4),
            "run_log":    json.loads(self.run_log),
        }


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialised at", DATABASE_URL)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

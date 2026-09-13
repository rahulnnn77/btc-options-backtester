"""
config.py — Central configuration for the BTC Options Backtester backend.
All secrets are loaded from environment variables or .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Delta Exchange API ─────────────────────────────────────────────
DELTA_API_KEY    = os.getenv("DELTA_API_KEY",    "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
DELTA_BASE_URL   = os.getenv("DELTA_BASE_URL",   "https://api.delta.exchange")

# ── Application Auth ───────────────────────────────────────────────
APP_USERNAME     = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD     = os.getenv("APP_PASSWORD", "btc123")   # change this!
SECRET_KEY       = os.getenv("SECRET_KEY",   "super-secret-jwt-key-change-in-prod")
TOKEN_EXPIRE_MIN = 60 * 24  # 24 hours

# ── Database ───────────────────────────────────────────────────────
DB_PATH          = os.getenv("DB_PATH", "../data/backtester.db")
DATABASE_URL     = f"sqlite:///{DB_PATH}"

# ── Live Data Settings ─────────────────────────────────────────────
PRICE_REFRESH_SECS   = int(os.getenv("PRICE_REFRESH_SECS", 10))   # WS push interval
CHAIN_REFRESH_SECS   = int(os.getenv("CHAIN_REFRESH_SECS", 30))   # option chain refresh
FUNDING_REFRESH_SECS = int(os.getenv("FUNDING_REFRESH_SECS", 30))

# ── CORS ───────────────────────────────────────────────────────────
CORS_ORIGINS = ["*"]  # lock this down in production

# ── Backtest defaults ──────────────────────────────────────────────
DEFAULT_CONTRACT_SIZE = 0.001  # 1 lot = 0.001 BTC on Delta Exchange
DEFAULT_RISK_FREE     = 0.05   # 5% annual risk-free rate (for BS)

"""
delta_client.py — Authenticated Delta Exchange API client.
Handles HMAC signing, rate limiting, and response parsing.
"""
import time
import hmac
import hashlib
import httpx
import asyncio
from typing import Optional, Dict, Any
from config import DELTA_API_KEY, DELTA_API_SECRET, DELTA_BASE_URL


def _sign(method: str, path: str, payload: str = "") -> Dict[str, str]:
    """Generate HMAC-SHA256 signed headers for Delta Exchange."""
    timestamp = str(int(time.time()))
    message   = method.upper() + timestamp + path + payload
    signature = hmac.new(
        DELTA_API_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "api-key":      DELTA_API_KEY,
        "timestamp":    timestamp,
        "signature":    signature,
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }


# ── Shared async HTTP client ───────────────────────────────────────
_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=DELTA_BASE_URL,
            timeout=15.0,
            headers={"Accept": "application/json"},
        )
    return _client


# ── Public endpoints (no auth needed) ─────────────────────────────
async def get_spot_ticker(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """Fetch live ticker for a perpetual."""
    client = get_client()
    r = await client.get(f"/v2/tickers/{symbol}")
    r.raise_for_status()
    return r.json().get("result", {})


async def get_option_chain() -> list:
    """Fetch all live BTC option tickers with greeks + quotes."""
    client = get_client()
    r = await client.get(
        "/v2/tickers",
        params={"contract_types": "call_options,put_options", "page_size": 500},
    )
    r.raise_for_status()
    raw = r.json().get("result", [])
    return [o for o in raw if o.get("underlying_asset_symbol") == "BTC"]


async def get_candles(
    symbol: str = "BTCUSDT",
    resolution: str = "1d",
    days: int = 1000,
) -> list:
    """Fetch historical OHLC candles (oldest → newest)."""
    client = get_client()
    start  = int(time.time()) - days * 86400
    r = await client.get(
        "/v2/history/candles",
        params={"resolution": resolution, "symbol": symbol, "start": start, "end": int(time.time())},
    )
    r.raise_for_status()
    candles = r.json().get("result", [])
    candles.reverse()   # oldest first
    return candles


async def get_all_products() -> list:
    """Fetch all Delta Exchange products."""
    client = get_client()
    r = await client.get("/v2/products", params={"page_size": 300})
    r.raise_for_status()
    return r.json().get("result", [])


# ── Authenticated endpoints ────────────────────────────────────────
async def get_wallet_balances() -> list:
    """Fetch wallet balances (requires auth)."""
    path   = "/v2/wallet/balances"
    client = get_client()
    r = await client.get(path, headers=_sign("GET", path))
    r.raise_for_status()
    return r.json().get("result", [])


async def get_positions() -> list:
    """Fetch open positions (requires auth)."""
    path   = "/v2/positions/margined"
    client = get_client()
    r = await client.get(path, headers=_sign("GET", path))
    r.raise_for_status()
    return r.json().get("result", [])


# ── Data structuring helpers ───────────────────────────────────────
def structure_option_chain(raw_options: list, spot: float) -> Dict:
    """
    Structure flat option list into nested dict:
    { expiry: { strike_int: { 'C': {...}, 'P': {...} } } }
    """
    chain: Dict[str, Dict[int, Dict]] = {}

    for o in raw_options:
        sym    = o.get("symbol", "")
        parts  = sym.split("-")
        if len(parts) < 4:
            continue

        ctype  = parts[0]                                       # 'C' or 'P'
        strike = int(float(o.get("strike_price", 0) or 0))
        expiry = parts[-1]
        quotes = o.get("quotes") or {}
        greeks = o.get("greeks") or {}

        chain.setdefault(expiry, {}).setdefault(strike, {})

        chain[expiry][strike][ctype] = {
            "symbol":  sym,
            "mark":    round(float(o.get("mark_price",  0) or 0), 2),
            "bid":     round(float(quotes.get("best_bid", 0) or 0), 2),
            "ask":     round(float(quotes.get("best_ask", 0) or 0), 2),
            "iv":      round(float(quotes.get("mark_iv",  0) or 0), 4),
            "bid_iv":  round(float(quotes.get("bid_iv",   0) or 0), 4),
            "ask_iv":  round(float(quotes.get("ask_iv",   0) or 0), 4),
            "delta":   round(float(greeks.get("delta",    0) or 0), 4),
            "gamma":   round(float(greeks.get("gamma",    0) or 0), 6),
            "theta":   round(float(greeks.get("theta",    0) or 0), 4),
            "vega":    round(float(greeks.get("vega",     0) or 0), 4),
            "oi":      int(float(o.get("oi_contracts",    0) or 0)),
            "volume":  round(float(o.get("volume",        0) or 0), 4),
        }

    return chain

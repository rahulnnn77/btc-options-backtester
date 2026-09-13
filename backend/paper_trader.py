"""
paper_trader.py — In-memory + DB-backed paper trading engine.
Tracks live P&L of open positions using real-time Delta prices.
"""
import math
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from backtest_engine import bs_price, get_strike, normalize_leg, DEFAULT_RISK_FREE
from config import DEFAULT_CONTRACT_SIZE


def _price_leg(spot: float, leg: Dict, dte_left: float) -> float:
    """Price a single leg at current spot + remaining DTE."""
    kind = str(leg.get("kind") or leg.get("option_type") or "call").lower()
    if kind == "future":
        return spot
    sigma = float(leg.get("iv") or leg.get("sigma") or 0.35)
    if sigma > 1.0:
        sigma /= 100.0
    if leg.get("strike") is not None:
        K = float(leg["strike"])
    else:
        K = get_strike(spot, leg.get("moneyness", 0))
    return bs_price(spot, K, max(0.0, dte_left), sigma, kind)


def compute_unrealized_pnl(
    position: Dict,
    current_spot: float,
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Given a paper position dict (from DB.to_dict) and the current spot,
    compute unrealized P&L and current greeks.
    """
    if position["status"] == "closed":
        return {"unrealized_pnl": position.get("realized_pnl", 0), "closed": True}

    entered_at_val = position["entered_at"]
    if isinstance(entered_at_val, str):
        entered_at = datetime.fromisoformat(entered_at_val)
    elif isinstance(entered_at_val, datetime):
        entered_at = entered_at_val
    else:
        entered_at = datetime.utcnow()

    now        = current_time or datetime.utcnow()
    days_held  = (now - entered_at).total_seconds() / 86400

    raw_legs     = position.get("legs") or []
    if isinstance(raw_legs, str):
        raw_legs = json.loads(raw_legs)
    legs         = [normalize_leg(l) for l in raw_legs]

    entry_prices = position.get("entry_prices") or []
    if isinstance(entry_prices, str):
        entry_prices = json.loads(entry_prices)

    lots         = position.get("lots", 1)
    CONTRACT     = DEFAULT_CONTRACT_SIZE

    # Estimate original DTE from params (default 7)
    orig_dte  = position.get("params", {}).get("dte_days", 7) if isinstance(position.get("params"), dict) else 7
    dte_left  = max(0.0, (orig_dte - days_held) / 365.0)

    total_pnl = 0.0
    leg_details: List[Dict] = []

    for idx, leg in enumerate(legs):
        ep   = entry_prices[idx] if idx < len(entry_prices) else 0
        kind = leg.get("kind", "call")
        qty  = (leg.get("qty", 1) or 1) * lots * CONTRACT

        if kind == "future":
            leg_pnl = (1 if leg["dir"] == "BUY" else -1) * (current_spot - ep) * qty
        else:
            cur_price = _price_leg(current_spot, leg, dte_left)
            leg_pnl   = (1 if leg["dir"] == "SELL" else -1) * (ep - cur_price) * qty
            ep_ref    = ep

        total_pnl += leg_pnl
        leg_details.append({
            "label":       leg.get("label", ""),
            "dir":         leg["dir"],
            "entry_price": round(ep, 4),
            "current_price": round(_price_leg(current_spot, leg, dte_left) if kind != "future" else current_spot, 4),
            "pnl":         round(leg_pnl, 4),
        })

    premium = position.get("premium", 0)
    return {
        "unrealized_pnl":  round(total_pnl, 4),
        "pnl_pct":         round(total_pnl / abs(premium) * 100, 2) if premium else 0,
        "days_held":       round(days_held, 2),
        "dte_left_days":   round(max(0, orig_dte - days_held), 2),
        "current_spot":    current_spot,
        "legs":            leg_details,
        "closed":          False,
    }


def check_exit_conditions(
    position: Dict,
    current_spot: float,
) -> Optional[str]:
    """
    Returns the exit reason string if an auto-exit condition is met, else None.
    Rules: stop-loss, take-profit, DTE expiry.
    """
    pnl_info = compute_unrealized_pnl(position, current_spot)
    if pnl_info.get("closed"):
        return None

    premium  = abs(position.get("premium", 0))
    upnl     = pnl_info["unrealized_pnl"]
    sl_pct   = position.get("sl_pct", 50) / 100
    tp_pct   = position.get("tp_pct", 50) / 100

    if premium > 0:
        if upnl <= -(premium * sl_pct):
            return "stop-loss"
        if upnl >= premium * tp_pct:
            return "target"

    if pnl_info["dte_left_days"] <= 0:
        return "expiry"

    return None

"""
backtest_engine.py — Full Black-Scholes backtesting engine.
Runs on server-side with full 1000-day dataset.
"""
import math
from typing import List, Dict, Any, Optional
from config import DEFAULT_CONTRACT_SIZE, DEFAULT_RISK_FREE


# ── Black-Scholes ──────────────────────────────────────────────────
def norm_cdf(x: float) -> float:
    a = [0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
    k = 1.0 / (1.0 + 0.2316419 * abs(x))
    y = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x) * (
        a[0]*k + a[1]*k**2 + a[2]*k**3 + a[3]*k**4 + a[4]*k**5
    )
    return y if x >= 0 else 1.0 - y


def bs_price(S: float, K: float, T: float, sigma: float,
             opt_type: str = "call", r: float = DEFAULT_RISK_FREE) -> float:
    if T <= 0:
        return max(0.0, (S - K) if opt_type == "call" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def bs_greeks(S: float, K: float, T: float, sigma: float,
              opt_type: str = "call", r: float = DEFAULT_RISK_FREE) -> Dict:
    if T <= 0:
        return {"delta": 1.0 if (opt_type == "call" and S > K) else 0.0,
                "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    nd1 = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)
    delta = norm_cdf(d1) if opt_type == "call" else -norm_cdf(-d1)
    gamma = nd1 / (S * sigma * math.sqrt(T))
    theta = (-(S * nd1 * sigma) / (2 * math.sqrt(T))
             - r * K * math.exp(-r * T) * (norm_cdf(d2) if opt_type == "call" else norm_cdf(-d2))) / 365
    vega  = S * nd1 * math.sqrt(T) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


# ── Strike helpers ─────────────────────────────────────────────────
def get_strike(spot: float, moneyness: int, step_override: Optional[float] = None) -> int:
    """Return a rounded strike: moneyness=0 → ATM, +1/-1 → one step OTM."""
    step = step_override or (round(spot / 1000) * 100)
    return int(round((spot + moneyness * step) / 100) * 100)


def normalize_leg(l: Dict) -> Dict:
    """Normalize a strategy leg to have standard keys: dir, kind, strike, iv, qty, label."""
    leg = dict(l)
    direction = str(leg.get("dir") or leg.get("action") or "SELL").upper()
    leg["dir"] = "SELL" if "SELL" in direction else "BUY"
    kind = str(leg.get("kind") or leg.get("option_type") or leg.get("type") or "call").lower()
    leg["kind"] = kind
    if leg.get("strike") is not None:
        try:
            leg["strike"] = float(leg["strike"])
        except (ValueError, TypeError):
            pass
    raw_iv = leg.get("iv") if leg.get("iv") is not None else leg.get("sigma")
    if raw_iv is not None:
        try:
            f_iv = float(raw_iv)
            leg["iv"] = f_iv / 100.0 if f_iv > 1.0 else f_iv
        except (ValueError, TypeError):
            pass
    if "qty" not in leg or leg["qty"] is None:
        leg["qty"] = 1.0
    if not leg.get("label"):
        stk_str = f"${int(leg['strike']):,}" if leg.get("strike") else "ATM"
        leg["label"] = f"{stk_str} {kind.upper()}"
    return leg


def price_leg(spot: float, leg: Dict, T: float) -> float:
    """Price a single leg using Black-Scholes (or spot for futures)."""
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

    return bs_price(spot, K, T, sigma, kind)


# ── Main backtest function ─────────────────────────────────────────
def run_backtest(
    candles:    List[Dict],
    legs:       List[Dict],
    capital:    float = 10_000,
    lots:       int   = 1,
    dte_days:   int   = 7,
    sigma:      float = 0.35,
    sl_pct:     float = 0.50,
    tp_pct:     float = 0.50,
    max_days:   int   = 7,
    slippage_bps: float = 20,
    entry_mode: str   = "daily",
    start_date: Optional[str] = None,
    end_date:   Optional[str] = None,
    funding_rate: float = 0.0,
) -> Dict[str, Any]:
    """
    Full backtest.  Returns rich result dict with:
      - trades (full log)
      - equity_curve + equity_dates
      - metrics (sharpe, max_dd, win_rate, etc.)
      - monthly_pnl
    """
    from datetime import datetime

    CONTRACT = DEFAULT_CONTRACT_SIZE
    legs = [normalize_leg(l) for l in legs]
    is_funding_only = all(l.get("kind") == "future" for l in legs)

    # ── Inject sigma into legs (unless they carry chain IV) ─────────
    for l in legs:
        if not (l.get("fromChain") and (l.get("iv") or 0) > 0):
            l["sigma"] = sigma

    # ── Filter candles by date range ────────────────────────────────
    def parse_ts(s: str) -> float:
        return datetime.strptime(s, "%Y-%m-%d").timestamp()

    filtered = candles
    if start_date:
        sd = parse_ts(start_date)
        filtered = [c for c in filtered if c["time"] >= sd]
    if end_date:
        ed = parse_ts(end_date) + 86400
        filtered = [c for c in filtered if c["time"] <= ed]

    if len(filtered) < 5:
        raise ValueError("Not enough candles in the selected date range.")

    trades: List[Dict]  = []
    equity              = capital
    equity_curve        = [capital]
    equity_dates        = []

    i = 0
    while i < len(filtered):
        c    = filtered[i]
        date = datetime.utcfromtimestamp(c["time"]).strftime("%d %b %Y")
        dow  = datetime.utcfromtimestamp(c["time"]).weekday()   # 0=Mon

        # Entry filter
        if entry_mode == "monday"  and dow != 0: i += 1; continue
        if entry_mode == "monthly" and datetime.utcfromtimestamp(c["time"]).day != 1: i += 1; continue

        S0    = c["close"]
        T0    = dte_days / 365.0
        entry_prices = [price_leg(S0, l, T0) for l in legs]

        # Net premium (positive = selling strategy, negative = buying)
        net_prem = sum(
            (1 if l["dir"] == "SELL" else -1) * entry_prices[idx] * (l.get("qty", 1) or 1) * lots * CONTRACT
            for idx, l in enumerate(legs)
            if l.get("kind") != "future"
        )
        slip = abs(net_prem) * slippage_bps / 10_000

        exit_pnl    = None
        exit_date   = date
        exit_reason = "expiry"
        days_held   = 0

        # ── Funding-only strategy ─────────────────────────────────
        if is_funding_only:
            hold = min(dte_days, max_days, len(filtered) - i - 1)
            fund_pnl = sum(
                capital * funding_rate * 3 * (l.get("qty", 1) or 1) * lots * CONTRACT
                for l in legs
            ) * hold
            exit_pnl    = fund_pnl - slip
            days_held   = hold
            exit_date   = datetime.utcfromtimestamp(
                filtered[min(i + hold, len(filtered) - 1)]["time"]
            ).strftime("%d %b %Y")
            exit_reason = "time"

        # ── Options strategy ──────────────────────────────────────
        else:
            max_loss   = abs(net_prem) * sl_pct
            max_profit = abs(net_prem) * tp_pct

            for d in range(1, min(max_days, len(filtered) - i - 1) + 1):
                cn   = filtered[i + d]
                Sn   = cn["close"]
                Tn   = max(0.0, (dte_days - d) / 365.0)
                cur_pnl = 0.0

                for idx, l in enumerate(legs):
                    kind = l.get("kind", "call")
                    qty  = (l.get("qty", 1) or 1) * lots * CONTRACT
                    if kind == "future":
                        cur_pnl += (1 if l["dir"] == "BUY" else -1) * (Sn - entry_prices[idx]) * qty
                    else:
                        exit_p   = price_leg(Sn, l, Tn)
                        cur_pnl += (1 if l["dir"] == "SELL" else -1) * (entry_prices[idx] - exit_p) * qty

                exit_date = datetime.utcfromtimestamp(cn["time"]).strftime("%d %b %Y")
                days_held = d

                if net_prem > 0 and cur_pnl <= -max_loss:
                    exit_pnl    = cur_pnl - slip
                    exit_reason = "stop-loss"
                    break
                if net_prem > 0 and cur_pnl >= max_profit:
                    exit_pnl    = cur_pnl - slip
                    exit_reason = "target"
                    break

            # Expiry if not exited early
            if exit_pnl is None:
                exp_idx = min(i + dte_days, len(filtered) - 1)
                Sexp    = filtered[exp_idx]["close"]
                exp_pnl = 0.0
                for idx, l in enumerate(legs):
                    kind = l.get("kind", "call")
                    qty  = (l.get("qty", 1) or 1) * lots * CONTRACT
                    if kind == "future":
                        exp_pnl += (1 if l["dir"] == "BUY" else -1) * (Sexp - entry_prices[idx]) * qty
                    else:
                        K = int(l["strike"]) if l.get("fromChain") and l.get("strike") else get_strike(S0, l.get("moneyness", 0))
                        intr = max(0, Sexp - K) if kind == "call" else max(0, K - Sexp)
                        exp_pnl += (1 if l["dir"] == "SELL" else -1) * (entry_prices[idx] - intr) * qty

                exit_pnl    = exp_pnl - slip
                exit_date   = datetime.utcfromtimestamp(filtered[exp_idx]["time"]).strftime("%d %b %Y")
                exit_reason = "expiry"

        equity += exit_pnl
        equity_curve.append(round(equity, 4))
        equity_dates.append(exit_date)

        ret_pct = (exit_pnl / abs(net_prem) * 100) if net_prem != 0 else 0

        trades.append({
            "num":        len(trades) + 1,
            "entry_date": date,
            "exit_date":  exit_date,
            "entry_spot": round(S0, 2),
            "strategy":   " / ".join(f"{l['dir'][0]} {l.get('label','leg')}" for l in legs),
            "premium":    round(net_prem, 4),
            "pnl":        round(exit_pnl, 4),
            "return_pct": round(ret_pct, 2),
            "equity":     round(equity, 4),
            "exit_reason": exit_reason,
            "days_held":  days_held,
        })

        skip = 7 if entry_mode == "monday" else (28 if entry_mode == "monthly" else max(1, dte_days))
        i   += skip

    # ── Compute metrics ────────────────────────────────────────────
    pnls      = [t["pnl"] for t in trades]
    wins      = sum(1 for p in pnls if p > 0)
    total_pnl = sum(pnls)
    avg_pnl   = total_pnl / len(pnls) if pnls else 0
    std_pnl   = math.sqrt(sum((p - avg_pnl)**2 for p in pnls) / len(pnls)) if len(pnls) > 1 else 1e-9

    freq      = {"daily": 252, "monday": 52, "monthly": 12}.get(entry_mode, 252 / max(1, dte_days))
    sharpe    = (avg_pnl / std_pnl) * math.sqrt(freq)

    max_dd    = 0.0
    peak      = equity_curve[0]
    for e in equity_curve:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    days_span = (filtered[-1]["time"] - filtered[0]["time"]) / 86400
    total_ret = (equity_curve[-1] - capital) / capital * 100
    ann_ret   = total_ret / (days_span / 365) if days_span > 0 else 0

    # Monthly P&L groups
    from collections import defaultdict
    monthly: Dict[str, float] = defaultdict(float)
    for t in trades:
        parts = t["exit_date"].split(" ")
        key   = f"{parts[1]} {parts[2]}" if len(parts) >= 3 else t["exit_date"]
        monthly[key] += t["pnl"]

    return {
        "trades":       trades,
        "equity_curve": equity_curve,
        "equity_dates": equity_dates,
        "monthly_pnl":  dict(monthly),
        "metrics": {
            "total_pnl":    round(total_pnl, 4),
            "total_ret":    round(total_ret, 4),
            "ann_ret":      round(ann_ret, 4),
            "sharpe":       round(sharpe, 4),
            "max_dd":       round(max_dd, 4),
            "win_rate":     round(wins / len(pnls) * 100, 2) if pnls else 0,
            "wins":         wins,
            "losses":       len(pnls) - wins,
            "num_trades":   len(trades),
            "avg_pnl":      round(avg_pnl, 4),
            "final_equity": round(equity_curve[-1], 2),
            "best_trade":   round(max(pnls), 4) if pnls else 0,
            "worst_trade":  round(min(pnls), 4) if pnls else 0,
            "days_tested":  int(days_span),
        }
    }

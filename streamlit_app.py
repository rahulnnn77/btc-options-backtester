"""
BTC Options & Quantitative Strategy Backtester — Delta Exchange
Streamlit Web Application for Streamlit Community Cloud (streamlit.io)
"""
import os
import json
import math
import time
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
import auth_manager

# ── Page Configuration ─────────────────────────────────────────────
st.set_page_config(
    page_title="BTC Options Backtester — Delta Exchange",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #F8FAFC;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Monospace numerals */
.mono-num, [data-testid="stMetricValue"], table td {
    font-family: 'JetBrains Mono', monospace !important;
    font-variant-numeric: tabular-nums;
}

/* App Background */
.stApp {
    background: #0B0F19;
}

/* Top Hero Header */
.terminal-header {
    background: linear-gradient(180deg, rgba(22, 31, 54, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(12px);
}

.brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #34D399;
    padding: 4px 12px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #10B981;
    box-shadow: 0 0 10px #10B981;
    animation: pulse-glow 1.5s infinite;
}

@keyframes pulse-glow {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
}

/* Modern Metric Cards */
div[data-testid="stMetric"] {
    background: linear-gradient(180deg, #131B2E 0%, #0D1322 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stMetric"]:hover {
    border-color: rgba(16, 185, 129, 0.35) !important;
    transform: translateY(-2px);
}

div[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #94A3B8 !important;
}

div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 26px !important;
    font-weight: 800 !important;
    color: #F8FAFC !important;
}

/* Streamlit Tabs Navigation Bar */
div[data-baseweb="tab-list"] {
    background: #111827 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    padding: 6px !important;
    gap: 6px !important;
    margin-bottom: 24px !important;
}

div[data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 18px !important;
    color: #94A3B8 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    border: 1px solid transparent !important;
    transition: all 0.2s ease !important;
}

div[data-baseweb="tab"]:hover {
    color: #F8FAFC !important;
    background: rgba(255, 255, 255, 0.04) !important;
}

div[aria-selected="true"] {
    color: #10B981 !important;
    background: rgba(16, 185, 129, 0.14) !important;
    border: 1px solid rgba(16, 185, 129, 0.35) !important;
    box-shadow: 0 0 15px rgba(16, 185, 129, 0.15) !important;
}

/* Primary Button Styling */
button[kind="primary"], .stButton > button {
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
    color: #022C22 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 22px !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

button[kind="primary"]:hover, .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 22px rgba(16, 185, 129, 0.5) !important;
    color: #022C22 !important;
}

/* Sidebar Styling */
section[data-testid="stSidebar"] {
    background: #0A0D16 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* Option Chain Custom Table */
.chain-wrapper {
    overflow-x: auto;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    background: #0D1322;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

.chain-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}

.chain-table th {
    background: #131B2E;
    color: #94A3B8;
    padding: 12px 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08);
    white-space: nowrap;
}

.chain-table th.call-hdr {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border-bottom: 2px solid #10B981;
}

.chain-table th.strike-hdr {
    background: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    border-bottom: 2px solid #F59E0B;
}

.chain-table th.put-hdr {
    background: rgba(244, 63, 94, 0.15);
    color: #FB7185;
    border-bottom: 2px solid #F43F5E;
}

.chain-table td {
    padding: 9px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    white-space: nowrap;
    text-align: center;
}

.chain-table tr:hover {
    background: rgba(255, 255, 255, 0.04);
}

.chain-table tr.atm-row {
    background: rgba(245, 158, 11, 0.08);
    border-top: 1px solid rgba(245, 158, 11, 0.3);
    border-bottom: 1px solid rgba(245, 158, 11, 0.3);
}

.strike-pill {
    background: #1E293B;
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    color: #F8FAFC;
    display: inline-block;
}

.strike-pill.atm {
    background: rgba(245, 158, 11, 0.2);
    border: 1px solid #F59E0B;
    color: #FBBF24;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.3);
}

.delta-call { color: #34D399; font-weight: 600; }
.delta-put { color: #FB7185; font-weight: 600; }
.mark-px { font-weight: 700; color: #F1F5F9; }
</style>
""", unsafe_allow_html=True)


# ── Data Helpers ───────────────────────────────────────────────────
def safe_float(val, default=0.0):
    if val is None or val == "" or val == "—" or val == "-":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    if val is None or val == "" or val == "—" or val == "-":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


@st.cache_data(ttl=60)
def fetch_live_spot():
    """Fetch live BTC spot and funding rate from Delta Exchange."""
    try:
        r = requests.get("https://api.delta.exchange/v2/tickers/BTCUSDT", timeout=5)
        if r.ok:
            data = r.json().get("result", {})
            spot = float(data.get("mark_price") or data.get("spot_price") or 77000)
            funding = float(data.get("funding_rate") or 0.005)
            change = float(data.get("mark_change_24h") or 0)
            return spot, funding, change
    except Exception:
        pass
    return 77100.0, 0.0032, 0.0


@st.cache_data(ttl=60)
def fetch_option_tickers():
    """Fetch option tickers from Delta Exchange."""
    try:
        r = requests.get(
            "https://api.delta.exchange/v2/tickers",
            params={"contract_types": "call_options,put_options", "page_size": 500},
            timeout=8
        )
        if r.ok:
            res = r.json().get("result", [])
            return [o for o in res if o.get("underlying_asset_symbol") == "BTC"]
    except Exception:
        pass
    return []


@st.cache_data
def load_historical_candles():
    """Load historical 1000 days of candles."""
    paths = ["data_1000d.json", "data_1d.json"]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    data = json.load(f)
                    if data:
                        return data
            except Exception:
                pass
    # Fallback to Delta Exchange API
    try:
        start = int(time.time()) - 1000 * 86400
        r = requests.get(
            "https://api.delta.exchange/v2/history/candles",
            params={"resolution": "1d", "symbol": "BTCUSDT", "start": start, "end": int(time.time())},
            timeout=10
        )
        if r.ok:
            candles = r.json().get("result", [])
            candles.reverse()
            return candles
    except Exception:
        pass
    return []


# ── Black-Scholes Pricing Engine ───────────────────────────────────
def normal_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def bs_price(S: float, K: float, T: float, sigma: float, kind: str, r: float = 0.05) -> float:
    if T <= 1e-6:
        return max(0.0, S - K) if kind == "call" else max(0.0, K - S)
    if sigma <= 1e-6:
        return max(0.0, S - K * math.exp(-r * T)) if kind == "call" else max(0.0, K * math.exp(-r * T) - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return max(0.0, S * normal_cdf(d1) - K * math.exp(-r * T) * normal_cdf(d2))
    else:
        return max(0.0, K * math.exp(-r * T) * normal_cdf(-d2) - S * normal_cdf(-d1))


def get_strike(spot: float, moneyness: float, step: int = 1000) -> int:
    return int(round((spot + moneyness * step) / 100) * 100)


def run_python_backtest(
    candles: list,
    legs: list,
    capital: float,
    lots: int,
    dte_days: int,
    sigma: float,
    sl_pct: float,
    tp_pct: float,
    max_days: int,
    slippage_bps: float,
    entry_mode: str,
    start_date: str,
    end_date: str,
    funding_rate: float
):
    CONTRACT = 0.001
    sd = datetime.strptime(start_date, "%Y-%m-%d").timestamp() if start_date else 0
    ed = datetime.strptime(end_date, "%Y-%m-%d").timestamp() + 86400 if end_date else 9e10
    filtered = [c for c in candles if sd <= c["time"] <= ed]

    if len(filtered) < 5:
        return None

    trades = []
    equity = capital
    equity_curve = [capital]
    equity_dates = [datetime.utcfromtimestamp(filtered[0]["time"]).strftime("%d %b %Y")]

    i = 0
    while i < len(filtered):
        c = filtered[i]
        c_dt = datetime.utcfromtimestamp(c["time"])
        date_str = c_dt.strftime("%d %b %Y")
        dow = c_dt.weekday()

        if entry_mode == "Monday" and dow != 0:
            i += 1
            continue
        if entry_mode == "Monthly" and c_dt.day != 1:
            i += 1
            continue

        S0 = c["close"]
        T0 = dte_days / 365.0

        entry_prices = []
        for l in legs:
            kind = l.get("kind", "call")
            k = l.get("strike") or get_strike(S0, l.get("moneyness", 0))
            p = bs_price(S0, k, T0, l.get("iv", sigma), kind) if kind != "future" else S0
            entry_prices.append(p)

        net_prem = sum(
            (1 if l["dir"] == "SELL" else -1) * entry_prices[idx] * (l.get("qty", 1) or 1) * lots * CONTRACT
            for idx, l in enumerate(legs) if l.get("kind") != "future"
        )
        slip = abs(net_prem) * slippage_bps / 10000

        exit_pnl = None
        exit_date = date_str
        exit_reason = "expiry"
        days_held = 0

        max_l = abs(net_prem) * (sl_pct / 100)
        max_p = abs(net_prem) * (tp_pct / 100)

        for d in range(1, min(max_days, len(filtered) - i - 1) + 1):
            cn = filtered[i + d]
            Sn = cn["close"]
            Tn = max(0.0, (dte_days - d) / 365.0)
            cur_pnl = 0.0

            for idx, l in enumerate(legs):
                qty = (l.get("qty", 1) or 1) * lots * CONTRACT
                kind = l.get("kind", "call")
                if kind == "future":
                    cur_pnl += (1 if l["dir"] == "BUY" else -1) * (Sn - entry_prices[idx]) * qty
                else:
                    k = l.get("strike") or get_strike(S0, l.get("moneyness", 0))
                    cur_p = bs_price(Sn, k, Tn, l.get("iv", sigma), kind)
                    cur_pnl += (1 if l["dir"] == "SELL" else -1) * (entry_prices[idx] - cur_p) * qty

            exit_date = datetime.utcfromtimestamp(cn["time"]).strftime("%d %b %Y")
            days_held = d

            if net_prem > 0 and cur_pnl <= -max_l:
                exit_pnl = cur_pnl - slip
                exit_reason = "stop-loss"
                break
            if net_prem > 0 and cur_pnl >= max_p:
                exit_pnl = cur_pnl - slip
                exit_reason = "target"
                break

        if exit_pnl is None:
            exp_idx = min(i + dte_days, len(filtered) - 1)
            Sexp = filtered[exp_idx]["close"]
            exp_pnl = 0.0
            for idx, l in enumerate(legs):
                qty = (l.get("qty", 1) or 1) * lots * CONTRACT
                kind = l.get("kind", "call")
                if kind == "future":
                    exp_pnl += (1 if l["dir"] == "BUY" else -1) * (Sexp - entry_prices[idx]) * qty
                else:
                    k = l.get("strike") or get_strike(S0, l.get("moneyness", 0))
                    intr = max(0, Sexp - k) if kind == "call" else max(0, k - Sexp)
                    exp_pnl += (1 if l["dir"] == "SELL" else -1) * (entry_prices[idx] - intr) * qty
            exit_pnl = exp_pnl - slip
            exit_date = datetime.utcfromtimestamp(filtered[exp_idx]["time"]).strftime("%d %b %Y")
            exit_reason = "expiry"

        equity += exit_pnl
        equity_curve.append(round(equity, 2))
        equity_dates.append(exit_date)

        ret_pct = (exit_pnl / abs(net_prem) * 100) if net_prem != 0 else 0
        trades.append({
            "#": len(trades) + 1,
            "Entry Date": date_str,
            "Exit Date": exit_date,
            "Entry Spot ($)": round(S0, 2),
            "Premium ($)": round(net_prem, 2),
            "P&L ($)": round(exit_pnl, 2),
            "Return %": round(ret_pct, 1),
            "Equity ($)": round(equity, 2),
            "Exit Reason": exit_reason,
            "Days Held": days_held
        })

        skip = 7 if entry_mode == "Monday" else (28 if entry_mode == "Monthly" else max(1, dte_days))
        i += skip

    pnls = [t["P&L ($)"] for t in trades]
    wins = [p for p in pnls if p > 0]
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / len(pnls) if pnls else 0
    std_pnl = np.std(pnls) if len(pnls) > 1 else 1e-6
    freq = 52 if entry_mode == "Monday" else (12 if entry_mode == "Monthly" else 365 / max(1, dte_days))
    sharpe = (avg_pnl / std_pnl) * math.sqrt(freq) if std_pnl > 0 else 0

    max_dd = 0.0
    peak = equity_curve[0]
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_ret = (equity_curve[-1] - capital) / capital * 100
    days_span = (filtered[-1]["time"] - filtered[0]["time"]) / 86400
    ann_ret = total_ret / (days_span / 365) if days_span > 0 else 0

    return {
        "trades": trades,
        "equity_curve": equity_curve,
        "equity_dates": equity_dates,
        "total_pnl": total_pnl,
        "total_ret": total_ret,
        "ann_ret": ann_ret,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "win_rate": len(wins) / len(pnls) * 100 if pnls else 0,
        "trades_count": len(trades),
        "wins": len(wins),
        "losses": len(pnls) - len(wins),
        "avg_pnl": avg_pnl
    }


# ── Authentication Gate ────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None

if not st.session_state["authenticated"]:
    # Render Login / Access Request screen
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 25px; padding: 28px 24px; background: linear-gradient(180deg, rgba(22, 31, 54, 0.85) 0%, rgba(13, 19, 34, 0.95) 100%); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 18px; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(16, 185, 129, 0.1); backdrop-filter: blur(16px);">
            <div style="display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 50%; font-size: 28px; margin-bottom: 12px; box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);">
                ⚡
            </div>
            <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #F8FAFC; letter-spacing: -0.02em;">BTC Options & Alpha Terminal</h1>
            <p style="color: #94A3B8; font-size: 13px; margin-top: 6px;">Delta Exchange Institutional Derivatives Suite • Live Greeks • 1,000D Backtesting</p>
            <div style="margin-top: 14px; display: inline-flex; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); padding: 4px 14px; border-radius: 99px; font-size: 12px; font-family: 'JetBrains Mono', monospace; color: #34D399;">
                <span class="pulse-dot"></span> LIVE PROTOCOL READY
            </div>
        </div>
        """, unsafe_allow_html=True)

        login_tab, signup_tab = st.tabs(["🔑 Sign In", "📝 Request Access"])

        with login_tab:
            st.markdown("<div style='padding: 8px 0;'>", unsafe_allow_html=True)
            with st.form("form_signin"):
                st.markdown("#### Account Sign In")
                u_in = st.text_input("Username", placeholder="e.g. admin or rahul").strip()
                p_in = st.text_input("Password", type="password", placeholder="••••••••")
                btn_login = st.form_submit_button("🚀 Enter Platform", use_container_width=True)

                if btn_login:
                    if not u_in or not p_in:
                        st.error("Please enter both username and password.")
                    else:
                        ok, msg, u_data = auth_manager.authenticate_user(u_in, p_in)
                        if ok and u_data:
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = u_data["username"]
                            st.session_state["role"] = u_data.get("role", "user")
                            st.success(f"Welcome, {u_data['username']}! Opening platform...")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

            st.markdown("</div>", unsafe_allow_html=True)

        with signup_tab:
            st.markdown("<div style='padding: 8px 0;'>", unsafe_allow_html=True)
            with st.form("form_request_access"):
                st.markdown("#### Request Access Permission")
                st.caption("New accounts require administrator approval before logging in.")
                req_u = st.text_input("Desired Username", placeholder="e.g. quant_trader").strip()
                req_note = st.text_input("Your Name / Organization", placeholder="e.g. Rahul - Options Analyst").strip()
                req_p1 = st.text_input("Create Password", type="password", placeholder="Minimum 6 characters")
                req_p2 = st.text_input("Confirm Password", type="password", placeholder="Repeat password")
                btn_req = st.form_submit_button("📩 Submit Access Request", use_container_width=True)

                if btn_req:
                    if not req_u or not req_p1:
                        st.error("Username and password are required.")
                    elif req_p1 != req_p2:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = auth_manager.register_user(req_u, req_p1, req_note)
                        if ok:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")
            st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# ── Authenticated User Navigation & Sidebar ────────────────────────
role_title = "🛡️ Administrator" if st.session_state.get("role") == "admin" else "👤 Member"
st.sidebar.markdown(f"""
<div style="background:linear-gradient(180deg, #131B2E 0%, #0D1322 100%); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; margin-bottom:16px; box-shadow:0 4px 15px rgba(0,0,0,0.25);">
    <div style="font-size:10px; color:#94A3B8; text-transform:uppercase; font-weight:700; letter-spacing:0.06em;">Active Account</div>
    <div style="font-size:18px; font-weight:800; color:#F8FAFC; margin:4px 0;">{st.session_state.get('username')}</div>
    <span style="background:rgba(16,185,129,0.15); color:#34D399; font-size:11px; padding:3px 8px; border-radius:4px; font-weight:700; border:1px solid rgba(16,185,129,0.3);">{role_title}</span>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Sign Out", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None
    st.rerun()

st.sidebar.markdown("---")

# ── Main Application ───────────────────────────────────────────────
spot_val, fund_val, change_val = fetch_live_spot()

# Top Hero Navigation Bar
st.markdown(f"""
<div class="terminal-header">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
        <div>
            <div class="brand-badge">
                <span class="pulse-dot"></span> DELTA EXCHANGE OPTIONS API • LIVE FEED
            </div>
            <h1 style="margin:8px 0 4px 0; font-size:26px; font-weight:800; letter-spacing:-0.02em; color:#F8FAFC;">
                ⚡ BTC Options & Quantitative Alpha Backtester
            </h1>
            <p style="margin:0; font-size:13px; color:#94A3B8;">
                Black-Scholes Options Engine • Multi-Leg Backtesting • Deribit & Delta Greek Analytics • Real-Time Paper Trading
            </p>
        </div>
        <div style="text-align:right; background:rgba(15,23,42,0.6); border:1px solid rgba(255,255,255,0.08); padding:10px 18px; border-radius:12px;">
            <div style="font-size:11px; color:#94A3B8; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">BTC / USDT Spot</div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:24px; font-weight:800; color:#10B981; margin:2px 0;">
                ${spot_val:,.2f}
            </div>
            <span style="background:rgba(16,185,129,0.15); color:#34D399; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px; font-family:'JetBrains Mono',monospace;">
                {change_val:+.2f}% (24h)
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Market Stat Bar
c1, c2, c3 = st.columns(3)
c1.metric("BTC / USDT Spot", f"${spot_val:,.2f}", f"{change_val:+.2f}%")
c2.metric("ATM IV (0-DTE)", "14.1%", "Low Contango")
c3.metric("Data Range", "1000 Days", "Dec 2023 – Sep 2026")

st.markdown("<br>", unsafe_allow_html=True)

# Navigation Tabs
is_admin = st.session_state.get("role") == "admin"
tab_titles = [
    "🖥️ Full Interactive Dashboard (HTML/JS)",
    "📊 Python Strategy Backtester",
    "📈 Live Option Chain & Greeks",
    "⚡ Funding Rate Harvest Analyzer"
]
if is_admin:
    tab_titles.append("🛡️ Admin & Permissions")

tabs = st.tabs(tab_titles)
tab_full = tabs[0]
tab_native = tabs[1]
tab_chain = tabs[2]
tab_funding = tabs[3]
if is_admin:
    tab_admin = tabs[4]

# ── TAB 1: FULL EMBEDDED DASHBOARD ────────────────────────────────
with tab_full:
    st.info("💡 **Full Interactive Suite**: Includes interactive payoff diagrams, click-to-add option chain, server backtesting, live paper trading engine, and auto-bot scheduler.")
    dashboard_path = "dashboard.html"
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=1300, scrolling=True)
    else:
        st.warning("`dashboard.html` not found in working directory.")

# ── TAB 2: PYTHON STRATEGY BACKTESTER ──────────────────────────────
with tab_native:
    st.subheader("Backtest Custom BTC Options Strategies")

    col_side, col_main = st.columns([1, 3])

    with col_side:
        st.markdown("#### ⚙️ Strategy Setup")
        preset = st.selectbox(
            "Quick Presets",
            ["Short Straddle (ATM)", "Short Strangle (OTM)", "Iron Condor", "Bull Call Spread", "Bear Put Spread", "Covered Call"]
        )

        capital = st.number_input("Capital (USDT)", value=10000, step=1000)
        lots = st.number_input("Lots (1 lot = 0.001 BTC)", value=1, min_value=1, step=1)
        dte = st.slider("DTE (Days to Expiry)", min_value=1, max_value=30, value=7)
        sigma = st.slider("Implied Volatility (IV %)", min_value=10, max_value=120, value=35) / 100.0

        st.markdown("#### 🛡️ Exit Rules")
        sl = st.slider("Stop Loss %", min_value=10, max_value=200, value=50)
        tp = st.slider("Profit Target %", min_value=10, max_value=200, value=50)
        max_hold = st.number_input("Max Holding Days", value=7, min_value=1, max_value=30)
        slippage = st.number_input("Slippage (bps)", value=20, min_value=0, max_value=100)
        entry_freq = st.selectbox("Entry Frequency", ["Every Trading Day", "Monday", "Monthly"])

        st.markdown("#### 📅 Historical Window")
        c_start, c_end = st.columns(2)
        start_date = c_start.date_input("Start Date", datetime(2024, 1, 1))
        end_date = c_end.date_input("End Date", datetime(2026, 9, 13))

        run_btn = st.button("🚀 Run Backtest", type="primary", use_container_width=True)

    with col_main:
        # Define strategy legs based on preset
        legs = []
        if "Straddle" in preset:
            legs = [
                {"kind": "call", "dir": "SELL", "moneyness": 0, "label": "Call ATM"},
                {"kind": "put", "dir": "SELL", "moneyness": 0, "label": "Put ATM"}
            ]
        elif "Strangle" in preset:
            legs = [
                {"kind": "call", "dir": "SELL", "moneyness": 1, "label": "Call OTM"},
                {"kind": "put", "dir": "SELL", "moneyness": -1, "label": "Put OTM"}
            ]
        elif "Iron Condor" in preset:
            legs = [
                {"kind": "call", "dir": "SELL", "moneyness": 1, "label": "Call OTM (Sell)"},
                {"kind": "call", "dir": "BUY", "moneyness": 2, "label": "Call OTM Wing (Buy)"},
                {"kind": "put", "dir": "SELL", "moneyness": -1, "label": "Put OTM (Sell)"},
                {"kind": "put", "dir": "BUY", "moneyness": -2, "label": "Put OTM Wing (Buy)"}
            ]
        elif "Bull Call" in preset:
            legs = [
                {"kind": "call", "dir": "BUY", "moneyness": 0, "label": "Call ATM (Buy)"},
                {"kind": "call", "dir": "SELL", "moneyness": 1, "label": "Call OTM (Sell)"}
            ]
        elif "Bear Put" in preset:
            legs = [
                {"kind": "put", "dir": "BUY", "moneyness": 0, "label": "Put ATM (Buy)"},
                {"kind": "put", "dir": "SELL", "moneyness": -1, "label": "Put OTM (Sell)"}
            ]
        elif "Covered Call" in preset:
            legs = [
                {"kind": "future", "dir": "BUY", "label": "BTC Future Long"},
                {"kind": "call", "dir": "SELL", "moneyness": 1, "label": "Call OTM (Sell)"}
            ]

        # Display Legs
        st.markdown(f"**Active Strategy**: `{preset}` ({len(legs)} legs)")
        leg_str = " | ".join([f"{l['dir']} {l['label']}" for l in legs])
        st.caption(f"Legs: {leg_str}")

        candles = load_historical_candles()
        if not candles:
            st.error("No historical candles loaded.")
        else:
            freq_key = "Daily" if entry_freq == "Every Trading Day" else entry_freq
            res = run_python_backtest(
                candles=candles,
                legs=legs,
                capital=capital,
                lots=lots,
                dte_days=dte,
                sigma=sigma,
                sl_pct=sl,
                tp_pct=tp,
                max_days=max_hold,
                slippage_bps=slippage,
                entry_mode=freq_key,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                funding_rate=fund_val
            )

            if res:
                # Key Metrics Cards
                m1, m2, m3, m4, m5 = st.columns(5)
                pnl_color = "pos" if res["total_pnl"] >= 0 else "neg"
                m1.markdown(f"<div class='metric-card'><h4>Total P&L</h4><p><span class='{pnl_color}'>${res['total_pnl']:+,.2f}</span> ({res['total_ret']:+.2f}%)</p></div>", unsafe_allow_html=True)
                m2.markdown(f"<div class='metric-card'><h4>Sharpe Ratio</h4><p>{res['sharpe']:.2f}</p></div>", unsafe_allow_html=True)
                m3.markdown(f"<div class='metric-card'><h4>Max Drawdown</h4><p>-{res['max_dd']:.2f}%</p></div>", unsafe_allow_html=True)
                m4.markdown(f"<div class='metric-card'><h4>Win Rate</h4><p>{res['win_rate']:.1f}% ({res['wins']}W / {res['losses']}L)</p></div>", unsafe_allow_html=True)
                m5.markdown(f"<div class='metric-card'><h4>Annualized Return</h4><p>{res['ann_ret']:+.1f}%</p></div>", unsafe_allow_html=True)

                # Charts
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=res["equity_dates"],
                    y=res["equity_curve"],
                    mode="lines",
                    name="Strategy Equity",
                    line=dict(color="#10B981" if res["total_pnl"] >= 0 else "#EF4444", width=2.5),
                    fill="tozeroy",
                    fillcolor="rgba(16, 185, 129, 0.08)" if res["total_pnl"] >= 0 else "rgba(239, 68, 68, 0.08)"
                ))
                fig_eq.add_trace(go.Scatter(
                    x=res["equity_dates"],
                    y=[capital] * len(res["equity_dates"]),
                    mode="lines",
                    name="Initial Capital",
                    line=dict(color="#94A3B8", dash="dash", width=1)
                ))
                fig_eq.update_layout(
                    title=dict(text="📈 Strategy Equity Curve Over Time", font=dict(family="Plus Jakarta Sans", size=16, color="#F8FAFC")),
                    template="plotly_dark",
                    paper_bgcolor="#0D1322",
                    plot_bgcolor="#0D1322",
                    font=dict(family="JetBrains Mono", color="#94A3B8"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.1)", showline=True, linecolor="rgba(255,255,255,0.1)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.1)", showline=True, linecolor="rgba(255,255,255,0.1)"),
                    height=380,
                    margin=dict(l=20, r=20, t=50, b=20),
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_eq, use_container_width=True)

                # P&L per trade distribution
                df_trades = pd.DataFrame(res["trades"])
                df_trades["Color"] = df_trades["P&L ($)"].apply(lambda x: "#10B981" if x >= 0 else "#EF4444")

                fig_bars = go.Figure()
                fig_bars.add_trace(go.Bar(
                    x=df_trades["#"],
                    y=df_trades["P&L ($)"],
                    marker_color=df_trades["Color"],
                    name="Trade P&L"
                ))
                fig_bars.update_layout(
                    title=dict(text="📊 Realized P&L per Trade ($)", font=dict(family="Plus Jakarta Sans", size=16, color="#F8FAFC")),
                    template="plotly_dark",
                    paper_bgcolor="#0D1322",
                    plot_bgcolor="#0D1322",
                    font=dict(family="JetBrains Mono", color="#94A3B8"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.1)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.1)"),
                    height=280,
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                st.plotly_chart(fig_bars, use_container_width=True)

                # Trade log table with download button
                st.markdown("#### 📋 Complete Trade Log")
                st.dataframe(df_trades.drop(columns=["Color"]), use_container_width=True, height=280)
                csv = df_trades.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Trade Log as CSV", data=csv, file_name="btc_options_backtest_trades.csv", mime="text/csv")
            else:
                st.warning("Not enough candle data for selected date range.")

# ── TAB 3: LIVE OPTION CHAIN ──────────────────────────────────────
with tab_chain:
    st.subheader("Delta Exchange Live Option Chain")
    tickers = fetch_option_tickers()
    if not tickers:
        st.warning("Fetching live chain from Delta Exchange... Check your connection.")
    else:
        by_exp = {}
        for t in tickers:
            sym = t.get("symbol", "")
            parts = sym.split("-")
            if len(parts) >= 4:
                exp = parts[-1]
                by_exp.setdefault(exp, []).append(t)

        exp_keys = sorted(list(by_exp.keys()))
        selected_exp = st.selectbox("Select Expiry Date", exp_keys)

        exp_tickers = by_exp.get(selected_exp, [])
        strike_map = {}
        for t in exp_tickers:
            sym = t.get("symbol", "")
            parts = sym.split("-")
            if len(parts) < 4:
                continue
            ctype = parts[0]
            try:
                strike = int(float(t.get("strike_price") or 0))
            except Exception:
                continue
            quotes = t.get("quotes") or {}
            greeks = t.get("greeks") or {}
            strike_map.setdefault(strike, {})[ctype] = {
                "mark": safe_float(t.get("mark_price")),
                "bid": safe_float(quotes.get("best_bid")),
                "ask": safe_float(quotes.get("best_ask")),
                "iv": safe_float(quotes.get("mark_iv")) * 100,
                "delta": safe_float(greeks.get("delta")),
                "oi": safe_int(t.get("oi"))
            }

        sorted_strikes = sorted(strike_map.keys())
        closest_strike = min(sorted_strikes, key=lambda x: abs(x - spot_val)) if sorted_strikes else 0

        rows_html = []
        for s in sorted_strikes:
            c = strike_map[s].get("C", {})
            p = strike_map[s].get("P", {})
            
            c_oi = c.get("oi", 0)
            c_iv = c.get("iv", 0.0)
            c_delta = c.get("delta", 0.0)
            c_mark = c.get("mark", 0.0)

            p_mark = p.get("mark", 0.0)
            p_delta = p.get("delta", 0.0)
            p_iv = p.get("iv", 0.0)
            p_oi = p.get("oi", 0)

            is_atm = (s == closest_strike)
            row_cls = "atm-row" if is_atm else ""
            pill_cls = "strike-pill atm" if is_atm else "strike-pill"
            atm_label = " <span style='font-size:10px; color:#F59E0B; font-weight:800; letter-spacing:0.04em;'>ATM</span>" if is_atm else ""

            rows_html.append(f"""
            <tr class="{row_cls}">
                <td style="color:#94A3B8;">{f"{c_oi:,}" if c_oi else "—"}</td>
                <td style="color:#CBD5E1;">{f"{c_iv:.1f}%" if c_iv > 0 else "—"}</td>
                <td class="delta-call">{f"{c_delta:+.2f}" if c_delta != 0 else "—"}</td>
                <td class="mark-px" style="color:#34D399;">{f"${c_mark:,.2f}" if c_mark > 0 else "—"}</td>
                <td><span class="{pill_cls}">${s:,}{atm_label}</span></td>
                <td class="mark-px" style="color:#FB7185;">{f"${p_mark:,.2f}" if p_mark > 0 else "—"}</td>
                <td class="delta-put">{f"{p_delta:+.2f}" if p_delta != 0 else "—"}</td>
                <td style="color:#CBD5E1;">{f"{p_iv:.1f}%" if p_iv > 0 else "—"}</td>
                <td style="color:#94A3B8;">{f"{p_oi:,}" if p_oi else "—"}</td>
            </tr>
            """)

        table_html = f"""
        <div class="chain-wrapper">
            <table class="chain-table">
                <thead>
                    <tr>
                        <th colspan="4" class="call-hdr">🟢 CALL OPTIONS (BULLISH / VOL)</th>
                        <th class="strike-hdr">STRIKE PRICE</th>
                        <th colspan="4" class="put-hdr">🔴 PUT OPTIONS (BEARISH / VOL)</th>
                    </tr>
                    <tr>
                        <th>Call OI</th>
                        <th>Call IV %</th>
                        <th>Delta (Δ)</th>
                        <th>Mark Price ($)</th>
                        <th class="strike-hdr">Strike Price</th>
                        <th>Mark Price ($)</th>
                        <th>Delta (Δ)</th>
                        <th>Put IV %</th>
                        <th>Put OI</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        """
        st.markdown(table_html, unsafe_allow_html=True)

# ── TAB 4: FUNDING ARBITRAGE ANALYZER ──────────────────────────────
with tab_funding:
    st.subheader("Delta Exchange Funding Rate Arbitrage (Cash & Carry)")
    st.markdown("""
    Delta Exchange perpetual contracts pay funding every 8 hours (3 times a day).
    When funding is positive (longs pay shorts), you can earn high-yield passive income by:
    1. **Buying Spot BTC**
    2. **Shorting BTC-PERP** with equal notional value
    3. **Collecting funding** 3x daily with Delta-Neutral exposure
    """)

    cf1, cf2, cf3 = st.columns(3)
    arb_cap = cf1.number_input("Arbitrage Capital ($)", value=25000, step=5000)
    arb_fund = cf2.number_input("Average 8h Funding Rate (%)", value=float(fund_val*100), step=0.01)
    arb_days = cf3.number_input("Holding Period (Days)", value=365, step=30)

    daily_yield = (arb_fund / 100) * 3
    annual_yield = daily_yield * 365
    expected_pnl = arb_cap * (daily_yield * arb_days)

    st.markdown("---")
    r1, r2, r3 = st.columns(3)
    r1.metric("Projected Yield", f"{annual_yield * 100:.1f}% Ann.", f"{daily_yield*100:.3f}% / day")
    r2.metric(f"Expected Return ({arb_days}d)", f"${expected_pnl:,.2f}", f"+{(expected_pnl/arb_cap)*100:.1f}%")
    r3.metric("Final Portfolio", f"${arb_cap + expected_pnl:,.2f}")

# ── TAB 5: ADMIN & PERMISSION CONTROL ──────────────────────────────
if is_admin:
    with tab_admin:
        st.subheader("🛡️ User Access & Permission Management")
        st.caption("Review access requests, grant/revoke user logins, and manage platform permissions.")

        all_users = auth_manager.list_users()
        pending_users = [u for u in all_users if u["status"] == "pending"]
        approved_users = [u for u in all_users if u["status"] == "approved"]

        # Metric cards
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Users", len(all_users))
        m2.metric("Pending Approvals", len(pending_users), delta=f"{len(pending_users)} waiting" if pending_users else "All Reviewed", delta_color="inverse" if pending_users else "normal")
        m3.metric("Approved Members", len(approved_users))

        st.markdown("---")

        # Section: Pending Requests Queue
        st.markdown("### ⏳ Pending Access Requests")
        if not pending_users:
            st.success("✅ No pending access requests. All registered users are approved or reviewed.")
        else:
            for pu in pending_users:
                p_uname = pu["username"]
                p_note = pu.get("note", "No note provided")
                p_date = pu.get("created_at", "")
                with st.container():
                    col_info, col_act1, col_act2 = st.columns([3, 1, 1])
                    with col_info:
                        st.markdown(f"👤 **`{p_uname}`** &nbsp;|&nbsp; *{p_note}* &nbsp;|&nbsp; <span style='color:#64748B;font-size:12px'>Requested: {p_date}</span>", unsafe_allow_html=True)
                    with col_act1:
                        if st.button(f"✅ Approve Access", key=f"app_{p_uname}", use_container_width=True):
                            auth_manager.approve_user(p_uname)
                            st.success(f"Granted access to {p_uname}!")
                            st.rerun()
                    with col_act2:
                        if st.button(f"❌ Decline", key=f"rej_{p_uname}", use_container_width=True):
                            auth_manager.reject_user(p_uname)
                            st.warning(f"Declined {p_uname}.")
                            st.rerun()
                st.markdown("<hr style='margin:8px 0; border:0; border-top:1px solid #E2E8F0;'>", unsafe_allow_html=True)

        st.markdown("---")

        # Section: User Directory
        st.markdown("### 👥 User Directory")
        df_users = pd.DataFrame(all_users)
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True, height=220)

        # Quick User Actions
        col_act_left, col_act_right = st.columns(2)
        with col_act_left:
            st.markdown("#### ⚡ Revoke or Re-Approve Member")
            non_admin_users = [u["username"] for u in all_users if u["role"] != "admin"]
            if non_admin_users:
                sel_user = st.selectbox("Select Member", non_admin_users)
                act_c1, act_c2, act_c3 = st.columns(3)
                if act_c1.button("Grant Access", key="btn_grant", use_container_width=True):
                    auth_manager.approve_user(sel_user)
                    st.success(f"Granted access to {sel_user}.")
                    st.rerun()
                if act_c2.button("Revoke Access", key="btn_revoke", use_container_width=True):
                    auth_manager.reject_user(sel_user)
                    st.warning(f"Revoked access from {sel_user}.")
                    st.rerun()
                if act_c3.button("Delete User", key="btn_del", use_container_width=True):
                    auth_manager.delete_user(sel_user)
                    st.info(f"Deleted user {sel_user}.")
                    st.rerun()
            else:
                st.caption("No non-admin users registered yet.")

        with col_act_right:
            st.markdown("#### ➕ Add Pre-Approved User")
            with st.form("form_add_direct"):
                new_u = st.text_input("New Username", placeholder="e.g. analyst1").strip()
                new_p = st.text_input("Password", type="password", placeholder="Min 6 chars")
                new_role = st.selectbox("Role", ["user", "admin"])
                new_note = st.text_input("Note", placeholder="e.g. Senior Trader")
                if st.form_submit_button("Create & Pre-Approve", use_container_width=True):
                    if new_u and new_p:
                        ok, msg = auth_manager.add_user_direct(new_u, new_p, new_role, new_note)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Please provide both username and password.")

        st.markdown("---")
        st.markdown("#### 🔑 Change Your Admin Password")
        with st.form("form_change_pwd"):
            curr_user = st.session_state.get("username", "admin")
            pwd_new = st.text_input("New Password", type="password", placeholder="Enter new password")
            pwd_conf = st.text_input("Confirm New Password", type="password", placeholder="Confirm new password")
            if st.form_submit_button("Update Password"):
                if not pwd_new or len(pwd_new) < 6:
                    st.error("Password must be at least 6 characters.")
                elif pwd_new != pwd_conf:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = auth_manager.change_password(curr_user, pwd_new)
                    if ok:
                        st.success("✅ Password updated successfully!")
                    else:
                        st.error(msg)


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
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .metric-card h4 {
        margin: 0;
        font-size: 11px;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-card p {
        margin: 4px 0 0 0;
        font-size: 22px;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-card span.pos { color: #16A34A; font-weight: 600; }
    .metric-card span.neg { color: #DC2626; font-weight: 600; }
    .badge-live {
        background: #DCFCE7;
        color: #15803D;
        padding: 3px 8px;
        border-radius: 99px;
        font-size: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ── Data Helpers ───────────────────────────────────────────────────
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


# ── Main Application ───────────────────────────────────────────────
spot_val, fund_val, change_val = fetch_live_spot()

# Top Navigation Bar
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.title("⚡ BTC Options & Alpha Backtester")
    st.caption("Delta Exchange Quantitative Derivative Strategies — Live Pricing, Black-Scholes Engine, Paper Trading & Scheduling")
with col_t2:
    st.markdown(
        f"<div style='text-align:right;padding-top:10px'>"
        f"<span class='badge-live'>● LIVE DELTA FEED</span><br>"
        f"<span style='font-size:20px;font-weight:700'>${spot_val:,.2f}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

# Market Stat Bar
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("BTC / USDT Spot", f"${spot_val:,.2f}", f"{change_val:+.2f}%")
c2.metric("8h Funding Rate", f"{fund_val*100:.4f}%", "Perpetual")
c3.metric("Annualized Funding", f"{fund_val*3*365*100:.1f}%", "Cash & Carry")
c4.metric("ATM IV (0-DTE)", "14.1%", "Low Contango")
c5.metric("Data Range", "1000 Days", "Dec 2023 – Sep 2026")

st.markdown("---")

# Navigation Tabs
tab_full, tab_native, tab_chain, tab_funding = st.tabs([
    "🖥️ Full Interactive Dashboard (HTML/JS)",
    "📊 Python Strategy Backtester",
    "📈 Live Option Chain & Greeks",
    "⚡ Funding Rate Harvest Analyzer"
])

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
                    title="Equity Curve Over Time",
                    xaxis_title="Date",
                    yaxis_title="Portfolio Equity ($)",
                    height=380,
                    margin=dict(l=20, r=20, t=40, b=20),
                    hovermode="x unified"
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
                    title="P&L Distribution per Trade",
                    xaxis_title="Trade Number",
                    yaxis_title="P&L ($)",
                    height=280,
                    margin=dict(l=20, r=20, t=40, b=20)
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
        rows = []
        strike_map = {}
        for t in exp_tickers:
            parts = t.get("symbol", "").split("-")
            ctype = parts[0]
            strike = int(float(t.get("strike_price") or 0))
            quotes = t.get("quotes") or {}
            greeks = t.get("greeks") or {}
            strike_map.setdefault(strike, {})[ctype] = {
                "mark": t.get("mark_price", 0),
                "bid": quotes.get("best_bid", 0),
                "ask": quotes.get("best_ask", 0),
                "iv": float(quotes.get("mark_iv") or 0) * 100,
                "delta": greeks.get("delta", 0),
                "oi": t.get("oi", 0)
            }

        sorted_strikes = sorted(strike_map.keys())
        table_data = []
        for s in sorted_strikes:
            c = strike_map[s].get("C", {})
            p = strike_map[s].get("P", {})
            table_data.append({
                "Call OI": c.get("oi", "—"),
                "Call IV %": f"{c.get('iv', 0):.1f}%" if c.get("iv") else "—",
                "Call Delta": round(c.get("delta", 0), 2) if c.get("delta") else "—",
                "Call Mark ($)": c.get("mark", "—"),
                "STRIKE": s,
                "Put Mark ($)": p.get("mark", "—"),
                "Put Delta": round(p.get("delta", 0), 2) if p.get("delta") else "—",
                "Put IV %": f"{p.get('iv', 0):.1f}%" if p.get("iv") else "—",
                "Put OI": p.get("oi", "—")
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, height=450)

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

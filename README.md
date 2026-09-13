# ⚡ Delta Exchange BTC Options & Quantitative Strategy Backtester

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance quantitative options backtester and automated trading bot engine built specifically for **Delta Exchange Bitcoin (BTC) Options and Perpetual Futures**.

---

## 🌟 Key Features

1. **📊 1000-Day Historical Options Backtester**:
   - Comprehensive Black-Scholes pricing engine running on real historical BTC market candles (Dec 2023 – Sep 2026).
   - Instant metrics: **Sharpe Ratio**, **Maximum Drawdown**, **Win Rate %**, **Annualized Returns**, and **P&L per trade**.
   - Interactive Equity Curve and monthly return heatmaps.

2. **📈 Real-Time Option Chain & Greeks**:
   - Live Delta Exchange option chain feeds across all active expiry cycles.
   - Strike-by-strike Call/Put table with **Delta**, **Implied Volatility (IV %)**, **Bid/Ask**, and **Open Interest**.
   - 1-click **Buy** / **Sell** action buttons to compose custom multi-leg strategies directly into the builder.

3. **📝 Live Paper Trading Engine**:
   - Enter paper trades with 1 click directly from the Strategy Builder.
   - Real-time unrealized P&L calculations updated against live Delta Exchange mark prices.
   - Automated server-side exit rules for **Stop-Loss**, **Take-Profit**, and **DTE Expiry**.

4. **🤖 Automated Strategy Bot Scheduler**:
   - Schedule quantitative strategies to run automatically on standard cron expressions (e.g., `0 8 * * *` for daily 8:00 AM IST).
   - In-app bot management: **Pause**, **Resume**, and **Delete** active bots with live run logs.

5. **⚡ Delta-Neutral Funding Rate Arbitrage**:
   - Cash-and-carry arbitrage analyzer collecting Delta Exchange 8-hour perpetual funding rates.
   - Projected annualized yield calculator.

---

## 🚀 Instant Deployment on Streamlit Community Cloud

Deploy directly to [share.streamlit.io](https://share.streamlit.io):

1. Fork or push this repository to your GitHub account.
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **"New app"**.
3. Select your repository, set the main file path to:
   ```
   streamlit_app.py
   ```
4. Click **"Deploy"**!

---

## 💻 Running Locally

### Option A: Streamlit Web App
```bash
# Clone the repository
git clone https://github.com/rahulnnn77/btc-options-backtester.git
cd btc-options-backtester

# Install dependencies
pip install -r requirements.txt

# Launch Streamlit app
streamlit run streamlit_app.py
```

### Option B: FastAPI Backend + Full Web Dashboard
```bash
# Start FastAPI backend server
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- Open `http://localhost:8000/` in your browser.
- Interactive Swagger API docs: `http://localhost:8000/docs`

---

## 🏛️ Project Architecture

```
├── streamlit_app.py         # Streamlit Cloud application entrypoint
├── dashboard.html           # Full interactive client dashboard (HTML/Vanilla CSS/JS)
├── market_data.js           # Embedded candle and market data
├── data_1000d.json          # 1000 days of historical daily BTC candles
├── backend/
│   ├── main.py              # FastAPI server, REST routes, WebSocket broadcaster
│   ├── delta_client.py      # HMAC-authenticated async Delta Exchange client
│   ├── backtest_engine.py   # Black-Scholes pricing & backtesting engine
│   ├── paper_trader.py      # Real-time unrealized P&L & auto-exit monitor
│   ├── scheduler.py         # APScheduler cron job scheduler
│   ├── database.py          # SQLite persistence (backtests, paper trades, jobs)
│   └── config.py            # Central configuration & secrets
├── requirements.txt         # Root Python requirements
└── README.md                # Documentation
```

---

## 🔒 Security Note
Never commit your raw Delta Exchange API keys or secrets to public repositories. Set `DELTA_API_KEY` and `DELTA_API_SECRET` as environment variables or inside Streamlit Cloud Secrets (`.streamlit/secrets.toml`).

---

## 📄 License
MIT License. Free for educational and algorithmic trading purposes.
